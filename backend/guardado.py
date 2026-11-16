"""Todo lo que la app guarda de una persona con cuenta pasa por este módulo, y solo por este.

Qué se guarda de una póliza: su texto partido en fragmentos, sus vectores y el texto de cada
página leído con los dos extractores (contra eso se verifican las citas). El archivo PDF no
se guarda. De las consultas, las últimas 20 por póliza: pregunta, respuesta y citas.

Dónde: en la base de DATABASE_URL (Neon), tablas `polizas` y `consultas`. El contenido va
cifrado por la app con AES-256-GCM antes de llegar a la base; la llave es QMC_CLAVE_DATOS,
una variable de entorno del servidor. Quien administra el servidor tiene la llave y por lo
tanto podría leer el contenido: la política de privacidad lo dice así.

Si más adelante se guardan archivos (el PDF, por ejemplo), entra aquí: `guardar_poliza`,
`cargar_poliza` y `borrar_poliza` son los únicos puntos que tocan el contenido.
"""

from __future__ import annotations

import base64
import gzip
import io
import json
import os
import secrets
from datetime import datetime, timedelta, timezone

import numpy as np
import sqlalchemy as sa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ai.indice import Indice
from ai.llm import config
from ai.respuesta import Poliza
from ai.troceado import Trozo
from ai.verificacion import leer_todas

MAX_CONSULTAS = 20
_meta = sa.MetaData()
usuarios = sa.Table(
    "usuarios", _meta,
    sa.Column("id", sa.String(40), primary_key=True),
    sa.Column("correo", sa.String(254), nullable=False, unique=True),
    sa.Column("clave_hash", sa.String(200), nullable=False),
    sa.Column("plan", sa.String(10), nullable=False),  # "gratis" o "pagado"
    sa.Column("creado", sa.DateTime(timezone=True), nullable=False),
    sa.Column("ultimo_acceso", sa.DateTime(timezone=True), nullable=False),
    sa.Column("acepto_privacidad", sa.DateTime(timezone=True), nullable=False),  # consentimiento explícito (Ley 29733)
)
sesiones = sa.Table(
    "sesiones", _meta,
    sa.Column("token_hash", sa.String(64), primary_key=True),
    sa.Column("usuario_id", sa.String(40), nullable=False, index=True),
    sa.Column("expira", sa.DateTime(timezone=True), nullable=False),
)
polizas = sa.Table(
    "polizas", _meta,
    sa.Column("id", sa.String(40), primary_key=True),
    sa.Column("usuario_id", sa.String(40), nullable=False, index=True),
    sa.Column("creado", sa.DateTime(timezone=True), nullable=False),
    sa.Column("borrar_el", sa.DateTime(timezone=True), nullable=True),  # plan gratis: a los 7 días; pagado: nunca
    sa.Column("contenido", sa.LargeBinary, nullable=False),  # cifrado: nombre, fragmentos, vectores y texto de las páginas
)
consultas = sa.Table(
    "consultas", _meta,
    sa.Column("id", sa.String(40), primary_key=True),
    sa.Column("poliza_id", sa.String(40), nullable=False, index=True),
    sa.Column("usuario_id", sa.String(40), nullable=False, index=True),
    sa.Column("creado", sa.DateTime(timezone=True), nullable=False),
    sa.Column("contenido", sa.LargeBinary, nullable=False),  # cifrado: pregunta, respuesta y citas verificadas
)
TABLAS = (usuarios, sesiones, polizas, consultas)


class SinLlave(RuntimeError):
    """Falta QMC_CLAVE_DATOS: sin llave no se guarda nada."""


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def _utc(fecha: datetime | None) -> datetime | None:
    """SQLite devuelve las fechas sin zona: se leen como UTC."""
    return fecha if fecha is None or fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def nueva_llave() -> str:
    return base64.urlsafe_b64encode(AESGCM.generate_key(bit_length=256)).decode()


def _llave() -> AESGCM:
    texto = config("QMC_CLAVE_DATOS")
    if not texto:
        raise SinLlave("Falta QMC_CLAVE_DATOS: el guardado de pólizas no está configurado.")
    llave = base64.urlsafe_b64decode(texto)
    if len(llave) != 32:
        raise SinLlave("QMC_CLAVE_DATOS no es una llave de 256 bits.")
    return AESGCM(llave)


def hay_llave() -> bool:
    try:
        _llave()
        return True
    except (SinLlave, ValueError):
        return False


def cifrar(datos: dict, atado_a: str) -> bytes:
    """JSON comprimido y cifrado con AES-256-GCM. `atado_a` (el id de la fila y su dueño) va
    autenticado: un contenido movido a otra fila o a otra cuenta no se descifra."""
    nonce = os.urandom(12)
    claro = gzip.compress(json.dumps(datos, ensure_ascii=False).encode())
    return nonce + _llave().encrypt(nonce, claro, atado_a.encode())


def descifrar(cifrado: bytes, atado_a: str) -> dict:
    return json.loads(gzip.decompress(_llave().decrypt(cifrado[:12], cifrado[12:], atado_a.encode())))


def crear_tablas(motor: sa.Engine) -> None:
    _meta.create_all(motor)


# ---------------------------------------------------------------------------
# Pólizas
# ---------------------------------------------------------------------------


def _empacar(poliza: Poliza, radiografia: dict | None) -> dict:
    paginas = int(poliza.indice.meta.get("paginas") or max(p for t in poliza.indice.trozos for p in t.paginas))
    if poliza.pdf_bytes:  # completa lo que falte leer; una póliza ya cargada de la base no tiene PDF
        leer_todas(poliza.pdf_bytes, poliza.paginas_leidas, paginas)
    vectores = None
    if poliza.indice.vectores is not None:
        memoria = io.BytesIO()
        np.save(memoria, poliza.indice.vectores.astype(np.float16))
        vectores = base64.b64encode(memoria.getvalue()).decode()
    return {
        "nombre": poliza.nombre, "sha256": poliza.sha256, "archivos": poliza.archivos, "revision": poliza.revision,
        "meta": poliza.indice.meta, "trozos": [t.a_dict() for t in poliza.indice.trozos], "vectores": vectores,
        "paginas": {lector: {str(n): poliza.paginas_leidas.get((lector, n), "") for n in range(1, paginas + 1)}
                    for lector in ("pdfplumber", "pypdf")},
        "radiografia": radiografia,
    }


def _desempacar(poliza_id: str, datos: dict) -> Poliza:
    vectores = None
    if datos["vectores"]:
        vectores = np.load(io.BytesIO(base64.b64decode(datos["vectores"]))).astype(np.float32)
    indice = Indice([Trozo.de_dict(t) for t in datos["trozos"]], vectores, datos["meta"])
    poliza = Poliza(poliza_id, datos["nombre"], indice, b"", datos["sha256"],
                    archivos=[tuple(a) for a in datos["archivos"]], revision=datos.get("revision"))
    for lector, por_pagina in datos["paginas"].items():
        for n, texto in por_pagina.items():
            poliza.paginas_leidas[lector, int(n)] = texto
    if datos.get("radiografia"):
        poliza.radiografia = datos["radiografia"]
    return poliza


def contar_polizas(motor: sa.Engine, usuario_id: str) -> int:
    with motor.connect() as c:
        return c.execute(sa.select(sa.func.count()).select_from(polizas).where(
            polizas.c.usuario_id == usuario_id, sa.or_(polizas.c.borrar_el.is_(None), polizas.c.borrar_el > ahora()))).scalar()


def guardar_poliza(motor: sa.Engine, usuario_id: str, poliza: Poliza, dias: int | None, radiografia: dict | None = None) -> dict:
    """Guarda el índice de la póliza (no el PDF). `dias`: en cuántos días se borra sola; None, nunca."""
    poliza_id = "g_" + secrets.token_urlsafe(18)
    creado = ahora()
    borrar_el = creado + timedelta(days=dias) if dias else None
    with motor.begin() as c:
        c.execute(sa.insert(polizas).values(id=poliza_id, usuario_id=usuario_id, creado=creado, borrar_el=borrar_el,
                                            contenido=cifrar(_empacar(poliza, radiografia), f"{poliza_id}|{usuario_id}")))
    return {"poliza_id": poliza_id, "nombre": poliza.nombre, "paginas": poliza.indice.meta.get("paginas"), "creado": creado, "borrar_el": borrar_el}


def cargar_poliza(motor: sa.Engine, usuario_id: str, poliza_id: str) -> Poliza | None:
    """La póliza guardada, si es de esa cuenta y no venció. Una vencida no se devuelve aunque
    la limpieza todavía no la haya borrado."""
    with motor.connect() as c:
        fila = c.execute(sa.select(polizas.c.contenido, polizas.c.borrar_el).where(
            polizas.c.id == poliza_id, polizas.c.usuario_id == usuario_id)).first()
    if fila is None or (fila.borrar_el is not None and _utc(fila.borrar_el) <= ahora()):
        return None
    return _desempacar(poliza_id, descifrar(fila.contenido, f"{poliza_id}|{usuario_id}"))


def actualizar_radiografia(motor: sa.Engine, usuario_id: str, poliza_id: str, radiografia: dict) -> None:
    atado = f"{poliza_id}|{usuario_id}"
    with motor.begin() as c:
        fila = c.execute(sa.select(polizas.c.contenido).where(polizas.c.id == poliza_id, polizas.c.usuario_id == usuario_id)).first()
        if fila is not None:
            c.execute(sa.update(polizas).where(polizas.c.id == poliza_id).values(
                contenido=cifrar(descifrar(fila.contenido, atado) | {"radiografia": radiografia}, atado)))


def listar_polizas(motor: sa.Engine, usuario_id: str) -> list[dict]:
    with motor.connect() as c:
        filas = c.execute(sa.select(polizas.c.id, polizas.c.creado, polizas.c.borrar_el, polizas.c.contenido).where(
            polizas.c.usuario_id == usuario_id, sa.or_(polizas.c.borrar_el.is_(None), polizas.c.borrar_el > ahora())
        ).order_by(polizas.c.creado.desc())).all()
    salida = []
    for f in filas:
        datos = descifrar(f.contenido, f"{f.id}|{usuario_id}")
        salida.append({"poliza_id": f.id, "nombre": datos["nombre"], "paginas": datos["meta"].get("paginas"),
                       "archivos": [{"nombre": n, "paginas": p} for n, p in datos["archivos"]],
                       "creado": _utc(f.creado), "borrar_el": _utc(f.borrar_el)})
    return salida


def borrar_poliza(motor: sa.Engine, usuario_id: str, poliza_id: str) -> bool:
    """Borra la póliza y todas sus consultas."""
    with motor.begin() as c:
        c.execute(sa.delete(consultas).where(consultas.c.poliza_id == poliza_id, consultas.c.usuario_id == usuario_id))
        return c.execute(sa.delete(polizas).where(polizas.c.id == poliza_id, polizas.c.usuario_id == usuario_id)).rowcount > 0


def conservar_polizas(motor: sa.Engine, usuario_id: str) -> None:
    """Al pasar al plan pagado: las pólizas guardadas dejan de tener fecha de borrado."""
    with motor.begin() as c:
        c.execute(sa.update(polizas).where(polizas.c.usuario_id == usuario_id).values(borrar_el=None))


# ---------------------------------------------------------------------------
# Historial de consultas
# ---------------------------------------------------------------------------

_CAMPOS = ("modo", "pregunta", "documento", "aviso", "cubre", "etiqueta_veredicto", "respuesta", "condiciones", "exclusiones_aplicables",
           "podrian_aplicar", "no_incluido_en_documento", "citas", "mencionadas_ausentes", "repreguntas", "fecha_hecho")


def _resumen(r: dict) -> dict:
    """Lo que se guarda de una respuesta: lo que se le mostró a la persona, sin los pasajes."""
    salida = {k: r[k] for k in _CAMPOS if k in r}
    if "respuestas" in r:
        salida["respuestas"] = [_resumen(x) for x in r["respuestas"]]
    return salida


def guardar_consulta(motor: sa.Engine, usuario_id: str, poliza_id: str, respuesta: dict) -> str:
    consulta_id = "c_" + secrets.token_urlsafe(18)
    with motor.begin() as c:
        c.execute(sa.insert(consultas).values(id=consulta_id, poliza_id=poliza_id, usuario_id=usuario_id, creado=ahora(),
                                              contenido=cifrar(_resumen(respuesta), f"{consulta_id}|{usuario_id}")))
        viejas = c.execute(sa.select(consultas.c.id).where(consultas.c.poliza_id == poliza_id, consultas.c.usuario_id == usuario_id)
                           .order_by(consultas.c.creado.desc(), consultas.c.id).offset(MAX_CONSULTAS)).scalars().all()
        if viejas:
            c.execute(sa.delete(consultas).where(consultas.c.id.in_(viejas)))
    return consulta_id


def listar_consultas(motor: sa.Engine, usuario_id: str, poliza_id: str) -> list[dict]:
    with motor.connect() as c:
        filas = c.execute(sa.select(consultas.c.id, consultas.c.creado, consultas.c.contenido).where(
            consultas.c.poliza_id == poliza_id, consultas.c.usuario_id == usuario_id).order_by(consultas.c.creado.desc())).all()
    return [{"consulta_id": f.id, "creado": _utc(f.creado), **descifrar(f.contenido, f"{f.id}|{usuario_id}")} for f in filas]


def borrar_consulta(motor: sa.Engine, usuario_id: str, consulta_id: str) -> bool:
    with motor.begin() as c:
        return c.execute(sa.delete(consultas).where(consultas.c.id == consulta_id, consultas.c.usuario_id == usuario_id)).rowcount > 0


# ---------------------------------------------------------------------------
# Borrado: el de la cuenta entera y el automático
# ---------------------------------------------------------------------------


def borrar_todo(motor: sa.Engine, usuario_id: str) -> dict:
    """Borra la cuenta y todo lo suyo, de todas las tablas. Devuelve cuántas filas quitó de cada una."""
    with motor.begin() as c:
        return {t.name: c.execute(sa.delete(t).where((t.c.id if t is usuarios else t.c.usuario_id) == usuario_id)).rowcount
                for t in (consultas, polizas, sesiones, usuarios)}


def purgar(motor: sa.Engine, momento: datetime | None = None, meses_inactiva: int = 12) -> dict:
    """La limpieza automática: pólizas vencidas (con sus consultas), sesiones vencidas y cuentas
    sin entrar en `meses_inactiva` meses. `momento` permite adelantar el reloj en las pruebas."""
    momento = momento or ahora()
    with motor.begin() as c:
        vencidas = c.execute(sa.select(polizas.c.id).where(polizas.c.borrar_el.is_not(None), polizas.c.borrar_el <= momento)).scalars().all()
        n_consultas = c.execute(sa.delete(consultas).where(consultas.c.poliza_id.in_(vencidas))).rowcount if vencidas else 0
        n_polizas = c.execute(sa.delete(polizas).where(polizas.c.id.in_(vencidas))).rowcount if vencidas else 0
        n_sesiones = c.execute(sa.delete(sesiones).where(sesiones.c.expira <= momento)).rowcount
        inactivas = c.execute(sa.select(usuarios.c.id).where(usuarios.c.ultimo_acceso <= momento - timedelta(days=30 * meses_inactiva))).scalars().all()
    for usuario_id in inactivas:
        borrar_todo(motor, usuario_id)
    return {"polizas": n_polizas, "consultas": n_consultas, "sesiones": n_sesiones, "cuentas_inactivas": len(inactivas)}


def filas(motor: sa.Engine, usuario_id: str | None = None) -> dict:
    """Cuántas filas hay en cada tabla (de una cuenta, o en total). Para las pruebas de borrado."""
    with motor.connect() as c:
        salida = {}
        for t in TABLAS:
            consulta = sa.select(sa.func.count()).select_from(t)
            if usuario_id is not None:
                consulta = consulta.where((t.c.id if t is usuarios else t.c.usuario_id) == usuario_id)
            salida[t.name] = c.execute(consulta).scalar()
        return salida


if __name__ == "__main__":
    # Genera una llave nueva para ponerla en QMC_CLAVE_DATOS (Render > Environment). Guárdala
    # también fuera de Render: si se pierde, lo guardado no se puede descifrar.
    print(nueva_llave())

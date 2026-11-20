"""API de ¿Qué Cubre?: el mismo pipeline de ai/ detrás de HTTP.

    uvicorn backend.main:app --reload

Endpoints: subir uno o varios PDF, preguntar (con repregunta si falta información y una
respuesta por pregunta si vienen varias), los pasos para reclamar con su fecha límite, la
radiografía de la póliza, las coberturas que se superponen entre pólizas, borrar la póliza
subida y el mapa de RENIPRESS. El cliente manda en X-Dispositivo un identificador que él mismo genera.

Privacidad: el PDF subido vive solo en memoria (backend/almacen.py); se sube el umbral con
el que Starlette pasa un archivo a disco temporal para que tampoco toque el disco al llegar.
Al cliente va solo lo verificado: se quitan la salida cruda del modelo y los descartes.
"""

from __future__ import annotations

import datetime as dt
import math
import threading
import time
from dataclasses import dataclass
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.concurrency import run_in_threadpool  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from starlette.formparsers import MultiPartParser  # noqa: E402

from ai import consulta as flujo  # noqa: E402
from ai import clinicas, embeddings, pasos, radiografia, renipress, subida  # noqa: E402
from ai.llm import ErrorLLM, LimiteAlcanzado, ProveedorNoDisponible, config, obtener_proveedor  # noqa: E402
from ai.recuperacion import metodo_efectivo  # noqa: E402
from ai.respuesta import Poliza, responder  # noqa: E402
from backend import acceso_google, almacen, cuentas, guardado, observabilidad, pagos  # noqa: E402
from backend.limites import LIMA, Limites, clave_dispositivo, clave_ip  # noqa: E402

VERSION = "1.3.0"
POLITICA = config("QMC_POLITICA_URL") or "https://github.com/RenatoGates/que-me-cubre/blob/main/docs/privacidad.md"
MAX_ARCHIVOS = 6
MAX_BYTES = 20 * 1024 * 1024  # por archivo
MultiPartParser.spool_max_size = MAX_BYTES + 1

subidas = almacen.Subidas()


@lru_cache(maxsize=1)
def limites() -> Limites:
    lim = Limites()
    guardado.crear_tablas(lim.motor)  # cuentas, pólizas guardadas e historial: misma base que los contadores
    return lim


_ultima_limpieza = 0.0


def limpiar_vencido() -> None:
    """Borra pólizas vencidas, sesiones vencidas y cuentas inactivas; como mucho una vez por hora.
    El servidor gratuito se duerme, así que no hay tarea programada: se hace al atender."""
    global _ultima_limpieza
    if time.monotonic() - _ultima_limpieza > 3600 or _ultima_limpieza == 0.0:
        _ultima_limpieza = time.monotonic()
        guardado.purgar(limites().motor)


class SinModelo:
    """Proveedor que no llama a nadie: todo sale por la red de seguridad (cláusulas sin veredicto)."""

    nombre = "ninguno"
    modelos = {"normalizacion": "—", "respuesta": "—"}
    reutiliza_datos = False
    aviso = "No se llamó al modelo."

    def __init__(self, error: ErrorLLM) -> None:
        self.error = error

    def json(self, *args, **kwargs):
        raise self.error


@lru_cache(maxsize=1)
def proveedor():
    try:
        return obtener_proveedor()
    except ErrorLLM as e:
        return SinModelo(ProveedorNoDisponible(str(e)))


def proveedor_por_tope() -> SinModelo:
    error = LimiteAlcanzado("tope global mensual")
    error.motivo_publico = "Este mes el servicio llegó a su tope de gasto en el modelo."
    return SinModelo(error)


@asynccontextmanager
async def ciclo(_app: FastAPI):
    observabilidad.activar()
    limites()
    limpiar_vencido()
    yield
    observabilidad.cerrar()


app = FastAPI(title="¿Qué Cubre?", version=VERSION, lifespan=ciclo)


def error(status: int, codigo: str, mensaje: str, **extra) -> HTTPException:
    return HTTPException(status, {"codigo": codigo, "mensaje": mensaje, **extra})


def ip_de(request: Request) -> str:
    reenviada = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return reenviada or (request.client.host if request.client else "desconocida")


def dispositivo_valido(dispositivo: str | None) -> str:
    if not dispositivo or not (8 <= len(dispositivo) <= 100):
        raise error(400, "falta_dispositivo", "Falta el encabezado X-Dispositivo (entre 8 y 100 caracteres).")
    return dispositivo


@dataclass
class Quien:
    """Quién hace la petición: una cuenta (con sesión) o un dispositivo sin cuenta."""

    cuenta: dict | None
    dispositivo: str | None  # hash del identificador que manda el cliente

    @property
    def plan(self) -> str:
        return self.cuenta["plan"] if self.cuenta else "sin_cuenta"

    @property
    def clave(self) -> str:
        return "u:" + self.cuenta["usuario_id"] if self.cuenta else self.dispositivo


def token_de(authorization: str | None) -> str | None:
    return authorization[7:].strip() if authorization and authorization.lower().startswith("bearer ") else None


def quien_es(x_dispositivo: str | None, authorization: str | None, exigir_cuenta: bool = False) -> Quien:
    token = token_de(authorization)
    cuenta = cuentas.de_sesion(limites().motor, token) if token else None
    if token and cuenta is None:
        raise error(401, "sesion_vencida", "Tu sesión venció. Vuelve a entrar.")
    if cuenta is None and exigir_cuenta:
        raise error(401, "sin_sesion", "Para esto necesitas entrar a tu cuenta.")
    return Quien(cuenta, None if cuenta else clave_dispositivo(dispositivo_valido(x_dispositivo)))


def fecha_lima(momento) -> str | None:
    return momento.astimezone(LIMA).strftime("%d/%m/%Y") if momento else None


# Pólizas guardadas ya descifradas, por un rato: {id: (usuario, póliza, hasta cuándo sirve)}
_guardadas: dict[str, tuple[str, Poliza, float]] = {}


def poliza_guardada(poliza_id: str, cuenta: dict | None) -> Poliza:
    if cuenta is None:
        raise error(401, "sin_sesion", "Esa póliza está guardada en una cuenta: entra para usarla.")
    en_memoria = _guardadas.get(poliza_id)
    if en_memoria and en_memoria[0] == cuenta["usuario_id"] and en_memoria[2] > time.monotonic():
        return en_memoria[1]
    poliza = guardado.cargar_poliza(limites().motor, cuenta["usuario_id"], poliza_id)
    if poliza is None:
        _guardadas.pop(poliza_id, None)
        raise error(404, "poliza_no_encontrada", "Esa póliza guardada ya no existe: se borró o venció. Vuelve a subir tu PDF.")
    while len(_guardadas) >= 10:
        _guardadas.pop(next(iter(_guardadas)))
    _guardadas[poliza_id] = (cuenta["usuario_id"], poliza, time.monotonic() + 600)
    return poliza


def buscar_poliza(poliza_id: str, cuenta: dict | None = None) -> Poliza:
    if poliza_id in almacen.fuentes():
        return almacen.precargada(poliza_id)
    if poliza_id.startswith("g_"):
        return poliza_guardada(poliza_id, cuenta)
    poliza = subidas.obtener(poliza_id)
    if poliza is None:
        raise error(404, "poliza_no_encontrada", "Esa póliza ya no está en memoria. Vuelve a subir tu PDF.")
    return poliza


def resumen_poliza(poliza_id: str, poliza: Poliza) -> dict:
    return {
        "poliza_id": poliza_id,
        "nombre": poliza.nombre,
        "paginas": poliza.indice.meta.get("paginas"),
        "fragmentos": len(poliza.indice.trozos),
        "secciones": poliza.secciones,
        "archivos": [{"nombre": n, "paginas": p} for n, p in poliza.archivos],
        "busqueda": metodo_efectivo(poliza.indice),
        "documento_sha256": poliza.sha256,  # identifica el documento (p. ej., para saber de cuál fue la radiografía gratis)
        # Si el documento no parece un condicionado de seguro: un aviso, sin bloquear (ai/portero.py)
        "aviso_documento": (poliza.revision or {}).get("aviso"),
    }


# ---------------------------------------------------------------------------
# Estado
# ---------------------------------------------------------------------------


@app.get("/salud")
def salud() -> dict:
    return {"ok": True, "version": VERSION}


@app.get("/info")
def info() -> dict:
    """Lo que el cliente necesita decirle a la persona sobre el servicio."""
    p, lim = proveedor(), limites()
    return {
        "version": VERSION,
        "modelo": p.modelos["respuesta"],
        "proveedor": p.nombre,
        "aviso_proveedor": p.aviso,
        "embeddings": embeddings.modelo() if embeddings.disponible() else None,
        "registra_preguntas": observabilidad.activo(),
        "limite_consultas_dia": lim.limite_dispositivo,
        "limites": {plan: {"dia": lim.limite_de(plan), "polizas_guardadas": 0 if plan == "sin_cuenta" else pagos.polizas_permitidas(plan),
                           "dias_de_guardado": None if plan == "sin_cuenta" else pagos.dias_de_guardado(plan)}
                    for plan in ("sin_cuenta", "gratis", "pagado")},
        "plan_pagado": {"producto": pagos.PRODUCTO, "precio": pagos.PRECIO},
        "cuentas_disponibles": guardado.hay_llave(),
        "google_disponible": acceso_google.disponible(),
        "politica_privacidad": POLITICA,
        "sin_modelo_por_tope": lim.tope_global_alcanzado(),
    }


@app.get("/uso")
def uso(x_dispositivo: str | None = Header(default=None), authorization: str | None = Header(default=None)) -> dict:
    lim = limites()
    return estado_limites(lim, quien_es(x_dispositivo, authorization), lim.tope_global_alcanzado())


# ---------------------------------------------------------------------------
# Pólizas
# ---------------------------------------------------------------------------


@app.get("/polizas")
def polizas_de_ejemplo() -> list[dict]:
    return [
        {"poliza_id": doc_id, "aseguradora": f["aseguradora"], "producto": f["producto"],
         "ejemplos": almacen.ejemplos().get(doc_id, [])}
        for doc_id, f in almacen.fuentes().items()
    ]


@app.get("/polizas/{poliza_id}")
def ver_poliza(poliza_id: str, authorization: str | None = Header(default=None)) -> dict:
    return resumen_poliza(poliza_id, buscar_poliza(poliza_id, cuentas.de_sesion(limites().motor, token_de(authorization))))


@app.post("/polizas", status_code=201)
async def subir_poliza(request: Request, archivos: list[UploadFile] = File(...),
                       x_dispositivo: str | None = Header(default=None)) -> dict:
    dispositivo = dispositivo_valido(x_dispositivo)
    if not 1 <= len(archivos) <= MAX_ARCHIVOS:
        raise error(400, "demasiados_archivos", f"Sube entre 1 y {MAX_ARCHIVOS} archivos PDF.")
    pares = []
    for a in archivos:
        datos = await a.read()
        if len(datos) > MAX_BYTES:
            raise error(413, "archivo_grande", f"{a.filename}: supera los {MAX_BYTES // (1024 * 1024)} MB.")
        if not datos.startswith(b"%PDF"):
            raise error(400, "no_es_pdf", f"{a.filename}: no es un PDF.")
        pares.append((a.filename or "poliza.pdf", datos))
    lim = limites()
    if not lim.tomar("s" + clave_dispositivo(dispositivo), lim.limite_subidas):
        raise error(429, "limite_subidas", f"Llegaste al límite de {lim.limite_subidas} pólizas subidas por hoy.")
    try:
        poliza = await run_in_threadpool(subida.poliza_de_pdfs, pares)
    except subida.PolizaIlegible as e:
        raise error(422, "poliza_ilegible", str(e)) from e
    except Exception as e:  # noqa: BLE001 - PDF dañado o protegido
        raise error(422, "poliza_ilegible", "No pude leer ese PDF: puede estar dañado o protegido.") from e
    return resumen_poliza(subidas.guardar(poliza), poliza)


@app.delete("/polizas/{poliza_id}")
def borrar_poliza(poliza_id: str, x_dispositivo: str | None = Header(default=None), authorization: str | None = Header(default=None)) -> dict:
    if poliza_id in almacen.fuentes():
        raise error(400, "es_de_ejemplo", "Los condicionados de ejemplo no se borran.")
    if poliza_id.startswith("g_"):  # una póliza guardada: se borra de la base con todo su historial
        q = quien_es(x_dispositivo, authorization, exigir_cuenta=True)
        _guardadas.pop(poliza_id, None)
        return {"borrada": guardado.borrar_poliza(limites().motor, q.cuenta["usuario_id"], poliza_id)}
    return {"borrada": subidas.borrar(poliza_id)}


# ---------------------------------------------------------------------------
# Preguntar
# ---------------------------------------------------------------------------


class Aclaracion(BaseModel):
    pregunta: str = Field(max_length=300)
    respuesta: str = Field(max_length=500)


class Consulta(BaseModel):
    poliza_id: str = Field(min_length=1, max_length=200)
    pregunta: str = Field(min_length=3, max_length=1000)
    # Lo que la persona respondió a las repreguntas de una respuesta anterior con modo "aclaracion"
    aclaraciones: list[Aclaracion] = Field(default_factory=list, max_length=3)


def limpiar(r: dict) -> dict:
    """Al cliente va solo lo verificado: fuera la salida cruda del modelo y los descartes."""
    for clave in ("modelo_crudo", "descartes"):
        r.pop(clave, None)
    for sub in r.get("respuestas", []):
        limpiar(sub)
    return r


def cupo(request: Request, q: Quien) -> Limites:
    """Cuenta una consulta del día según el plan de quien pregunta, o responde 429. Sin cuenta,
    además, un techo por IP (el identificador de dispositivo lo genera el cliente)."""
    lim = limites()
    limite = lim.limite_de(q.plan)
    if not lim.tomar(q.clave, limite):
        raise error(429, "limite_cuenta" if q.cuenta else "limite_dispositivo",
                    f"Llegaste a tus {limite} consultas de hoy. Mañana se renuevan.", limite_dia=limite)
    if q.cuenta is None and not lim.tomar(clave_ip(ip_de(request)), lim.limite_ip):
        devolver_cupo(lim, q)
        raise error(429, "limite_red", "Desde esta red ya se hicieron demasiadas consultas hoy. Mañana se renueva.")
    return lim


def otra_consulta(lim: Limites, q: Quien) -> bool:
    """Una consulta más del mismo texto (varias preguntas): ¿queda cupo?"""
    return lim.tomar(q.clave, lim.limite_de(q.plan))


def devolver_cupo(lim: Limites, q: Quien) -> None:
    lim.devolver(q.clave)


def estado_limites(lim: Limites, q: Quien, por_tope: bool) -> dict:
    """Cuánto le queda hoy a quien pregunta."""
    dia = lim.limite_de(q.plan)
    return {"plan": q.plan, "limite_dia": dia, "restantes_hoy": max(0, dia - lim.usadas(q.clave)), "sin_modelo_por_tope": por_tope}


@app.post("/preguntar")
def preguntar(consulta: Consulta, request: Request, x_dispositivo: str | None = Header(default=None),
              authorization: str | None = Header(default=None)) -> dict:
    pregunta = consulta.pregunta.strip()
    q = quien_es(x_dispositivo, authorization)
    poliza = buscar_poliza(consulta.poliza_id, q.cuenta)
    lim = cupo(request, q)
    por_tope = lim.tope_global_alcanzado()
    quien = proveedor_por_tope() if por_tope else proveedor()
    tipo = "ejemplo" if consulta.poliza_id in almacen.fuentes() else "guardada" if consulta.poliza_id.startswith("g_") else "subida"
    with observabilidad.consulta(pregunta, poliza=consulta.poliza_id if tipo == "ejemplo" else tipo) as anotar:
        r = flujo.atender(pregunta, poliza, quien, [a.model_dump() for a in consulta.aclaraciones],
                          permitir_otra=lambda: otra_consulta(lim, q))
        costo = r["uso"]["costo_usd"]
        if r["modo"] == "aclaracion":  # todavía no se respondió nada: no gasta una consulta del día
            devolver_cupo(lim, q)
        respondidas = r.get("respuestas", [r])
        lim.registrar_gasto(costo, sin_modelo=any(x["modo"] == "solo_clausulas" for x in respondidas))
        anotar(modo=r["modo"], veredicto=[x.get("cubre") for x in respondidas], citas=sum(len(x.get("citas", [])) for x in respondidas),
               busqueda=metodo_efectivo(poliza.indice), costo_usd=costo, segundos=r["uso"]["segundos"],
               error=next((x.get("error") for x in respondidas if x.get("error")), None), por_tope=por_tope)
    limpiar(r)
    if tipo == "guardada" and r["modo"] != "aclaracion":  # historial: solo de pólizas guardadas en una cuenta
        r["consulta_id"] = guardado.guardar_consulta(lim.motor, q.cuenta["usuario_id"], consulta.poliza_id, r)
    return r | {"limites": estado_limites(lim, q, por_tope)}


# ---------------------------------------------------------------------------
# Qué hacer ahora, radiografía y superposiciones
# ---------------------------------------------------------------------------


class PedidoPasos(BaseModel):
    poliza_id: str = Field(min_length=1, max_length=200)
    situacion: str = Field(default="", max_length=1000)
    fecha_hecho: dt.date | None = None  # si no viene, se lee de la situación ("ayer", "el 12 de noviembre")


@app.post("/pasos")
def pasos_para_reclamar(pedido: PedidoPasos, request: Request, x_dispositivo: str | None = Header(default=None),
                        authorization: str | None = Header(default=None)) -> dict:
    if pedido.fecha_hecho and pedido.fecha_hecho > dt.date.today() + dt.timedelta(days=1):
        raise error(400, "fecha_futura", "La fecha del hecho no puede ser futura.")
    q = quien_es(x_dispositivo, authorization)
    poliza = buscar_poliza(pedido.poliza_id, q.cuenta)
    lim = cupo(request, q)
    por_tope = lim.tope_global_alcanzado()
    r = pasos.que_hacer(poliza, pedido.situacion.strip(), pedido.fecha_hecho, proveedor_por_tope() if por_tope else proveedor())
    lim.registrar_gasto(r["uso"]["costo_usd"], sin_modelo=r["modo"] != "pasos")
    return limpiar(r) | {"limites": estado_limites(lim, q, por_tope)}


_candado_radiografia = threading.Lock()


def radiografia_de(poliza_id: str, cuenta: dict | None = None) -> dict:
    """La radiografía de la póliza: la versionada si es un condicionado de ejemplo; si es una
    póliza subida, se genera una vez y queda en memoria junto con ella (y, si la póliza está
    guardada en una cuenta, cifrada con ella)."""
    poliza = buscar_poliza(poliza_id, cuenta)
    if poliza_id in almacen.fuentes():
        guardada = radiografia.guardada(poliza_id)
        if guardada is not None:
            return guardada
    with _candado_radiografia:
        hecha = getattr(poliza, "radiografia", None)
        if hecha is None:
            lim = limites()
            hecha = radiografia.generar(poliza, proveedor_por_tope() if lim.tope_global_alcanzado() else proveedor())
            lim.registrar_gasto(hecha["uso"]["costo_usd"], sin_modelo=hecha["modo"] != "radiografia")
            hecha.pop("descartes", None)
            if hecha["modo"] == "radiografia":  # si el modelo falló, se reintenta la próxima vez
                poliza.radiografia = hecha
                if poliza_id.startswith("g_") and cuenta:
                    guardado.actualizar_radiografia(lim.motor, cuenta["usuario_id"], poliza_id, hecha)
    return hecha


def clave_radiografia(poliza_id: str, poliza: Poliza) -> str:
    """Qué póliza es, para la radiografía gratis: el id si es de ejemplo; si no, la huella del
    documento (la misma al subirla y después de guardarla)."""
    return poliza_id if poliza_id in almacen.fuentes() else poliza.sha256


@app.get("/polizas/{poliza_id}/radiografia")
def ver_radiografia(poliza_id: str, x_dispositivo: str | None = Header(default=None),
                    authorization: str | None = Header(default=None)) -> dict:
    """Del plan pagado; cada cuenta gratis tiene una completa de muestra (backend/pagos.py)."""
    q = quien_es(x_dispositivo, authorization)
    poliza = buscar_poliza(poliza_id, q.cuenta)
    clave = clave_radiografia(poliza_id, poliza)
    acceso = pagos.acceso_radiografia(q.cuenta, clave)
    if acceso == "sin_cuenta":
        raise error(403, "radiografia_sin_cuenta", "Crea una cuenta gratis para ver una radiografía.", funcion="radiografia")
    if acceso == "bloqueada" or (acceso == "muestra" and not pagos.tomar_muestra(limites().motor, q.cuenta["usuario_id"], clave)):
        raise error(403, "plan_pagado", "Ya usaste tu radiografía gratis. Las demás son del plan pagado.", funcion="radiografia")
    r = radiografia_de(poliza_id, q.cuenta)
    if acceso == "muestra" and r["modo"] != "radiografia":  # no salió: la muestra gratis no se pierde
        pagos.soltar_muestra(limites().motor, q.cuenta["usuario_id"], clave)
    return r | {"acceso": "pagado" if acceso == "pagado" else "muestra"}


@app.get("/polizas/{poliza_id}/clinicas")
def clinicas_nombradas(poliza_id: str, authorization: str | None = Header(default=None)) -> dict:
    """Las clínicas que el condicionado nombra literalmente, cada una con su cita verificada.
    Sin modelo. Si no nombra ninguna, la lista va vacía y el cliente no muestra la sección."""
    poliza = buscar_poliza(poliza_id, cuentas.de_sesion(limites().motor, token_de(authorization)))
    halladas = getattr(poliza, "clinicas", None)
    if halladas is None:
        halladas = clinicas.nombradas(poliza)
        poliza.clinicas = halladas
    return {"clinicas": halladas,
            "aviso": "Tu póliza nombra estas clínicas. Que las nombre no dice para qué coberturas están en convenio: lee la cita."}


class PedidoSuperposicion(BaseModel):
    poliza_ids: list[str] = Field(min_length=2, max_length=4)


@app.post("/superposiciones")
def coberturas_superpuestas(pedido: PedidoSuperposicion, request: Request, x_dispositivo: str | None = Header(default=None),
                            authorization: str | None = Header(default=None)) -> dict:
    if len(set(pedido.poliza_ids)) != len(pedido.poliza_ids):
        raise error(400, "polizas_repetidas", "Elige pólizas distintas para comparar.")
    q = quien_es(x_dispositivo, authorization)
    if not pagos.puede_comparar(q.plan):
        raise error(403, "plan_pagado", "¿Pagas doble? es del plan pagado.", funcion="superposiciones")
    for poliza_id in pedido.poliza_ids:
        buscar_poliza(poliza_id, q.cuenta)
    lim = cupo(request, q)
    por_tope = lim.tope_global_alcanzado()
    pares = [(buscar_poliza(i, q.cuenta).nombre, radiografia_de(i, q.cuenta)) for i in pedido.poliza_ids]
    r = radiografia.superposiciones(pares, proveedor_por_tope() if por_tope else proveedor())
    lim.registrar_gasto(r.get("uso", {}).get("costo_usd", 0.0), sin_modelo=r["modo"] != "superposicion")
    return r | {"limites": estado_limites(lim, q, por_tope)}


# ---------------------------------------------------------------------------
# Cuentas, pólizas guardadas e historial
# ---------------------------------------------------------------------------

CONSENTIMIENTO = ("Acepto la política de privacidad y que se guarde el texto de mi póliza y mis consultas, que pueden incluir "
                  "datos de salud.")


class Registro(BaseModel):
    correo: str = Field(max_length=254)
    clave: str = Field(max_length=200)
    acepto_privacidad: bool = False  # la casilla no viene marcada: hay que aceptarla


class Credenciales(BaseModel):
    correo: str = Field(max_length=254)
    clave: str = Field(max_length=200)


class AccesoGoogle(BaseModel):
    id_token: str = Field(min_length=20, max_length=4096)
    acepto_privacidad: bool = False  # solo cuenta si la cuenta es nueva


class Confirmacion(BaseModel):
    clave: str = Field(default="", max_length=200)  # una cuenta que entra solo con Google no tiene contraseña


class Compra(BaseModel):
    token_compra: str = Field(min_length=1, max_length=4096)
    producto: str = Field(default=pagos.PRODUCTO, max_length=100)


def _intento(request: Request) -> None:
    lim = limites()
    if not lim.tomar("a" + clave_ip(ip_de(request)), 30):
        raise error(429, "demasiados_intentos", "Demasiados intentos desde esta red por hoy.")


def _cuentas_activas() -> None:
    if not guardado.hay_llave():
        raise error(503, "cuentas_no_disponibles", "Las cuentas todavía no están activadas en este servidor.")


def datos_de_cuenta(cuenta: dict) -> dict:
    lim = limites()
    guardadas = guardado.listar_polizas(lim.motor, cuenta["usuario_id"])
    for g in guardadas:
        g["borrado_automatico"] = fecha_lima(g["borrar_el"])
    plan = cuenta["plan"]
    radiografia_ = "pagado" if plan == "pagado" else "muestra_usada" if cuenta["radiografia_gratis"] else "muestra_disponible"
    return {"correo": cuenta["correo"], "plan": plan, "acceso": "google" if cuenta["con_google"] else "clave",
            "polizas_permitidas": pagos.polizas_permitidas(plan), "dias_de_guardado": pagos.dias_de_guardado(plan),
            "funciones": {"superposiciones": pagos.puede_comparar(plan), "radiografia": radiografia_,
                          "radiografia_gratis_de": cuenta["radiografia_gratis"]},
            "polizas": guardadas, "limites": estado_limites(lim, Quien(cuenta, None), lim.tope_global_alcanzado())}


@app.get("/cuenta/avisos")
def avisos_de_cuenta() -> dict:
    """Lo que el cliente muestra al crear una cuenta: la casilla (sin marcar) y el enlace a la política."""
    return {"consentimiento": CONSENTIMIENTO, "politica_privacidad": POLITICA, "disponible": guardado.hay_llave(),
            "google_disponible": acceso_google.disponible()}


@app.post("/cuenta/google")
def entrar_con_google(datos: AccesoGoogle, request: Request) -> dict:
    """Entra (o crea la cuenta, si aceptó la política) con el ID token de Google."""
    _intento(request)
    _cuentas_activas()
    limpiar_vencido()
    try:
        token, cuenta, nueva = cuentas.entrar_con_google(limites().motor, datos.id_token, datos.acepto_privacidad)
    except cuentas.ErrorCuenta as e:
        raise error(400 if e.codigo == "falta_consentimiento" else 401, e.codigo, str(e)) from e
    return {"token": token, "cuenta_nueva": nueva, "cuenta": datos_de_cuenta(cuenta)}


@app.post("/cuenta/registro", status_code=201)
def registrar_cuenta(datos: Registro, request: Request) -> dict:
    _intento(request)
    _cuentas_activas()
    try:
        token, cuenta = cuentas.registrar(limites().motor, datos.correo, datos.clave, datos.acepto_privacidad)
    except cuentas.ErrorCuenta as e:
        raise error(409 if e.codigo == "correo_en_uso" else 400, e.codigo, str(e)) from e
    return {"token": token, "cuenta": datos_de_cuenta(cuenta)}


@app.post("/cuenta/sesion")
def entrar_a_la_cuenta(datos: Credenciales, request: Request) -> dict:
    _intento(request)
    limpiar_vencido()
    try:
        token, cuenta = cuentas.entrar(limites().motor, datos.correo, datos.clave)
    except cuentas.ErrorCuenta as e:
        raise error(401, e.codigo, str(e)) from e
    return {"token": token, "cuenta": datos_de_cuenta(cuenta)}


@app.delete("/cuenta/sesion")
def salir_de_la_cuenta(authorization: str | None = Header(default=None)) -> dict:
    if token_de(authorization):
        cuentas.salir(limites().motor, token_de(authorization))
    return {"sesion_cerrada": True}


@app.get("/cuenta")
def ver_cuenta(authorization: str | None = Header(default=None)) -> dict:
    limpiar_vencido()
    return datos_de_cuenta(quien_es(None, authorization, exigir_cuenta=True).cuenta)


@app.post("/cuenta/compra")
def comprar_plan(compra: Compra, authorization: str | None = Header(default=None)) -> dict:
    """El pago único, comprado con Google Play Billing desde la app de Android. Hoy responde 501."""
    cuenta = quien_es(None, authorization, exigir_cuenta=True).cuenta
    if compra.producto != pagos.PRODUCTO:
        raise error(400, "producto_desconocido", "Ese producto no existe.")
    try:
        comprobante = pagos.verificar_compra(compra.token_compra, compra.producto)
    except pagos.CobroNoDisponible as e:
        raise error(501, "cobro_no_disponible", str(e)) from e
    except pagos.CompraInvalida as e:
        raise error(402, "compra_invalida", "Google Play no confirmó esa compra.") from e
    if not pagos.activar(limites().motor, cuenta["usuario_id"], comprobante):
        raise error(409, "compra_usada", "Esa compra ya activó otra cuenta.")
    return datos_de_cuenta(cuentas.de_sesion(limites().motor, token_de(authorization)))


@app.delete("/cuenta")
def borrar_cuenta(confirmacion: Confirmacion, authorization: str | None = Header(default=None)) -> dict:
    """Borra la cuenta y todo: pólizas guardadas, historial, sesiones y contadores. Una cuenta con
    contraseña la pide; una que entra solo con Google se confirma con su sesión."""
    cuenta = quien_es(None, authorization, exigir_cuenta=True).cuenta
    lim = limites()
    if cuenta["con_clave"] and not cuentas.clave_de(lim.motor, cuenta["usuario_id"], confirmacion.clave):
        raise error(401, "clave_incorrecta", "La contraseña no coincide: no borré nada.")
    for poliza_id in [k for k, v in _guardadas.items() if v[0] == cuenta["usuario_id"]]:
        _guardadas.pop(poliza_id, None)
    borrado = guardado.borrar_todo(lim.motor, cuenta["usuario_id"])
    lim.olvidar("u:" + cuenta["usuario_id"])
    return {"cuenta_borrada": True, "filas_borradas": borrado}


@app.post("/polizas/{poliza_id}/guardar", status_code=201)
def guardar_poliza(poliza_id: str, authorization: str | None = Header(default=None)) -> dict:
    """Guarda en la cuenta la póliza que se acaba de subir: su texto, sus vectores y el texto de
    cada página. El PDF no se guarda."""
    cuenta = quien_es(None, authorization, exigir_cuenta=True).cuenta
    if poliza_id in almacen.fuentes() or poliza_id.startswith("g_"):
        raise error(400, "no_se_guarda", "Solo se guarda una póliza que acabas de subir.")
    poliza = buscar_poliza(poliza_id)
    lim = limites()
    permitidas = pagos.polizas_permitidas(cuenta["plan"])
    if guardado.contar_polizas(lim.motor, cuenta["usuario_id"]) >= permitidas:
        plural = "s" if permitidas != 1 else ""
        raise error(409, "limite_polizas", f"Tu plan guarda {permitidas} póliza{plural}. Borra una para guardar otra.")
    try:
        g = guardado.guardar_poliza(lim.motor, cuenta["usuario_id"], poliza, pagos.dias_de_guardado(cuenta["plan"]),
                                    getattr(poliza, "radiografia", None))
    except guardado.SinLlave as e:
        raise error(503, "cuentas_no_disponibles", "El guardado todavía no está activado en este servidor.") from e
    dia = fecha_lima(g["borrar_el"])
    return g | {"borrado_automatico": dia, "aviso": f"Guardada · se borra el {dia}" if dia else "Guardada"}


@app.get("/polizas/{poliza_id}/consultas")
def historial(poliza_id: str, authorization: str | None = Header(default=None)) -> dict:
    cuenta = quien_es(None, authorization, exigir_cuenta=True).cuenta
    poliza_guardada(poliza_id, cuenta)
    return {"consultas": guardado.listar_consultas(limites().motor, cuenta["usuario_id"], poliza_id)}


@app.delete("/consultas/{consulta_id}")
def borrar_consulta(consulta_id: str, authorization: str | None = Header(default=None)) -> dict:
    cuenta = quien_es(None, authorization, exigir_cuenta=True).cuenta
    return {"borrada": guardado.borrar_consulta(limites().motor, cuenta["usuario_id"], consulta_id)}


# ---------------------------------------------------------------------------
# Mapa (RENIPRESS): sin modelo y sin ubicación de la persona
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def registro():
    return renipress.cargar()


@app.get("/mapa/departamentos")
def mapa_departamentos() -> list[dict]:
    return [{"id": d, "nombre": renipress.nombre_propio(d)} for d in sorted(registro()["departamento"].unique())]


@app.get("/mapa/distritos")
def mapa_distritos(departamento: str) -> list[dict]:
    return [{"provincia": p, "distrito": d, "nombre": renipress.nombre_propio(d),
             "nombre_provincia": renipress.nombre_propio(p)} for p, d in renipress.distritos(registro(), departamento)]


@lru_cache(maxsize=1)
def _con_internamiento() -> list:
    df = registro()
    con = df[df["tipo"].str.contains("CON INTERNAMIENTO")].dropna(subset=["lat", "lon"])
    return [[f.nombre, renipress.nombre_propio(f.clasificacion.split(",")[0]), round(float(f.lat), 5), round(float(f.lon), 5)]
            for f in con.itertuples()]


@app.get("/mapa/con-internamiento")
def mapa_con_internamiento() -> dict:
    """Hospitales y clínicas con internamiento de todo el país con coordenadas: [nombre, tipo,
    lat, lon]. El cliente calcula con esto lo más cercano sin enviar la ubicación a nadie."""
    return {"aviso": "Son establecimientos registrados en SUSALUD, no la red de tu aseguradora.",
            "fuente": renipress.fuente(), "establecimientos": _con_internamiento()}


@app.get("/mapa/establecimientos")
def mapa_establecimientos(departamento: str, provincia: str, distrito: str, solo_internamiento: bool = False) -> dict:
    sel = renipress.establecimientos(registro(), departamento, provincia, distrito)
    if solo_internamiento:
        sel = sel[sel["tipo"].str.contains("CON INTERNAMIENTO")]
    columnas = ["codigo", "nombre", "clasificacion", "tipo", "categoria", "direccion", "telefono", "horario",
                "institucion", "lat", "lon"]
    filas = sel[columnas].to_dict("records")
    for f in filas:
        for c in ("lat", "lon"):
            if isinstance(f[c], float) and math.isnan(f[c]):
                f[c] = None
    con_coordenadas = sel.dropna(subset=["lat", "lon"])
    if len(con_coordenadas) == 0:  # distrito sin coordenadas en el registro: el centro del departamento
        con_coordenadas = registro()[registro()["departamento"] == departamento].dropna(subset=["lat", "lon"])
    centro = ({"lat": round(float(con_coordenadas["lat"].median()), 5), "lon": round(float(con_coordenadas["lon"].median()), 5)}
              if len(con_coordenadas) else None)
    return {
        "centro": centro,
        "total": len(filas),
        "sin_coordenadas": sum(1 for f in filas if f["lat"] is None or f["lon"] is None),
        "aviso": "Son establecimientos registrados en SUSALUD, no la red de tu aseguradora.",
        "fuente": renipress.fuente(),
        "establecimientos": filas,
    }

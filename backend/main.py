"""API de ¿Qué me cubre?: el mismo pipeline de ai/ detrás de HTTP.

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
from ai.llm import ErrorLLM, LimiteAlcanzado, ProveedorNoDisponible, obtener_proveedor  # noqa: E402
from ai.recuperacion import metodo_efectivo  # noqa: E402
from ai.respuesta import Poliza, responder  # noqa: E402
from backend import almacen, observabilidad  # noqa: E402
from backend.limites import Limites, clave_dispositivo, clave_ip  # noqa: E402

VERSION = "1.1.0"
MAX_ARCHIVOS = 6
MAX_BYTES = 20 * 1024 * 1024  # por archivo
MultiPartParser.spool_max_size = MAX_BYTES + 1

subidas = almacen.Subidas()


@lru_cache(maxsize=1)
def limites() -> Limites:
    return Limites()


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
    yield
    observabilidad.cerrar()


app = FastAPI(title="¿Qué me cubre?", version=VERSION, lifespan=ciclo)


def error(status: int, codigo: str, mensaje: str, **extra) -> HTTPException:
    return HTTPException(status, {"codigo": codigo, "mensaje": mensaje, **extra})


def ip_de(request: Request) -> str:
    reenviada = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
    return reenviada or (request.client.host if request.client else "desconocida")


def dispositivo_valido(dispositivo: str | None) -> str:
    if not dispositivo or not (8 <= len(dispositivo) <= 100):
        raise error(400, "falta_dispositivo", "Falta el encabezado X-Dispositivo (entre 8 y 100 caracteres).")
    return dispositivo


def buscar_poliza(poliza_id: str) -> Poliza:
    if poliza_id in almacen.fuentes():
        return almacen.precargada(poliza_id)
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
        "sin_modelo_por_tope": lim.tope_global_alcanzado(),
    }


@app.get("/uso")
def uso(x_dispositivo: str | None = Header(default=None)) -> dict:
    lim = limites()
    usadas = lim.usadas(clave_dispositivo(dispositivo_valido(x_dispositivo)))
    return {"limite_dia": lim.limite_dispositivo, "usadas_hoy": usadas,
            "restantes_hoy": max(0, lim.limite_dispositivo - usadas), "sin_modelo_por_tope": lim.tope_global_alcanzado()}


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
def ver_poliza(poliza_id: str) -> dict:
    return resumen_poliza(poliza_id, buscar_poliza(poliza_id))


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
def borrar_poliza(poliza_id: str) -> dict:
    if poliza_id in almacen.fuentes():
        raise error(400, "es_de_ejemplo", "Los condicionados de ejemplo no se borran.")
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


def cupo(request: Request, x_dispositivo: str | None) -> tuple[Limites, str]:
    """Cuenta una consulta para el dispositivo y para la IP, o responde 429."""
    dispositivo = clave_dispositivo(dispositivo_valido(x_dispositivo))
    lim = limites()
    if not lim.tomar(dispositivo, lim.limite_dispositivo):
        raise error(429, "limite_dispositivo",
                    f"Llegaste al límite de {lim.limite_dispositivo} consultas por hoy. Mañana se renueva.",
                    limite_dia=lim.limite_dispositivo)
    if not lim.tomar(clave_ip(ip_de(request)), lim.limite_ip):
        lim.devolver(dispositivo)
        raise error(429, "limite_red", "Desde esta red ya se hicieron demasiadas consultas hoy. Mañana se renueva.")
    return lim, dispositivo


def estado_limites(lim: Limites, dispositivo: str, por_tope: bool) -> dict:
    return {"limite_dia": lim.limite_dispositivo, "restantes_hoy": max(0, lim.limite_dispositivo - lim.usadas(dispositivo)),
            "sin_modelo_por_tope": por_tope}


@app.post("/preguntar")
def preguntar(consulta: Consulta, request: Request, x_dispositivo: str | None = Header(default=None)) -> dict:
    pregunta = consulta.pregunta.strip()
    poliza = buscar_poliza(consulta.poliza_id)
    lim, dispositivo = cupo(request, x_dispositivo)
    por_tope = lim.tope_global_alcanzado()
    quien = proveedor_por_tope() if por_tope else proveedor()
    tipo = "ejemplo" if consulta.poliza_id in almacen.fuentes() else "subida"
    with observabilidad.consulta(pregunta, poliza=consulta.poliza_id if tipo == "ejemplo" else "subida") as anotar:
        r = flujo.atender(pregunta, poliza, quien, [a.model_dump() for a in consulta.aclaraciones],
                          permitir_otra=lambda: lim.tomar(dispositivo, lim.limite_dispositivo))
        costo = r["uso"]["costo_usd"]
        if r["modo"] == "aclaracion":  # todavía no se respondió nada: no gasta una consulta del día
            lim.devolver(dispositivo)
        respondidas = r.get("respuestas", [r])
        lim.registrar_gasto(costo, sin_modelo=any(x["modo"] == "solo_clausulas" for x in respondidas))
        anotar(modo=r["modo"], veredicto=[x.get("cubre") for x in respondidas], citas=sum(len(x.get("citas", [])) for x in respondidas),
               busqueda=metodo_efectivo(poliza.indice), costo_usd=costo, segundos=r["uso"]["segundos"],
               error=next((x.get("error") for x in respondidas if x.get("error")), None), por_tope=por_tope)
    return limpiar(r) | {"limites": estado_limites(lim, dispositivo, por_tope)}


# ---------------------------------------------------------------------------
# Qué hacer ahora, radiografía y superposiciones
# ---------------------------------------------------------------------------


class PedidoPasos(BaseModel):
    poliza_id: str = Field(min_length=1, max_length=200)
    situacion: str = Field(default="", max_length=1000)
    fecha_hecho: dt.date | None = None  # si no viene, se lee de la situación ("ayer", "el 12 de noviembre")


@app.post("/pasos")
def pasos_para_reclamar(pedido: PedidoPasos, request: Request, x_dispositivo: str | None = Header(default=None)) -> dict:
    if pedido.fecha_hecho and pedido.fecha_hecho > dt.date.today() + dt.timedelta(days=1):
        raise error(400, "fecha_futura", "La fecha del hecho no puede ser futura.")
    poliza = buscar_poliza(pedido.poliza_id)
    lim, dispositivo = cupo(request, x_dispositivo)
    por_tope = lim.tope_global_alcanzado()
    r = pasos.que_hacer(poliza, pedido.situacion.strip(), pedido.fecha_hecho, proveedor_por_tope() if por_tope else proveedor())
    lim.registrar_gasto(r["uso"]["costo_usd"], sin_modelo=r["modo"] != "pasos")
    return limpiar(r) | {"limites": estado_limites(lim, dispositivo, por_tope)}


_candado_radiografia = threading.Lock()


def radiografia_de(poliza_id: str) -> dict:
    """La radiografía de la póliza: la versionada si es un condicionado de ejemplo; si es una
    póliza subida, se genera una vez y queda en memoria junto con ella."""
    poliza = buscar_poliza(poliza_id)
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
    return hecha


@app.get("/polizas/{poliza_id}/radiografia")
def ver_radiografia(poliza_id: str, x_dispositivo: str | None = Header(default=None)) -> dict:
    dispositivo_valido(x_dispositivo)
    return radiografia_de(poliza_id)


@app.get("/polizas/{poliza_id}/clinicas")
def clinicas_nombradas(poliza_id: str) -> dict:
    """Las clínicas que el condicionado nombra literalmente, cada una con su cita verificada.
    Sin modelo. Si no nombra ninguna, la lista va vacía y el cliente no muestra la sección."""
    poliza = buscar_poliza(poliza_id)
    halladas = getattr(poliza, "clinicas", None)
    if halladas is None:
        halladas = clinicas.nombradas(poliza)
        poliza.clinicas = halladas
    return {"clinicas": halladas,
            "aviso": "Tu póliza nombra estas clínicas. Que las nombre no dice para qué coberturas están en convenio: lee la cita."}


class PedidoSuperposicion(BaseModel):
    poliza_ids: list[str] = Field(min_length=2, max_length=4)


@app.post("/superposiciones")
def coberturas_superpuestas(pedido: PedidoSuperposicion, request: Request, x_dispositivo: str | None = Header(default=None)) -> dict:
    if len(set(pedido.poliza_ids)) != len(pedido.poliza_ids):
        raise error(400, "polizas_repetidas", "Elige pólizas distintas para comparar.")
    for poliza_id in pedido.poliza_ids:
        buscar_poliza(poliza_id)
    lim, dispositivo = cupo(request, x_dispositivo)
    por_tope = lim.tope_global_alcanzado()
    pares = [(buscar_poliza(i).nombre, radiografia_de(i)) for i in pedido.poliza_ids]
    r = radiografia.superposiciones(pares, proveedor_por_tope() if por_tope else proveedor())
    lim.registrar_gasto(r.get("uso", {}).get("costo_usd", 0.0), sin_modelo=r["modo"] != "superposicion")
    return r | {"limites": estado_limites(lim, dispositivo, por_tope)}


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

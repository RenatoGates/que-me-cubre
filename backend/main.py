"""API de ¿Qué me cubre?: el mismo pipeline de ai/ detrás de HTTP.

    uvicorn backend.main:app --reload

Endpoints: subir uno o varios PDF, preguntar, borrar la póliza subida y el mapa de
RENIPRESS. El cliente manda en X-Dispositivo un identificador que él mismo genera.

Privacidad: el PDF subido vive solo en memoria (backend/almacen.py); se sube el umbral con
el que Starlette pasa un archivo a disco temporal para que tampoco toque el disco al llegar.
Al cliente va solo lo verificado: se quitan la salida cruda del modelo y los descartes.
"""

from __future__ import annotations

import math
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI, File, Header, HTTPException, Request, UploadFile  # noqa: E402
from fastapi.concurrency import run_in_threadpool  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402
from starlette.formparsers import MultiPartParser  # noqa: E402

from ai import embeddings, renipress, subida  # noqa: E402
from ai.llm import ErrorLLM, LimiteAlcanzado, ProveedorNoDisponible, obtener_proveedor  # noqa: E402
from ai.recuperacion import metodo_efectivo  # noqa: E402
from ai.respuesta import Poliza, responder  # noqa: E402
from backend import almacen, observabilidad  # noqa: E402
from backend.limites import Limites, clave_dispositivo, clave_ip  # noqa: E402

VERSION = "1.0.0"
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


class Consulta(BaseModel):
    poliza_id: str = Field(min_length=1, max_length=200)
    pregunta: str = Field(min_length=3, max_length=1000)


@app.post("/preguntar")
def preguntar(consulta: Consulta, request: Request, x_dispositivo: str | None = Header(default=None)) -> dict:
    dispositivo = clave_dispositivo(dispositivo_valido(x_dispositivo))
    pregunta = consulta.pregunta.strip()
    poliza = buscar_poliza(consulta.poliza_id)
    lim = limites()
    if not lim.tomar(dispositivo, lim.limite_dispositivo):
        raise error(429, "limite_dispositivo",
                    f"Llegaste al límite de {lim.limite_dispositivo} consultas por hoy. Mañana se renueva.",
                    limite_dia=lim.limite_dispositivo)
    ip = clave_ip(ip_de(request))
    if not lim.tomar(ip, lim.limite_ip):
        lim.devolver(dispositivo)
        raise error(429, "limite_red", "Desde esta red ya se hicieron demasiadas consultas hoy. Mañana se renueva.")

    por_tope = lim.tope_global_alcanzado()
    quien = proveedor_por_tope() if por_tope else proveedor()
    tipo = "ejemplo" if consulta.poliza_id in almacen.fuentes() else "subida"
    with observabilidad.consulta(pregunta, poliza=consulta.poliza_id if tipo == "ejemplo" else "subida") as anotar:
        r = responder(pregunta, poliza, quien)
        costo = r["uso"]["costo_usd"]
        lim.registrar_gasto(costo, sin_modelo=r["modo"] != "completo")
        anotar(modo=r["modo"], veredicto=r["cubre"], citas=len(r["citas"]), busqueda=metodo_efectivo(poliza.indice),
               costo_usd=costo, segundos=r["uso"]["segundos"], error=r.get("error"), por_tope=por_tope)

    for clave in ("modelo_crudo", "descartes"):
        r.pop(clave, None)
    r["limites"] = {"limite_dia": lim.limite_dispositivo,
                    "restantes_hoy": max(0, lim.limite_dispositivo - lim.usadas(dispositivo)),
                    "sin_modelo_por_tope": por_tope}
    return r


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
    return {
        "total": len(filas),
        "sin_coordenadas": sum(1 for f in filas if f["lat"] is None or f["lon"] is None),
        "aviso": "Son establecimientos registrados en SUSALUD, no la red de tu aseguradora.",
        "fuente": renipress.fuente(),
        "establecimientos": filas,
    }

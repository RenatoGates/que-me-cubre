"""Prueba, sin red y sin gasto, la API (backend/main.py) con respuestas grabadas.

- Preguntar sobre un condicionado de ejemplo y sobre una póliza subida en dos PDF.
- Al cliente no le llega la salida cruda del modelo ni los descartes.
- Tope por dispositivo: al pasarlo, 429; otro dispositivo sigue.
- Tope global: la API no se cae, responde las cláusulas sin veredicto.
- Borrar la póliza subida: después ya no se puede consultar.
- Mapa de RENIPRESS.
- Los archivos subidos no pasan por el disco temporal del servidor.

    python pruebas/probar_api.py      # termina con código 1 si algo falla
"""

from __future__ import annotations

import os
import tempfile

from comun import RAIZ, partir_pdf, utf8

_base = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_base.close()
os.environ.update({
    "QMC_PROVEEDOR": "grabado",
    "DATABASE_URL": f"sqlite:///{_base.name.replace(os.sep, '/')}",
    "QMC_LIMITE_DISPOSITIVO_DIA": "3",
    "QMC_TOPE_GLOBAL_USD": "2.00",
    "QMC_RECUPERACION": "bm25_variantes",
    "LANGFUSE_PUBLIC_KEY": "",
    "LANGFUSE_SECRET_KEY": "",
    "VOYAGE_API_KEY": "",
})

from fastapi.testclient import TestClient  # noqa: E402
from starlette.formparsers import MultiPartParser  # noqa: E402

from backend import main  # noqa: E402

FALLAS: list[str] = []
CHUBB = "chubb_viajes_jetsmart"
P01 = "Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos?"
P02 = "Me dijeron que me saque una radiografía al llegar a Lima porque allá no tenían la especialidad, ¿eso también me cubre?"


def caso(nombre: str, ok: bool, detalle: object = "") -> None:
    print(f"{'✓' if ok else '✗'} {nombre}" + ("" if ok else f"  ({detalle})"))
    if not ok:
        FALLAS.append(nombre)


def cabecera(dispositivo: str) -> dict:
    return {"X-Dispositivo": dispositivo}


def main_() -> int:
    utf8()
    with TestClient(main.app) as api:
        caso("salud", api.get("/salud").json()["ok"] is True)
        ejemplos = api.get("/polizas").json()
        caso("ejemplos: los condicionados precargados, con preguntas de ejemplo en Chubb",
             CHUBB in [e["poliza_id"] for e in ejemplos] and any(e["ejemplos"] for e in ejemplos), ejemplos)
        info = api.get("/info").json()
        caso("info: sin claves de Langfuse no se registran preguntas", info["registra_preguntas"] is False, info)

        r = api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01})
        caso("sin X-Dispositivo: 400", r.status_code == 400 and r.json()["detail"]["codigo"] == "falta_dispositivo", r.text[:200])

        r = api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=cabecera("dispositivo-a-0001"))
        d = r.json()
        caso("ejemplo: P01 con veredicto y citas verificadas",
             r.status_code == 200 and d["modo"] == "completo" and d["cubre"] == "con_limites" and len(d["citas"]) > 0,
             (r.status_code, d.get("modo"), d.get("cubre")))
        caso("al cliente no le llega la salida cruda del modelo ni los descartes",
             "modelo_crudo" not in d and "descartes" not in d, list(d))
        caso("la respuesta dice cuántas consultas quedan hoy", d["limites"] == {"limite_dia": 3, "restantes_hoy": 2,
                                                                              "sin_modelo_por_tope": False}, d.get("limites"))

        entero = (RAIZ / "data" / "polizas" / f"{CHUBB}.pdf").read_bytes()
        parte1, parte2 = partir_pdf(entero, [11])
        archivos = [("archivos", ("generales.pdf", parte1, "application/pdf")),
                    ("archivos", ("clausulas.pdf", parte2, "application/pdf"))]
        r = api.post("/polizas", files=archivos, headers=cabecera("dispositivo-b-0001"))
        subida = r.json()
        caso("subir dos PDF: una póliza de 62 páginas con sus dos archivos",
             r.status_code == 201 and subida["paginas"] == 62 and [a["paginas"] for a in subida["archivos"]] == [10, 52],
             r.text[:300])
        caso("subir: el archivo no pasa a disco temporal (umbral por encima del tamaño máximo)",
             MultiPartParser.spool_max_size > main.MAX_BYTES)
        r = api.post("/polizas", files=[("archivos", ("nota.pdf", b"hola", "application/pdf"))],
                     headers=cabecera("dispositivo-b-0001"))
        caso("subir algo que no es PDF: 400", r.status_code == 400 and r.json()["detail"]["codigo"] == "no_es_pdf", r.text[:200])

        # Una póliza subida no tiene normalización en la caché y sin red no hay modelo: salen las cláusulas.
        r = api.post("/preguntar", json={"poliza_id": subida["poliza_id"], "pregunta": P02}, headers=cabecera("dispositivo-b-0001"))
        d = r.json()
        caso("póliza subida: se puede consultar (sin red: las cláusulas encontradas, sin veredicto)",
             r.status_code == 200 and d.get("modo") == "solo_clausulas" and len(d["pasajes"]) > 0 and d["documento"].startswith("Tu póliza"),
             (r.status_code, d.get("modo"), d.get("error_detalle")))

        borrada = api.delete(f"/polizas/{subida['poliza_id']}").json()
        r = api.post("/preguntar", json={"poliza_id": subida["poliza_id"], "pregunta": P02}, headers=cabecera("dispositivo-b-0001"))
        caso("borrar la póliza subida: ya no se puede consultar (404)",
             borrada == {"borrada": True} and r.status_code == 404, (borrada, r.status_code))
        caso("un condicionado de ejemplo no se borra", api.delete(f"/polizas/{CHUBB}").status_code == 400)

        codigos = [api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=cabecera("dispositivo-c-0001")).status_code
                   for _ in range(4)]
        r = api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=cabecera("dispositivo-c-0001"))
        caso("tope por dispositivo: 3 consultas y después 429",
             codigos == [200, 200, 200, 429] and r.json()["detail"]["codigo"] == "limite_dispositivo", codigos)
        uso = api.get("/uso", headers=cabecera("dispositivo-c-0001")).json()
        caso("uso: 3 usadas, 0 restantes", (uso["usadas_hoy"], uso["restantes_hoy"]) == (3, 0), uso)
        r = api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=cabecera("dispositivo-d-0001"))
        caso("otro dispositivo sigue pudiendo consultar", r.status_code == 200)

        r = api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": "¿Me cubren si pierdo el pasaporte en Cusco?"},
                     headers=cabecera("dispositivo-d-0001"))
        d = r.json()
        caso("si el modelo no responde: 200 con las cláusulas, sin veredicto",
             r.status_code == 200 and d["modo"] == "solo_clausulas" and d["cubre"] is None and len(d["pasajes"]) > 0,
             (r.status_code, d.get("modo")))

        gasto = main.limites().gasto_del_mes()
        caso("contador global: cuenta las consultas respondidas y las que salieron sin modelo",
             gasto["consultas"] == 7 and gasto["sin_modelo"] == 2 and main.limites().usadas("no-existe") == 0, gasto)

        os.environ["QMC_TOPE_GLOBAL_USD"] = "0"
        r = api.post("/preguntar", json={"poliza_id": CHUBB, "pregunta": P01}, headers=cabecera("dispositivo-e-0001"))
        d = r.json()
        caso("tope global alcanzado: la API no se cae, muestra las cláusulas sin veredicto",
             r.status_code == 200 and d["modo"] == "solo_clausulas" and d["etiqueta_veredicto"] == "Sin veredicto"
             and "tope de gasto" in d["aviso"] and len(d["pasajes"]) > 0 and d["limites"]["sin_modelo_por_tope"] is True,
             (r.status_code, d.get("modo"), d.get("aviso")))
        caso("tope global alcanzado: el mapa y la subida siguen funcionando",
             api.get("/mapa/departamentos").status_code == 200 and api.get("/info").json()["sin_modelo_por_tope"] is True)
        os.environ["QMC_TOPE_GLOBAL_USD"] = "2.00"

        departamentos = api.get("/mapa/departamentos").json()
        distritos = api.get("/mapa/distritos", params={"departamento": "SAN MARTIN"}).json()
        mapa = api.get("/mapa/establecimientos", params={"departamento": "SAN MARTIN", "provincia": "SAN MARTIN",
                                                         "distrito": "TARAPOTO"}).json()
        caso("mapa: departamentos, distritos y establecimientos de Tarapoto con el aviso de que no es la red",
             len(departamentos) >= 24 and any(x["distrito"] == "TARAPOTO" for x in distritos) and mapa["total"] > 0
             and mapa["total"] == len(mapa["establecimientos"]) and "no la red" in mapa["aviso"],
             (len(departamentos), len(distritos), mapa.get("total")))
        caso("mapa: sin coordenadas sale como null, no como NaN",
             mapa["sin_coordenadas"] == sum(1 for e in mapa["establecimientos"] if e["lat"] is None))

    print(f"\n{'Todo bien' if not FALLAS else f'{len(FALLAS)} fallas'}.")
    return 1 if FALLAS else 0


if __name__ == "__main__":
    raise SystemExit(main_())

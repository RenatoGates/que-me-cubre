"""Prueba, sin red y sin gasto, el portero de documento, la reparación de PDF, las clínicas
nombradas en el condicionado y lo que el mapa promete sobre la ubicación.

- Portero: los condicionados precargados parecen póliza; un PDF de otra cosa recibe el aviso
  y se puede consultar igual (no se bloquea).
- Reparar: un PDF que pdfplumber no abre se reescribe; uno ilegible se rechaza con un mensaje.
  Si está en data/privado/ la póliza dental real que motivó el arreglo, se comprueba con ella.
- Clínicas nombradas: en un PDF de prueba que nombra clínicas salen con su cita verificada y
  su página; las frases genéricas ("la clínica u hospital de LA COMPAÑÍA") no cuentan; en
  los cinco condicionados precargados no hay ninguna, así que no se muestra nada.
- Mapa: la etiqueta permanente está escrita tal cual, la plantilla no guarda nada en el
  navegador y solo habla con OpenStreetMap (nunca con el servidor de la app).

    python pruebas/probar_mapa_portero.py      # termina con código 1 si algo falla
"""

from __future__ import annotations

import io
import os
import re
import tempfile

from comun import RAIZ, fuentes, poliza, utf8

_base = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_base.close()
os.environ.update({"QMC_PROVEEDOR": "grabado", "DATABASE_URL": f"sqlite:///{_base.name.replace(os.sep, '/')}",
                   "LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": "", "VOYAGE_API_KEY": ""})

from fastapi.testclient import TestClient  # noqa: E402

from ai import clinicas, portero, subida  # noqa: E402
from backend import main  # noqa: E402

FALLAS: list[str] = []
ETIQUETA = "Estos son centros de salud cercanos. NO verificamos si están en la red de tu póliza."


def caso(nombre: str, ok: bool, detalle: object = "") -> None:
    print(f"{'✓' if ok else '✗'} {nombre}" + ("" if ok else f"  ({detalle})"))
    if not ok:
        FALLAS.append(nombre)


def pdf_de(parrafos: list[str]) -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    estilo = getSampleStyleSheet()["BodyText"]
    salida = io.BytesIO()
    SimpleDocTemplate(salida, pagesize=A4).build(
        [Paragraph(p.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"), estilo) for p in parrafos])
    return salida.getvalue()


RECETAS = [f"Receta {i}: Para preparar el arroz con pollo se sofríe la cebolla con el ajo y el ají amarillo, se agrega el culantro "
           "licuado y el caldo, y se cocina a fuego lento hasta que el grano esté en su punto. Se sirve con salsa criolla."
           for i in range(1, 25)]
CON_CLINICAS = [
    "CONDICIONES GENERALES DEL SEGURO DE SALUD DE PRUEBA",
    "Artículo 1° Riesgos Cubiertos. La Compañía cubre los gastos médicos por Accidente del Asegurado dentro de la vigencia de la Póliza, "
    "previa aplicación del deducible y hasta la suma asegurada, con las exclusiones de este condicionado.",
    "Artículo 2° Red de Atención. El Asegurado podrá atenderse al crédito en la Clínica San Pablo y en el Hospital Dos de Mayo. "
    "Para emergencias también atiende la clínica Ricardo Palma.",
    "Artículo 3° Reembolso. Si el Asegurado se atiende en una clínica u hospital que no pertenece a la red de LA COMPAÑÍA, "
    "deberá dar aviso del siniestro dentro de los siete (7) días y presentar los comprobantes en clínicas y hospitales del Perú.",
]


def main_() -> int:
    utf8()

    # --- Portero ---
    medidas = {doc_id: portero.revisar_trozos(poliza(doc_id).indice.trozos) for doc_id in fuentes()}
    caso("portero: los cinco condicionados precargados parecen póliza",
         all(m["parece_poliza"] and m["aviso"] is None for m in medidas.values()), {k: v["densidad"] for k, v in medidas.items()})
    recetas = subida.poliza_de_pdfs([("recetas.pdf", pdf_de(RECETAS))])
    caso("portero: un PDF de recetas recibe el aviso, con el texto acordado",
         recetas.revision["parece_poliza"] is False and recetas.revision["aviso"] ==
         "Esto no parece un condicionado de seguro. Puedo intentarlo igual, pero las respuestas pueden no tener sentido.", recetas.revision)
    caso("portero: un texto que solo repite una palabra de póliza no pasa por densidad",
         portero.revisar("póliza " * 300)["parece_poliza"] is False)

    # --- Reparar ---
    bueno = pdf_de(CON_CLINICAS)
    caso("reparar: un PDF que ya se lee queda igual, byte por byte", subida.reparar(bueno) == bueno)
    try:
        subida.reparar(b"%PDF-1.4 esto no es un PDF de verdad")
        caso("reparar: un PDF ilegible se rechaza con un mensaje claro", False, "no falló")
    except subida.PolizaIlegible as e:
        caso("reparar: un PDF ilegible se rechaza con un mensaje claro", "dañado o protegido" in str(e), str(e))
    dental = RAIZ / "data" / "privado" / "seguro_dental_personal.pdf"
    if dental.exists():  # solo en la máquina del dueño: el archivo no está en el repositorio
        import pdfplumber

        crudo = dental.read_bytes()
        try:
            with pdfplumber.open(io.BytesIO(crudo)) as abierto:
                abre_tal_cual = len(abierto.pages) > 0
        except Exception:  # noqa: BLE001
            abre_tal_cual = False
        reparado = subida.reparar(crudo)
        with pdfplumber.open(io.BytesIO(reparado)) as abierto:
            paginas = len(abierto.pages)
        caso("reparar: la póliza dental real, que pdfplumber no abría, se lee entera tras reescribirla",
             not abre_tal_cual and reparado != crudo and paginas == 18, (abre_tal_cual, paginas))
    else:
        print("– reparar: sin la póliza dental privada en data/privado/, ese caso no se corre aquí")

    # --- Clínicas nombradas ---
    con = subida.poliza_de_pdfs([("salud.pdf", bueno)])
    halladas = clinicas.nombradas(con)
    nombres = [c["nombre"] for c in halladas]
    caso("clínicas: salen las tres que el PDF nombra y ninguna frase genérica",
         nombres == ["Clínica San Pablo", "Hospital Dos de Mayo", "clínica Ricardo Palma"], nombres)
    caso("clínicas: cada una trae su cita literal, su página y la verificación contra el PDF",
         all(c["nombre"].split(" ", 1)[1] in c["cita"] and c["pagina"] == 1 and c["verificacion"]["pdfplumber"] and c["verificacion"]["pypdf"]
             and c["cita"] in " ".join(t.texto for t in con.indice.trozos) for c in halladas), halladas[:1])
    caso("clínicas: el PDF de prueba con vocabulario de póliza no recibe el aviso del portero", con.revision["parece_poliza"], con.revision)
    sin = {doc_id: [c["nombre"] for c in clinicas.nombradas(poliza(doc_id))] for doc_id in fuentes()}
    caso("clínicas: ninguno de los cinco condicionados precargados nombra una clínica (no se muestra la sección)",
         all(not v for v in sin.values()), sin)

    # --- API ---
    with TestClient(main.app) as api:
        d = {"X-Dispositivo": "mapa-portero-0001"}
        r = api.post("/polizas", files=[("archivos", ("recetas.pdf", pdf_de(RECETAS), "application/pdf"))], headers=d)
        subida_ = r.json()
        caso("API: subir algo que no es una póliza no se bloquea, pero devuelve el aviso",
             r.status_code == 201 and subida_["aviso_documento"] == portero.AVISO, r.text[:200])
        r = api.post("/preguntar", json={"poliza_id": subida_["poliza_id"], "pregunta": "¿Me cubre una torcedura de tobillo?"}, headers=d)
        caso("API: y se puede preguntar igual", r.status_code == 200 and r.json()["modo"] in ("solo_clausulas", "completo", "aclaracion"), r.status_code)
        r = api.post("/polizas", files=[("archivos", ("salud.pdf", bueno, "application/pdf"))], headers=d).json()
        caso("API: una póliza no trae aviso", r["aviso_documento"] is None, r.get("aviso_documento"))
        nombradas = api.get(f"/polizas/{r['poliza_id']}/clinicas").json()
        caso("API: /clinicas devuelve las nombradas con su cita", [c["nombre"] for c in nombradas["clinicas"]] == nombres and "coberturas" in nombradas["aviso"])
        caso("API: /clinicas de un condicionado que no nombra ninguna va vacío", api.get("/polizas/chubb_viajes_jetsmart/clinicas").json()["clinicas"] == [])
        mapa = api.get("/mapa/establecimientos", params={"departamento": "SAN MARTIN", "provincia": "SAN MARTIN", "distrito": "TARAPOTO"}).json()
        caso("API: el mapa da el centro del distrito elegido (Tarapoto)",
             mapa["centro"] is not None and -6.6 < mapa["centro"]["lat"] < -6.4 and -76.5 < mapa["centro"]["lon"] < -76.3, mapa.get("centro"))

    # --- Plantilla del mapa: lo que promete sobre la ubicación ---
    plantilla = (RAIZ / "app" / "mapa_cercano.html").read_text(encoding="utf-8")
    app = (RAIZ / "app" / "app.py").read_text(encoding="utf-8")
    caso("mapa: la etiqueta permanente está escrita tal cual", f'<div id="etiqueta">{ETIQUETA}</div>' in plantilla)
    caso("mapa: no guarda nada en el navegador (ni almacenamiento ni cookies)",
         not re.search(r"localStorage|sessionStorage|indexedDB|document\.cookie", plantilla))
    servidores = set(re.findall(r"https://([a-z0-9.-]+)", plantilla))
    permitidos = {"unpkg.com", "tile.openstreetmap.org", "overpass-api.de", "overpass.private.coffee", "overpass.kumi.systems"}
    caso("mapa: la plantilla solo habla con OpenStreetMap y con la librería del mapa, nunca con el servidor de la app",
         servidores <= permitidos and "QMC_API_URL" not in plantilla and "onrender" not in plantilla, servidores - permitidos)
    caso("mapa: pide la ubicación solo al tocar el botón y, si se niega, sigue con el distrito",
         plantilla.count("getCurrentPosition") == 1 and 'el("ubicar").addEventListener("click"' in plantilla
         and "elige tu distrito arriba y sigo con eso" in plantilla)
    caso("mapa: Streamlit le pasa el centro del distrito, no recibe coordenadas de vuelta",
         "components.html(" in app and "declare_component" not in app and "geolocation" not in app)

    print(f"\n{'Todo bien' if not FALLAS else f'{len(FALLAS)} fallas'}.")
    return 1 if FALLAS else 0


if __name__ == "__main__":
    raise SystemExit(main_())

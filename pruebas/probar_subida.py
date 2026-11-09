"""Prueba, sin red y sin cuota, la subida de una póliza en varios PDF (ai/subida.py) y el aviso de
avance de responder().

- Una póliza partida en dos PDF se indexa igual que entera: mismos trozos, mismo texto.
- Cada página de corrido se traduce a su archivo y a su página dentro de él, también cuando
  un pasaje cruza de un archivo al otro.
- Las citas se verifican contra el PDF unido: una frase de la segunda parte está en su página.
- Un archivo escaneado (sin texto) se rechaza diciendo cuál es.
- responder() avisa cada paso (buscar, redactar, verificar) para que la app lo muestre.

    python pruebas/probar_subida.py      # termina con código 1 si algo falla
"""

from __future__ import annotations

import io
import os

from comun import RAIZ, partir_pdf, poliza, utf8

os.environ["QMC_PROVEEDOR"] = "grabado"

from pypdf import PdfWriter  # noqa: E402

from ai import subida  # noqa: E402
from ai.llm import ProveedorGrabado  # noqa: E402
from ai.respuesta import responder  # noqa: E402
from ai.verificacion import verificar_en_pdf  # noqa: E402

FALLAS: list[str] = []
P01 = "Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos?"


def caso(nombre: str, ok: bool, detalle: str = "") -> None:
    print(f"{'✓' if ok else '✗'} {nombre}" + ("" if ok else f"  ({detalle})"))
    if not ok:
        FALLAS.append(nombre)


def en_blanco(paginas: int) -> bytes:
    escritor = PdfWriter()
    for _ in range(paginas):
        escritor.add_blank_page(width=612, height=792)
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()


def main() -> int:
    utf8()
    entero = (RAIZ / "data" / "polizas" / "chubb_viajes_jetsmart.pdf").read_bytes()
    parte1, parte2 = partir_pdf(entero, [11])
    archivos = [("condiciones_generales.pdf", parte1), ("clausulas_adicionales.pdf", parte2)]

    partida = subida.poliza_de_pdfs(archivos)
    una = subida.poliza_de_pdfs([("chubb.pdf", entero)])
    caso("dos PDF: un solo documento de 62 páginas, con las páginas de cada archivo",
         partida.indice.meta["paginas"] == 62 and partida.archivos == [archivos[0][:1] + (10,), archivos[1][:1] + (52,)],
         str(partida.archivos))
    caso("dos PDF: mismos trozos y mismo texto que el PDF entero",
         [t.texto for t in partida.indice.trozos] == [t.texto for t in una.indice.trozos],
         f"{len(partida.indice.trozos)} frente a {len(una.indice.trozos)}")
    caso("dos PDF: el nombre dice cuántos archivos son", partida.nombre == "Tu póliza (2 archivos)", partida.nombre)
    caso("dos PDF: la huella cambia si cambia el orden",
         subida.huella([parte1, parte2]) != subida.huella([parte2, parte1]))

    caso("página 10 → última del primer archivo", subida.ubicar_pagina(partida.archivos, 10) == ("condiciones_generales.pdf", 10))
    caso("página 11 → primera del segundo", subida.ubicar_pagina(partida.archivos, 11) == ("clausulas_adicionales.pdf", 1))
    caso("rango dentro de un archivo",
         subida.paginas_con_archivo(partida.archivos, [16, 17]) == "clausulas_adicionales.pdf, págs. 6–7")
    caso("pasaje que cruza de un archivo al otro",
         subida.paginas_con_archivo(partida.archivos, [10, 11])
         == "condiciones_generales.pdf, pág. 10 – clausulas_adicionales.pdf, pág. 1")

    trozo = next(t for t in partida.indice.trozos if "B4 - Continuación" in t.texto)
    frase = trozo.texto[trozo.texto.index("B4 - Continuación"):][:60]
    caso("B4 está en la página 16 de corrido = pág. 6 del segundo archivo",
         subida.paginas_con_archivo(partida.archivos, trozo.paginas) == "clausulas_adicionales.pdf, pág. 6",
         str(trozo.paginas))
    caso("la cita se verifica en el PDF unido con los dos lectores",
         verificar_en_pdf(partida.pdf_bytes, [(trozo.paginas[0], frase)]) == {"pdfplumber": True, "pypdf": True})

    try:
        subida.poliza_de_pdfs([("condiciones_generales.pdf", parte1), ("foto_de_la_poliza.pdf", en_blanco(3))])
        caso("un archivo escaneado se rechaza diciendo cuál", False, "no se rechazó")
    except subida.PolizaIlegible as e:
        caso("un archivo escaneado se rechaza diciendo cuál", "foto_de_la_poliza.pdf" in str(e), str(e))

    pasos: list[str] = []
    r = responder(P01, poliza("chubb_viajes_jetsmart"), ProveedorGrabado(), avance=pasos.append)
    caso("avance: buscar, redactar y verificar (normalización en la caché)",
         r["modo"] == "completo" and [p.split()[0] for p in pasos] == ["Buscando", "Redactando", "Verificando"], str(pasos))
    pasos.clear()
    responder("¿Me cubren si pierdo el pasaporte en Cusco?", poliza("chubb_viajes_jetsmart"), ProveedorGrabado(),
              avance=pasos.append)
    caso("avance: una pregunta nueva empieza por entenderla", pasos[:1] == ["Entendiendo tu pregunta…"], str(pasos))

    print(f"\n{'Todo bien' if not FALLAS else f'{len(FALLAS)} fallas'}.")
    return 1 if FALLAS else 0


if __name__ == "__main__":
    raise SystemExit(main())

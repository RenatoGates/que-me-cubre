"""La póliza que sube la persona: uno o varios PDF, leídos como un solo documento.

Hay pólizas que vienen en partes (el condicionado en un PDF y las cláusulas en otro, o un
documento partido en dos). Se suben juntas y se indexan como una sola: las páginas se
numeran de corrido en el orden de subida, que es el orden de las páginas del PDF unido con
el que se verifican las citas. Para mostrar, cada página se traduce a su archivo y a su
número dentro de él ("parte2.pdf, pág. 4").

Todo en memoria: nada se escribe en disco (ver app/app.py).
"""

from __future__ import annotations

import hashlib
import io

from pypdf import PdfReader, PdfWriter

from ai import embeddings, portero
from ai.extraccion import extraer_varios
from ai.indice import Indice
from ai.respuesta import Poliza
from ai.troceado import trocear
from ai.verificacion import leer_todas


def metodo_configurado() -> str:
    from ai.llm import config
    from ai.recuperacion import METODO_POR_DEFECTO

    return (config("QMC_RECUPERACION", METODO_POR_DEFECTO) or METODO_POR_DEFECTO).strip().lower()


class PolizaIlegible(ValueError):
    """El PDF no se puede usar: escaneado, sin texto o dañado."""


def huella(pdfs: list[bytes]) -> str:
    """Identifica el conjunto de archivos, en su orden (cambiar el orden cambia las páginas)."""
    return hashlib.sha256(b"".join(hashlib.sha256(b).digest() for b in pdfs)).hexdigest()


def unir_pdfs(pdfs: list[bytes]) -> bytes:
    """Un solo PDF con las páginas de todos, en orden. Con un archivo, el mismo archivo."""
    if len(pdfs) == 1:
        return pdfs[0]
    escritor = PdfWriter()
    for datos in pdfs:
        escritor.append(PdfReader(io.BytesIO(datos)))
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()


def reparar(pdf: bytes) -> bytes:
    """El mismo PDF si pdfplumber lo abre; si no, reescrito en memoria con pypdf. Hay PDF
    reales (una póliza dental, en las pruebas) con un detalle de formato que pdfminer rechaza
    y pypdf lee: reescrito, lo leen los dos y las páginas siguen siendo las mismas."""
    import pdfplumber

    try:
        with pdfplumber.open(io.BytesIO(pdf)) as abierto:
            len(abierto.pages)
        return pdf
    except Exception:  # noqa: BLE001 - cualquier falla de lectura: se intenta la reescritura
        pass
    try:
        escritor = PdfWriter()
        escritor.append(PdfReader(io.BytesIO(pdf)))
        salida = io.BytesIO()
        escritor.write(salida)
        with pdfplumber.open(io.BytesIO(salida.getvalue())) as abierto:
            len(abierto.pages)
        return salida.getvalue()
    except Exception as e:  # noqa: BLE001
        raise PolizaIlegible("No pude leer ese PDF: puede estar dañado o protegido con contraseña.") from e


def poliza_de_pdfs(archivos: list[tuple[str, bytes]]) -> Poliza:
    """[(nombre del archivo, bytes)] → la póliza indexada como un solo documento."""
    pdfs = [reparar(datos) for _, datos in archivos]
    doc = extraer_varios(pdfs)
    escaneados = [archivos[i][0] for i in doc.archivos_escaneados()]
    if escaneados:
        raise PolizaIlegible(
            f"{', '.join(escaneados)}: no tiene texto seleccionable en la mayoría de páginas (parece "
            "escaneado). Necesitaría OCR, que esta versión no hace."
        )
    nombre = "Tu póliza" if len(archivos) == 1 else f"Tu póliza ({len(archivos)} archivos)"
    trozos = trocear(doc.bloques, "subida", nombre)
    if not trozos:
        raise PolizaIlegible("No encontré texto en el PDF.")
    try:
        unido = unir_pdfs(pdfs)
    except Exception as e:  # noqa: BLE001 - PDF protegido o dañado
        raise PolizaIlegible(f"No pude unir los PDF: {e}") from e
    if len(PdfReader(io.BytesIO(unido)).pages) != doc.paginas_total:
        raise PolizaIlegible("Las páginas del PDF unido no coinciden con las leídas.")
    meta = {"doc_id": "subida", "documento": nombre, "paginas": doc.paginas_total}
    quiere_vectores = embeddings.disponible() and not metodo_configurado().startswith("bm25")
    try:
        indice = Indice.construir(trozos, meta, con_embeddings=quiere_vectores)
    except embeddings.ErrorEmbeddings:  # la póliza se indexa igual; la búsqueda queda en BM25
        indice = Indice.construir(trozos, meta, con_embeddings=False)
    poliza = Poliza("subida", nombre, indice, unido, huella(pdfs),
                    archivos=[(n, p) for (n, _), p in zip(archivos, doc.paginas_por_archivo)],
                    revision=portero.revisar_trozos(trozos))
    # El texto de cada página con los dos lectores queda leído desde ahora: las citas se
    # verifican contra él, tanto en memoria como si la póliza se guarda (sin el PDF).
    leer_todas(unido, poliza.paginas_leidas, doc.paginas_total, doc.paginas_crudas)
    return poliza


def ubicar_pagina(archivos: list[tuple[str, int]], pagina: int) -> tuple[str, int]:
    """Página de corrido → (archivo, página dentro de ese archivo)."""
    desde = 0
    for nombre, n in archivos:
        if pagina <= desde + n:
            return nombre, pagina - desde
        desde += n
    return archivos[-1][0], pagina - (desde - archivos[-1][1])


def paginas_con_archivo(archivos: list[tuple[str, int]], paginas: list[int]) -> str:
    """"parte2.pdf, pág. 4", "parte2.pdf, págs. 4–5" o, si cruza de un archivo al otro,
    "parte1.pdf, pág. 30 – parte2.pdf, pág. 1"."""
    (a1, p1), (a2, p2) = ubicar_pagina(archivos, paginas[0]), ubicar_pagina(archivos, paginas[-1])
    if a1 != a2:
        return f"{a1}, pág. {p1} – {a2}, pág. {p2}"
    return f"{a1}, pág. {p1}" if p1 == p2 else f"{a1}, págs. {p1}–{p2}"

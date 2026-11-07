"""Verificación de citas: el texto citado tiene que existir, literal, en la página que se dice.

Dos comprobaciones independientes del modelo:
1. `ubicar`: la cita está dentro del pasaje que el modelo recibió. Da la posición exacta,
   y de ella sale la página (el modelo nunca decide el número de página).
2. `verificar_en_pdf`: la cita está en esa página del PDF original, leída de nuevo con
   pdfplumber (el lector del producto, por columnas) y con pypdf (otro lector).

"Literal" significa los mismos caracteres en el mismo orden. Solo se ignoran espacios y
saltos de línea, guiones (los de fin de línea se unen al trocear), comillas tipográficas
y puntos suspensivos entre fragmentos. Mayúsculas y tildes cuentan.
"""

from __future__ import annotations

import io
import re

from ai.extraccion import texto_de_paginas

_IGNORAR = set(" \t\r\n ­​-‐‑‒–—")
_EQUIVALENTES = {"“": '"', "”": '"', "«": '"', "»": '"', "‘": "'", "’": "'", "´": "'"}
_PUA = re.compile(r"[-]")
_ELIPSIS = re.compile(r"\s*(?:\[\s*(?:\.\.\.|…)\s*\]|\(\s*(?:\.\.\.|…)\s*\)|\.\.\.|…)\s*")
MIN_FRAGMENTO = 12  # caracteres normalizados


def _normalizar(s: str) -> tuple[str, list[int]]:
    s = _PUA.sub("•", s.replace("&amp;", "&"))
    chars, mapa = [], []
    for i, c in enumerate(s):
        if c in _IGNORAR:
            continue
        chars.append(_EQUIVALENTES.get(c, c))
        mapa.append(i)
    return "".join(chars), mapa


def fragmentos(cita: str) -> list[str]:
    """Una cita con '...' se verifica por partes, en orden."""
    partes = [p for p in _ELIPSIS.split(cita) if p.strip()]
    return [p for p in partes if len(_normalizar(p)[0]) >= MIN_FRAGMENTO]


def ubicar(texto: str, cita: str) -> tuple[int, int] | None:
    """Posición [inicio, fin) de la cita en `texto`, o None si no está literal."""
    norm, mapa = _normalizar(texto)
    partes = fragmentos(cita)
    if not partes or not mapa:
        return None
    desde, inicio = 0, None
    for parte in partes:
        p, _ = _normalizar(parte)
        j = norm.find(p, desde)
        if j < 0:
            return None
        if inicio is None:
            inicio = j
        desde = j + len(p)
    return mapa[inicio], mapa[desde - 1] + 1


def verificar_en_pdf(pdf_bytes: bytes, partes: list[tuple[int, str]]) -> dict[str, bool]:
    """¿Cada parte de la cita está en su página del PDF? Con dos lectores distintos.

    `partes` es [(página, texto)]: una cita que cruza de una página a otra se verifica por
    tramos, porque entre ambas el PDF tiene el pie y el membrete de página.
    Tramos muy cortos para verificarse solos (< MIN_FRAGMENTO) se omiten; al menos uno
    tiene que verificarse.
    """
    from pypdf import PdfReader

    partes = [(n, t) for n, t in partes if len(_normalizar(t)[0]) >= MIN_FRAGMENTO]
    resultado = {"pdfplumber": False, "pypdf": False}
    if not partes:
        return resultado
    try:
        resultado["pdfplumber"] = all(ubicar(texto_de_paginas(pdf_bytes, [n]), t) is not None for n, t in partes)
    except Exception:  # noqa: BLE001 - un lector que falla cuenta como "no verificado"
        pass
    try:
        lector = PdfReader(io.BytesIO(pdf_bytes))

        def pagina(n: int) -> str:
            return lector.pages[n - 1].extract_text() or "" if 0 < n <= len(lector.pages) else ""

        resultado["pypdf"] = all(ubicar(pagina(n), t) is not None for n, t in partes)
    except Exception:  # noqa: BLE001
        pass
    return resultado

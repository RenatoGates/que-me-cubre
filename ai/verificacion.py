"""Verificación de citas: el texto citado tiene que existir, literal, en la página que se dice.

Dos comprobaciones independientes del modelo:
1. `ubicar`: la cita está dentro del pasaje que el modelo recibió. Da la posición exacta,
   y de ella sale la página (el modelo nunca decide el número de página).
2. `verificar_en_pdf`: la cita está en esa página del PDF original, leída de nuevo con
   pdfplumber (el lector del producto, por columnas) y con pypdf (otro lector).

"Literal" significa los mismos caracteres en el mismo orden. Solo se ignoran espacios y
saltos de línea, guiones (los de fin de línea se unen al trocear), comillas tipográficas
y puntos suspensivos entre fragmentos. Mayúsculas y tildes cuentan.

Única tolerancia adicional: el signo de puntuación final de la cita (. : ; ,). El modelo
suele cerrar con punto una cita que en el PDF termina en dos puntos. Si la cita no está tal
cual, se prueba sin ese último signo, y lo que se muestra es la cita sin él, que sí es
literal. Nada más se relaja: ni espacios internos, ni tildes, ni palabras.

3. `referencias` / `referencia_permitida`: el texto libre de la respuesta no puede nombrar
   artículos, cláusulas ni documentos que no estén en las citas verificadas.
"""

from __future__ import annotations

import io
import re

from ai.extraccion import texto_de_paginas
from ai.indice import sin_tildes, tokens

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


PUNTUACION_FINAL = ".:;,"


def ubicar_cita(texto: str, cita: str) -> tuple[tuple[int, int], str, str | None] | None:
    """Como `ubicar`, con la única tolerancia del signo final. Devuelve (posición, cita tal
    como está en el texto, signo final ignorado o None), o None si no está."""
    pos = ubicar(texto, cita)
    if pos:
        return pos, cita, None
    recortada = cita.rstrip()
    if recortada and recortada[-1] in PUNTUACION_FINAL:
        signo, recortada = recortada[-1], recortada[:-1]
        pos = ubicar(texto, recortada)
        if pos:
            return pos, recortada, signo
    return None


# ---------------------------------------------------------------------------
# Referencias en el texto libre
# ---------------------------------------------------------------------------

# Documentos que un condicionado suele mencionar y que no son el condicionado mismo.
DOCUMENTOS = (
    "condiciones particulares", "condiciones generales", "condiciones especiales", "certificado de seguro",
    "certificado", "solicitud de seguro", "resumen informativo", "endoso", "endosos", "anexo", "anexos",
    "clausula adicional", "clausulas adicionales", "tabla de beneficios", "plan de beneficios",
)
_ARTICULO = re.compile(r"\bart(?:[íi]culos?|\.)?\s*(\d+)", re.IGNORECASE)
_NUMERAL = re.compile(r"\bnumeral\s+(\d+(?:\.\d+)+|\d+)", re.IGNORECASE)
_CODIGO = re.compile(r"\b([A-Z]\d{1,2})\b")  # códigos de cobertura: B4, G2


def _plano(s: str) -> str:
    """Palabras en minúscula y sin tildes, separadas por un espacio (con bordes)."""
    return " " + " ".join(re.findall(r"[a-z0-9ñ]+", sin_tildes(s.lower()))) + " "


def referencias(texto: str, clausulas_documento: list[str]) -> list[tuple[str, str]]:
    """Artículos, numerales, códigos de cobertura, documentos y títulos de cláusula que el
    texto nombra, como (tipo, forma normalizada). Los títulos de cláusula se detectan solo
    si el texto los nombra completos; una paráfrasis ("la cláusula dental") no se detecta."""
    plano = _plano(texto)
    refs = [("articulo", f"articulo {n}") for n in _ARTICULO.findall(texto)]
    refs += [("numeral", " ".join(n.split("."))) for n in _NUMERAL.findall(texto)]
    refs += [("codigo", c) for c in _CODIGO.findall(texto)]
    restante = plano
    for doc in sorted(DOCUMENTOS, key=len, reverse=True):  # "certificado de seguro" antes que "certificado"
        if f" {doc} " in restante:
            refs.append(("documento", doc))
            restante = restante.replace(f" {doc} ", " ")
    tk = tokens(texto)
    for c in clausulas_documento:
        tc = tokens(c)
        if len(tc) >= 2 and any(tk[i : i + len(tc)] == tc for i in range(len(tk) - len(tc) + 1)):
            refs.append(("clausula", " ".join(tc)))
    return list(dict.fromkeys(refs))


def referencia_permitida(ref: tuple[str, str], citas: list[dict]) -> bool:
    """¿La referencia está en alguna cita verificada, en su texto o en su sección y artículo?"""
    tipo, valor = ref
    for c in citas:
        etiqueta = f"{c['seccion']} {c['articulo']}"
        if tipo == "codigo":
            if re.search(rf"\b{re.escape(valor)}\b", c["texto_literal"]) or re.search(rf"\b{re.escape(valor)}\b", etiqueta):
                return True
        elif tipo == "clausula":
            tc = valor.split()
            for t in (tokens(c["texto_literal"]), tokens(etiqueta)):
                if any(t[i : i + len(tc)] == tc for i in range(len(t) - len(tc) + 1)):
                    return True
        else:  # articulo, numeral, documento: como palabras seguidas
            if f" {valor} " in _plano(c["texto_literal"]) or f" {valor} " in _plano(etiqueta):
                return True
    return False


_ORACION = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ¿¡\"(])")


def recortar(texto: str, citas: list[dict], clausulas_documento: list[str]) -> tuple[str, list[dict]]:
    """Quita del texto las oraciones que nombran algo que no está en las citas verificadas.
    Devuelve (texto recortado, [{"oracion", "nombra"}] de lo quitado)."""
    quedan, quitadas = [], []
    for oracion in _ORACION.split(texto.strip()):
        malas = [v for v in referencias(oracion, clausulas_documento) if not referencia_permitida(v, citas)]
        if malas:
            quitadas.append({"oracion": oracion, "nombra": [v[1] for v in malas]})
        else:
            quedan.append(oracion)
    return " ".join(quedan).strip(), quitadas


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

"""Troceado por artículo (RAG, sesión 08).

Cada artículo (o numeral) de la póliza es un trozo. Si pasa de MAX_CARACTERES se parte en
límites de párrafo, o de línea si un párrafo es muy largo, y cada parte conserva la
etiqueta de su artículo ("Artículo 5° Exclusiones, parte 2 de 3").

Cada trozo guarda en qué carácter empieza cada página (`segmentos`), de modo que la página
de una cita se calcula a partir del texto citado y nunca la decide el modelo.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from ai.extraccion import Bloque, Linea

MAX_CARACTERES = 1400
MIN_ULTIMA_PARTE = 250  # una cola más corta que esto se une a la parte anterior

_RE_INICIO_ITEM = re.compile(
    r"^(\(?[a-z]{1,2}\)|\(?\d{1,2}\)|[•\-–]\s?|\d{1,2}(\.\d{1,2})+\.?|[ivx]{1,4}\)|[A-Z]\))"
)


@dataclass
class Trozo:
    id: str
    doc_id: str
    documento: str
    seccion: str
    articulo: str
    parte: int
    partes: int
    paginas: list[int]
    texto: str
    # (página, inicio, fin): rangos de caracteres de `texto` que vienen de cada página
    segmentos: list[tuple[int, int, int]] = field(default_factory=list)

    @property
    def etiqueta(self) -> str:
        sufijo = f" (parte {self.parte} de {self.partes})" if self.partes > 1 else ""
        return f"{self.seccion} › {self.articulo}{sufijo}"

    @property
    def paginas_texto(self) -> str:
        p = self.paginas
        return f"p. {p[0]}" if len(p) == 1 else f"pp. {p[0]}–{p[-1]}"

    def paginas_de(self, inicio: int, fin: int) -> list[int]:
        """Páginas que abarca el rango [inicio, fin) del texto del trozo."""
        return sorted({p for p, a, b in self.segmentos if a < fin and b > inicio})

    def texto_para_embedding(self) -> str:
        # Formato del modelo e5: los pasajes llevan el prefijo "passage: ".
        return f"passage: {self.seccion}. {self.articulo}. {self.texto}"

    def a_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def de_dict(cls, d: dict) -> "Trozo":
        d = dict(d)
        d["segmentos"] = [tuple(s) for s in d.get("segmentos", [])]
        return cls(**d)


# ---------------------------------------------------------------------------
# Reconstrucción de párrafos
# ---------------------------------------------------------------------------


def _parrafos(lineas: list[Linea]) -> list[list[Linea]]:
    """Agrupa líneas visuales en párrafos: corta en ítems de lista y tras punto final."""
    parrafos: list[list[Linea]] = []
    for ln in lineas:
        s = ln.texto
        nuevo = (
            not parrafos
            or _RE_INICIO_ITEM.match(s)
            or (
                parrafos[-1][-1].texto.rstrip().endswith((".", ":", ";"))
                and re.match(r"^[A-ZÁÉÍÓÚÑ¿(\"“0-9]", s)
            )
        )
        if nuevo:
            parrafos.append([ln])
        else:
            parrafos[-1].append(ln)
    return parrafos


def _unir(previo: str, siguiente: str) -> str:
    """Separador entre dos líneas de un mismo párrafo (deshace guiones de fin de línea)."""
    if previo.endswith("-") and len(previo) > 1 and previo[-2].isalpha() and siguiente[:1].isalpha():
        # "condicio-" + "nes" -> "condiciones"; "CONTRA-" + "TANTE" -> "CONTRATANTE";
        # pero "Pre-" + "Existente" conserva el guion.
        if siguiente[0].islower() or (previo[-2].isupper() and siguiente[0].isupper()):
            return "\x00"  # marcador: quitar el guion y no poner espacio
        return ""
    return " "


def _componer(parrafos: list[list[Linea]]) -> tuple[str, list[tuple[int, int, int]]]:
    """Texto del trozo y los rangos de caracteres de cada página."""
    texto = ""
    segmentos: list[tuple[int, int, int]] = []

    def agregar(fragmento: str, pagina: int) -> None:
        nonlocal texto
        inicio = len(texto)
        texto += fragmento
        if segmentos and segmentos[-1][0] == pagina and segmentos[-1][2] == inicio:
            segmentos[-1] = (pagina, segmentos[-1][1], len(texto))
        else:
            segmentos.append((pagina, inicio, len(texto)))

    for i, par in enumerate(parrafos):
        if i > 0:
            texto += "\n"
        for j, ln in enumerate(par):
            s = ln.texto.strip()
            if j > 0:
                sep = _unir(par[j - 1].texto.strip(), s)
                if sep == "\x00":
                    texto = texto[:-1]  # quita el guion
                    if segmentos:
                        p, a, b = segmentos[-1]
                        segmentos[-1] = (p, a, b - 1)
                    sep = ""
                texto += sep
            agregar(s, ln.pagina)
    return texto, segmentos


# ---------------------------------------------------------------------------
# Partición de artículos largos
# ---------------------------------------------------------------------------


def _unidades(parrafos: list[list[Linea]]) -> list[list[list[Linea]]]:
    """Unidades indivisibles: un párrafo, o trozos de un párrafo largo cortados en líneas."""
    unidades: list[list[list[Linea]]] = []
    for par in parrafos:
        largo = sum(len(ln.texto) + 1 for ln in par)
        if largo <= MAX_CARACTERES:
            unidades.append([par])
            continue
        actual: list[Linea] = []
        tam = 0
        for ln in par:
            actual.append(ln)
            tam += len(ln.texto) + 1
            fin_oracion = ln.texto.rstrip().endswith((".", ";", ":"))
            if tam >= MAX_CARACTERES * 0.8 and fin_oracion or tam >= MAX_CARACTERES:
                unidades.append([actual])
                actual, tam = [], 0
        if actual:
            unidades.append([actual])
    return unidades


def _empaquetar(unidades: list[list[list[Linea]]]) -> list[list[list[Linea]]]:
    grupos: list[list[list[Linea]]] = []
    tam = 0
    for u in unidades:
        largo = sum(len(ln.texto) + 1 for par in u for ln in par)
        if grupos and tam + largo <= MAX_CARACTERES:
            grupos[-1].extend(u)
            tam += largo
        else:
            grupos.append(list(u))
            tam = largo
    if len(grupos) > 1:
        ultimo = sum(len(ln.texto) for par in grupos[-1] for ln in par)
        penultimo = sum(len(ln.texto) for par in grupos[-2] for ln in par)
        if ultimo < MIN_ULTIMA_PARTE and ultimo + penultimo <= MAX_CARACTERES * 1.25:
            grupos[-2].extend(grupos.pop())
    return grupos


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def trocear(bloques: list[Bloque], doc_id: str, documento: str) -> list[Trozo]:
    trozos: list[Trozo] = []
    for bloque in bloques:
        validas = lambda ls: [ln for ln in ls if not ln.indice and ln.texto.strip()]  # noqa: E731
        encabezado = validas(bloque.lineas[: bloque.n_encabezado])
        cuerpo = validas(bloque.lineas[bloque.n_encabezado :])
        if not encabezado and not cuerpo:
            continue
        # El encabezado ("Artículo 3° Cobertura") es su propio párrafo, no se pega al texto.
        parrafos = ([encabezado] if encabezado else []) + _parrafos(cuerpo)
        grupos = _empaquetar(_unidades(parrafos))
        for n, grupo in enumerate(grupos, start=1):
            texto, segmentos = _componer(grupo)
            trozos.append(
                Trozo(
                    id=f"{doc_id}:{len(trozos):04d}",
                    doc_id=doc_id,
                    documento=documento,
                    seccion=bloque.seccion,
                    articulo=bloque.articulo,
                    parte=n,
                    partes=len(grupos),
                    paginas=sorted({p for p, _, _ in segmentos}),
                    texto=texto,
                    segmentos=segmentos,
                )
            )
    return trozos

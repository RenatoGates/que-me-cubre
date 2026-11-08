"""Índice de recuperación (RAG, sesión 08): embeddings densos + BM25 sobre los trozos.

- Embeddings: intfloat/multilingual-e5-small (el mismo modelo de la clase de la sesión 08),
  118 M de parámetros, 384 dimensiones, multilingüe y en CPU. Vectores normalizados, así
  que el producto punto es la similitud coseno.
- BM25: palabras sin tildes, sin palabras vacías y reducidas a su raíz (snowball español).
  Encuentra los términos exactos del seguro ("carencia", "deducible") que la normalización
  de la pregunta pone en la consulta.

Los condicionados precargados se indexan una vez con `python -m ai.ingesta` y se guardan
en data/indices/. Las pólizas que sube el usuario se indexan en memoria y no se guardan.
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
import snowballstemmer
from rank_bm25 import BM25Okapi

from ai.troceado import Trozo

MODELO_EMBEDDINGS = "intfloat/multilingual-e5-small"
VERSION_INDICE = 1  # súbela si cambia el extractor o el troceado

# ---------------------------------------------------------------------------
# Texto para BM25
# ---------------------------------------------------------------------------

_PALABRAS_VACIAS = set(
    """
    a al algo algun alguna algunas alguno algunos ante antes asi aun bajo cada como con contra
    cual cuales cuando de del desde donde dos e el ella ellas ellos en entre era es esa esas ese
    eso esos esta estas este esto estos fue fueron ha han hasta hay la las le les lo los mas me
    mi mis muy ni no nos o otra otras otro otros para pero por que quien se sea segun ser si sin
    sobre su sus tal tambien te ti tiene tienen todo todos tu tus un una unas uno unos y ya yo
    """.split()
)
_RAIZ = snowballstemmer.stemmer("spanish")


def sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def tokens(texto: str) -> list[str]:
    palabras = re.findall(r"[a-z0-9ñ]+", sin_tildes(texto.lower()))
    return _RAIZ.stemWords([p for p in palabras if p not in _PALABRAS_VACIAS and len(p) > 1])


def texto_para_bm25(t: Trozo) -> str:
    return f"{t.seccion} {t.articulo} {t.texto}"


# ---------------------------------------------------------------------------
# Títulos: vocabulario del documento e índice BM25 solo de títulos
# ---------------------------------------------------------------------------

_PREFIJO_CLAUSULA = re.compile(r"^cl[áa]usula adicional(?: de)?\s*:?\s*", re.IGNORECASE)
_NUMERACION = re.compile(
    r"^(?:art[íi]culo\s*\d+\s*[°º]?\s*[:.\-–]*\s*"  # "Artículo 3° ", "ARTÍCULO 9º.- "
    r"|[A-Z]\.\s+"  # "A. INFORMACION GENERAL", "PARTE C." queda aparte
    r"|\d+(?:\.\d+)*\.?\s+)",  # "9.5. ", "2.1.1. ", "1. "
    re.IGNORECASE,
)
_SIN_TITULO = re.compile(r"^(?:numeral\s+[\d.]+|texto (?:inicial|completo) de la secci[óo]n)$", re.IGNORECASE)


def limpiar_titulo(segmento: str) -> str | None:
    """Un segmento de título tal como lo dice el PDF, sin numeración. None si el troceado
    lo inventó ("numeral 10.1", "Texto inicial de la sección")."""
    s = segmento.strip()
    if _SIN_TITULO.match(s):
        return None
    s = _PREFIJO_CLAUSULA.sub("", s)
    s = re.sub(r"^parte\s+[a-z]\.\s*", "", s, flags=re.IGNORECASE)  # "PARTE C. EXCLUSIONES"
    for _ in range(2):  # "Artículo 10° 10.1. ..." trae dos niveles
        s = _NUMERACION.sub("", s)
    s = s.strip(" :.-–")
    return s if tokens(s) else None


def titulos_de(t: Trozo) -> list[str]:
    """Títulos que encabezan el trozo: su cláusula y cada nivel de su artículo."""
    partes = [t.seccion, *t.articulo.split(" › ")]
    return [s for s in (limpiar_titulo(p) for p in partes) if s]


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


@lru_cache(maxsize=1)
def modelo_embeddings():
    """Carga el modelo una sola vez por proceso (en la app, además, con st.cache_resource)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(MODELO_EMBEDDINGS, device="cpu")


def embeber_pasajes(trozos: list[Trozo], lote: int = 16) -> np.ndarray:
    modelo = modelo_embeddings()
    vectores = modelo.encode(
        [t.texto_para_embedding() for t in trozos],
        batch_size=lote,
        normalize_embeddings=True,
        convert_to_numpy=True,
        show_progress_bar=False,
    )
    return vectores.astype(np.float32)


def embeber_consulta(consulta: str) -> np.ndarray:
    # Formato del modelo e5: las consultas llevan el prefijo "query: ".
    v = modelo_embeddings().encode(
        [f"query: {consulta}"], normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
    )
    return v[0].astype(np.float32)


# ---------------------------------------------------------------------------
# Índice
# ---------------------------------------------------------------------------


@dataclass
class Indice:
    trozos: list[Trozo]
    vectores: np.ndarray | None  # (n, 384) normalizados; None si no hay embeddings
    meta: dict

    def __post_init__(self) -> None:
        self.bm25 = BM25Okapi([tokens(texto_para_bm25(t)) or ["_"] for t in self.trozos])
        # Índice aparte solo con los títulos: en el cuerpo, las palabras del título son unas
        # pocas entre cientos; aquí pesan solas (documentos cortos, palabras menos repetidas).
        self.bm25_titulos = BM25Okapi([tokens(" ".join(titulos_de(t))) or ["_"] for t in self.trozos])
        # Mismo texto (sin importar la sección) -> misma clave: sirve para no repetir
        # artículos idénticos de distintas cláusulas al recuperar.
        self.claves_texto = [hash(" ".join(tokens(t.texto))) for t in self.trozos]

    def vocabulario(self) -> tuple[list[str], list[str]]:
        """(títulos de cláusula, títulos de artículo) del documento, sin repetir, en orden.
        Es la lista de la que la normalización tiene que elegir."""
        if not hasattr(self, "_vocabulario"):
            clausulas = _unicos(limpiar_titulo(t.seccion) for t in self.trozos)
            articulos = _unicos(s for t in self.trozos for s in titulos_de(t)[1:])
            vistos = {" ".join(tokens(c)) for c in clausulas}
            articulos = [a for a in articulos if " ".join(tokens(a)) not in vistos]
            self._vocabulario = (clausulas, articulos)
        return self._vocabulario

    @classmethod
    def construir(cls, trozos: list[Trozo], meta: dict, con_embeddings: bool = True) -> "Indice":
        vectores = embeber_pasajes(trozos) if con_embeddings and trozos else None
        meta = {
            **meta,
            "version_indice": VERSION_INDICE,
            "modelo_embeddings": MODELO_EMBEDDINGS if vectores is not None else None,
            "n_trozos": len(trozos),
        }
        return cls(trozos, vectores, meta)

    # --- disco (solo para los condicionados públicos precargados) ---

    def guardar(self, carpeta: Path, doc_id: str) -> None:
        carpeta.mkdir(parents=True, exist_ok=True)
        with open(carpeta / f"{doc_id}.trozos.jsonl", "w", encoding="utf-8", newline="\n") as f:
            for t in self.trozos:
                f.write(json.dumps(t.a_dict(), ensure_ascii=False) + "\n")
        if self.vectores is not None:
            np.save(carpeta / f"{doc_id}.embeddings.npy", self.vectores.astype(np.float16))
        (carpeta / f"{doc_id}.meta.json").write_text(
            json.dumps(self.meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
        )

    @classmethod
    def cargar(cls, carpeta: Path, doc_id: str) -> "Indice":
        meta = json.loads((carpeta / f"{doc_id}.meta.json").read_text(encoding="utf-8"))
        with open(carpeta / f"{doc_id}.trozos.jsonl", encoding="utf-8") as f:
            trozos = [Trozo.de_dict(json.loads(linea)) for linea in f if linea.strip()]
        ruta_vec = carpeta / f"{doc_id}.embeddings.npy"
        vectores = np.load(ruta_vec).astype(np.float32) if ruta_vec.exists() else None
        if vectores is not None and len(vectores) != len(trozos):
            raise ValueError(f"{doc_id}: {len(vectores)} vectores para {len(trozos)} trozos; reindexa")
        return cls(trozos, vectores, meta)


def _unicos(titulos) -> list[str]:
    """Sin repetir por sus palabras (mayúsculas, tildes y signos no cuentan)."""
    salida, vistos = [], set()
    for t in titulos:
        clave = " ".join(tokens(t or ""))
        if clave and clave not in vistos:
            vistos.add(clave)
            salida.append(t)
    return salida

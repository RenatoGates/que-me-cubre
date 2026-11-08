"""Caché de normalizaciones de preguntas de ensayo y de prueba (versionada en el repo).

La normalización es la primera de las dos llamadas al LLM de cada consulta. Para las
preguntas que se ensayan antes de la demo (y las de pruebas/), se guarda una vez y la
app la reutiliza: en vivo se gasta una llamada en vez de dos.

Privacidad: la app desplegada SOLO LEE este archivo. Las preguntas de los usuarios nunca
se escriben aquí ni en ningún otro lado. Solo `python -m ai.preparar_demo`, corrido a mano
en local con una lista pública de preguntas (data/demo/preguntas_ensayo.json y
pruebas/preguntas.json), agrega entradas.

Clave: el texto de la pregunta (sin mayúsculas, tildes ni signos) + el sha256 del PDF.
Así acierta tanto con un condicionado precargado como si se sube el mismo PDF.

Cada entrada guarda la versión del prompt de normalización (ai/prompts.py). Una entrada de
otra versión no se usa y se borra la próxima vez que se escribe la caché. La versión 1
(antes de anclar la normalización a los títulos del documento) quedó en
pruebas/normalizaciones_v1.json como evidencia de la comparación.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from ai.indice import sin_tildes
from ai.prompts import VERSION_NORMALIZACION

CAMPOS = ("variantes", "titulos", "clausulas", "articulos", "hechos")

RUTA = Path(__file__).resolve().parent.parent / "data" / "cache" / "normalizaciones.json"


def texto_clave(pregunta: str) -> str:
    texto = sin_tildes(pregunta.lower())
    return " ".join(re.findall(r"[a-z0-9ñ]+", texto))


def clave(pregunta: str, sha256_pdf: str) -> str:
    return f"{sha256_pdf[:16]}|{texto_clave(pregunta)}"


@lru_cache(maxsize=1)
def _cargar() -> dict[str, dict]:
    if not RUTA.exists():
        return {}
    return json.loads(RUTA.read_text(encoding="utf-8"))


def buscar(pregunta: str, sha256_pdf: str) -> dict | None:
    """Normalización guardada para esta pregunta y este PDF, o None. Solo lectura."""
    entrada = _vigente(pregunta, sha256_pdf)
    if entrada is None:
        return None
    return {k: entrada[k] for k in CAMPOS} | {"ajuste": None}


def tokens_generacion(pregunta: str, sha256_pdf: str) -> dict | None:
    """Tokens que costó generar esa normalización (lo que gastaría en vivo sin la caché)."""
    entrada = _vigente(pregunta, sha256_pdf)
    return entrada.get("tokens") if entrada else None


def _vigente(pregunta: str, sha256_pdf: str) -> dict | None:
    entrada = _cargar().get(clave(pregunta, sha256_pdf))
    return entrada if entrada and entrada.get("version") == VERSION_NORMALIZACION else None


# --- Escritura: solo desde ai/preparar_demo.py (local, preguntas públicas) ---


def guardar(entradas: dict[str, dict]) -> None:
    datos = {k: v for k, v in _cargar().items() if v.get("version") == VERSION_NORMALIZACION}
    datos.update({k: {"version": VERSION_NORMALIZACION, **v} for k, v in entradas.items()})
    RUTA.parent.mkdir(parents=True, exist_ok=True)
    RUTA.write_text(
        json.dumps(dict(sorted(datos.items())), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    _cargar.cache_clear()

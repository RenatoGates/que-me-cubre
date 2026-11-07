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
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from ai.indice import sin_tildes

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
    entrada = _cargar().get(clave(pregunta, sha256_pdf))
    if entrada is None:
        return None
    return {k: entrada[k] for k in ("variantes", "terminos", "hechos")} | {"ajuste": None}


# --- Escritura: solo desde ai/preparar_demo.py (local, preguntas públicas) ---


def guardar(entradas: dict[str, dict]) -> None:
    datos = dict(_cargar())
    datos.update(entradas)
    RUTA.parent.mkdir(parents=True, exist_ok=True)
    RUTA.write_text(
        json.dumps(dict(sorted(datos.items())), ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    _cargar.cache_clear()

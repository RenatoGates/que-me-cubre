"""Embeddings por API (Voyage AI): los vectores de los pasajes y de las consultas.

Reemplaza al modelo local e5-small, que con torch no entraba en la memoria del servidor.
Qué sale hacia Voyage: al indexar una póliza, el texto de todos sus pasajes; en cada
consulta, la pregunta y sus variantes. Sin VOYAGE_API_KEY no se llama a nadie y la
búsqueda queda en BM25 (ai/recuperacion.py).
"""

from __future__ import annotations

import logging
import time
from typing import Literal

import httpx
import numpy as np

from ai.llm import config

URL = "https://api.voyageai.com/v1/embeddings"
MAX_TEXTOS = 128
MAX_CARACTERES = 150_000  # por petición; voyage-4-large admite 120 000 tokens
# Modo paciente (QMC_VOYAGE_PACIENTE=1), solo para los scripts: una cuenta de Voyage sin medio de
# pago admite 3 peticiones y 10 000 tokens por minuto. Lotes chicos, una petición cada 21 s y
# espera ante un 429. La API nunca espera así: ante un 429 busca con BM25.
CARACTERES_PACIENTE = 18_000
PAUSA_PACIENTE = 21.0

log = logging.getLogger("qmc.llm")
tokens_usados = 0  # del proceso; el backend lo lee para la observabilidad
_ultima_peticion = 0.0
_consultas: dict[tuple[str, str], np.ndarray] = {}  # (modelo, texto) -> vector, de este proceso


class ErrorEmbeddings(RuntimeError):
    """Voyage no devolvió vectores: sin clave, sin conexión, límite o error."""


def modelo() -> str:
    return config("QMC_MODELO_EMBEDDINGS", "voyage-4-large") or "voyage-4-large"


def disponible() -> bool:
    return bool(config("VOYAGE_API_KEY"))


def paciente() -> bool:
    return (config("QMC_VOYAGE_PACIENTE", "0") or "0") == "1"


def _lotes(textos: list[str]):
    tope = CARACTERES_PACIENTE if paciente() else MAX_CARACTERES
    lote, largo = [], 0
    for t in textos:
        if lote and (len(lote) >= MAX_TEXTOS or largo + len(t) > tope):
            yield lote
            lote, largo = [], 0
        lote.append(t)
        largo += len(t)
    if lote:
        yield lote


def _pedir(lote: list[str], tipo: str, clave: str) -> dict:
    global _ultima_peticion
    lento = paciente()
    for intento in range(1, 9 if lento else 3):
        if lento:
            time.sleep(max(0.0, _ultima_peticion + PAUSA_PACIENTE - time.monotonic()))
            _ultima_peticion = time.monotonic()
        try:
            r = httpx.post(URL, headers={"Authorization": f"Bearer {clave}"}, timeout=60.0,
                           json={"input": lote, "model": modelo(), "input_type": tipo})
        except httpx.HTTPError as e:
            log.warning("voyage %s: %s", tipo, type(e).__name__)
            raise ErrorEmbeddings("Voyage no responde en este momento.") from e
        if r.status_code == 429 and (lento or intento == 1):
            time.sleep(30.0 if lento else 2.0)
            continue
        if r.status_code != 200:
            log.warning("voyage %s: HTTP %d | %d textos", tipo, r.status_code, len(lote))
            raise ErrorEmbeddings(f"Voyage rechazó la solicitud ({r.status_code}).")
        return r.json()
    raise ErrorEmbeddings("Voyage: se alcanzó el límite de la cuenta.")


def embeber(textos: list[str], tipo: Literal["document", "query"]) -> np.ndarray:
    """Vectores normalizados (n, d), en el orden de `textos`."""
    global tokens_usados
    clave = config("VOYAGE_API_KEY")
    if not clave:
        raise ErrorEmbeddings("Falta VOYAGE_API_KEY.")
    if tipo == "query":  # las consultas repetidas (la misma pregunta con otro método) no se vuelven a pedir
        faltan = list(dict.fromkeys(t for t in textos if (modelo(), t) not in _consultas))
        if faltan:
            for t, v in zip(faltan, _embeber(faltan, tipo, clave)):
                if len(_consultas) > 2000:
                    _consultas.clear()
                _consultas[(modelo(), t)] = v
        return np.stack([_consultas[(modelo(), t)] for t in textos])
    return _embeber(textos, tipo, clave)


def _embeber(textos: list[str], tipo: str, clave: str) -> np.ndarray:
    global tokens_usados
    filas = []
    for lote in _lotes(textos):
        datos = _pedir(lote, tipo, clave)
        tokens_usados += int(datos.get("usage", {}).get("total_tokens", 0))
        filas += [d["embedding"] for d in sorted(datos["data"], key=lambda d: d["index"])]
    v = np.asarray(filas, dtype=np.float32)
    return v / np.maximum(np.linalg.norm(v, axis=1, keepdims=True), 1e-12)

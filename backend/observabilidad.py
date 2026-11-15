"""Observabilidad con Langfuse: qué se pregunta, modelo, tokens, costo, latencia y fallas.

Qué se envía: la pregunta (se apaga con QMC_LANGFUSE_PREGUNTA=0), y por cada llamada al
modelo la tarea, el modelo, los tokens, el costo, la duración y el tipo de falla. Qué no se
envía nunca: el PDF, los pasajes, las citas ni el texto de la respuesta (trae citas
literales de la póliza). Sin las claves de Langfuse no se envía nada.
"""

from __future__ import annotations

import logging
from contextlib import contextmanager

from ai import llm
from ai.llm import config

log = logging.getLogger("qmc.llm")
_cliente = None


def activar() -> bool:
    global _cliente
    if not (config("LANGFUSE_PUBLIC_KEY") and config("LANGFUSE_SECRET_KEY")):
        return False
    try:
        from langfuse import get_client

        _cliente = get_client()
    except Exception as e:  # noqa: BLE001 - la app funciona igual sin observabilidad
        log.warning("langfuse: no se pudo iniciar (%s)", type(e).__name__)
        return False
    llm.observar = _llamada
    return True


def activo() -> bool:
    return _cliente is not None


@contextmanager
def _llamada(tarea: str, proveedor: str, modelo: str):
    with _cliente.start_as_current_observation(as_type="generation", name=tarea, model=modelo,
                                               metadata={"proveedor": proveedor}) as g:
        def anotar(uso=None, error: str | None = None, detalle: str | None = None) -> None:
            if uso is not None:
                g.update(usage_details={"input": uso.tokens_entrada, "output": uso.tokens_salida},
                         cost_details={"total": uso.costo_usd})
            if error:
                g.update(level="ERROR", status_message=f"{error}: {detalle or ''}"[:300])

        yield anotar


@contextmanager
def consulta(pregunta: str, **meta):
    """Una traza por consulta. Devuelve una función para anotar el resultado (solo metadatos)."""
    if _cliente is None:
        yield lambda **_datos: None
        return
    con_pregunta = (config("QMC_LANGFUSE_PREGUNTA", "1") or "1") != "0"
    with _cliente.start_as_current_observation(as_type="span", name="consulta",
                                               input=pregunta if con_pregunta else None, metadata=meta) as span:
        def anotar(**datos) -> None:
            falla = datos.get("error")
            span.update(metadata={**meta, **datos}, **({"level": "WARNING", "status_message": str(falla)} if falla else {}))

        yield anotar


def cerrar() -> None:
    if _cliente is not None:
        _cliente.flush()

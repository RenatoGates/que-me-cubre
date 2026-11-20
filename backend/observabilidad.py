"""Observabilidad con Langfuse: solo métricas.

Qué se envía: qué función se usó, y por cada llamada al modelo la tarea, el modelo, los tokens,
el costo, la duración y el tipo de falla. Nunca texto: ni el PDF, ni los pasajes, ni la
pregunta, ni la respuesta, ni correos. Cada valor pasa por `solo_metricas`, que deja números,
booleanos y palabras clave cortas (como "completo" o "LimiteAlcanzado") y descarta todo lo
demás. Sin las claves de Langfuse no se envía nada.
"""

from __future__ import annotations

import logging
import re
from contextlib import contextmanager

from ai import llm
from ai.llm import config

log = logging.getLogger("qmc.llm")
_cliente = None
_PALABRA = re.compile(r"^[A-Za-z0-9_.\-]{1,48}$")  # una palabra clave, nunca una frase


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


def _valor(v):
    if isinstance(v, bool) or v is None or isinstance(v, (int, float)):
        return v
    if isinstance(v, str):
        return v if _PALABRA.match(v) else None
    if isinstance(v, (list, tuple)):
        return [x for x in (_valor(y) for y in v[:10]) if x is not None]
    return None


def solo_metricas(datos: dict) -> dict:
    """Deja solo números, booleanos y palabras clave: una frase (texto de una póliza, una
    pregunta o un correo) no pasa."""
    return {k: x for k, v in datos.items() if _PALABRA.match(k) and (x := _valor(v)) is not None}


@contextmanager
def _llamada(tarea: str, proveedor: str, modelo: str):
    falla = None
    with _cliente.start_as_current_observation(as_type="generation", name=_valor(tarea) or "tarea", model=_valor(modelo),
                                               metadata=solo_metricas({"proveedor": proveedor})) as g:
        def anotar(uso=None, error: str | None = None, detalle: str | None = None) -> None:  # noqa: ARG001 - el detalle no sale
            if uso is not None:
                g.update(usage_details={"input": int(uso.tokens_entrada), "output": int(uso.tokens_salida)},
                         cost_details={"total": float(uso.costo_usd)})
            if error:
                g.update(level="ERROR", status_message=_valor(error) or "error")

        try:
            yield anotar
        except BaseException as e:  # noqa: BLE001 - se relanza afuera de la traza
            falla = e
            g.update(level="ERROR", status_message=type(e).__name__)
    if falla is not None:
        raise falla


@contextmanager
def funcion(nombre: str, **meta):
    """Una traza por uso de una función (preguntar, pasos, radiografía, comparar). Devuelve una
    función para anotar el resultado; todo pasa por `solo_metricas`."""
    if _cliente is None:
        yield lambda **_datos: None
        return
    falla = None
    with _cliente.start_as_current_observation(as_type="span", name=_valor(nombre) or "funcion",
                                               metadata=solo_metricas(meta)) as span:
        def anotar(**datos) -> None:
            falla_ = _valor(datos.get("error"))
            span.update(metadata=solo_metricas({**meta, **datos}),
                        **({"level": "WARNING", "status_message": falla_} if falla_ else {}))

        try:
            yield anotar
        except BaseException as e:  # noqa: BLE001 - se relanza afuera de la traza
            falla = e
            span.update(level="WARNING", status_message=type(e).__name__)
    if falla is not None:
        raise falla


def cerrar() -> None:
    if _cliente is not None:
        _cliente.flush()

"""Cliente de la API de Anthropic con salidas estructuradas (LLM, sesión 08).

La clave se lee de st.secrets (app en Streamlit) o de la variable de entorno
ANTHROPIC_API_KEY (scripts locales, cargada desde .env). Nunca está en el código.
Ninguna pregunta ni respuesta se registra: esta función no escribe logs.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass

import anthropic

MODELO = "claude-opus-5-5"
# Si el modelo rechaza una solicitud por sus salvaguardas, la API la reintenta con un
# modelo de respaldo dentro de la misma llamada (beta "server-side fallback").
BETAS = ["server-side-fallback-2026-07-01"]

# Precios de lista (USD por millón de tokens) para estimar el costo por consulta.
PRECIOS_USD_MTOK = {
    "claude-opus-5-5": (4.00, 20.00),
    "claude-sonnet-5-5": (2.00, 10.00),
    "claude-haiku-5-5": (0.10, 0.50),
}


class ErrorLLM(RuntimeError):
    """El modelo no devolvió una salida utilizable (rechazo, corte o error de API)."""


@dataclass
class Uso:
    modelo: str
    tokens_entrada: int
    tokens_salida: int
    segundos: float

    @property
    def costo_usd(self) -> float:
        p_in, p_out = PRECIOS_USD_MTOK.get(self.modelo, PRECIOS_USD_MTOK[MODELO])
        return (self.tokens_entrada * p_in + self.tokens_salida * p_out) / 1_000_000

    def a_dict(self) -> dict:
        return {
            "modelo": self.modelo,
            "tokens_entrada": self.tokens_entrada,
            "tokens_salida": self.tokens_salida,
            "segundos": round(self.segundos, 2),
            "costo_usd": round(self.costo_usd, 5),
        }


def _clave() -> str | None:
    try:
        import streamlit as st

        if "ANTHROPIC_API_KEY" in st.secrets:
            return st.secrets["ANTHROPIC_API_KEY"]
    except Exception:  # noqa: BLE001 - fuera de Streamlit, o sin secrets.toml
        pass
    return os.environ.get("ANTHROPIC_API_KEY")


def hay_clave() -> bool:
    return bool(_clave())


def cliente() -> anthropic.Anthropic:
    clave = _clave()
    if not clave:
        raise ErrorLLM("Falta ANTHROPIC_API_KEY (en .streamlit/secrets.toml, en Settings > Secrets o en .env).")
    return anthropic.Anthropic(api_key=clave, max_retries=2, timeout=120.0)


def llamar_json(sistema: str, usuario: str, esquema: dict, esfuerzo: str, max_tokens: int = 16000) -> tuple[dict, Uso]:
    """Una llamada con salida JSON garantizada por esquema. Devuelve (datos, uso)."""
    t0 = time.perf_counter()
    try:
        r = cliente().beta.messages.create(
            model=MODELO,
            max_tokens=max_tokens,
            system=sistema,
            messages=[{"role": "user", "content": usuario}],
            output_config={"effort": esfuerzo, "format": {"type": "json_schema", "schema": esquema}},
            betas=BETAS,
            fallbacks="default",
        )
    except anthropic.AuthenticationError as e:
        raise ErrorLLM("La clave de Anthropic no es válida.") from e
    except anthropic.RateLimitError as e:
        raise ErrorLLM("La API de Anthropic está saturada (límite de uso); intenta en un minuto.") from e
    except anthropic.APIStatusError as e:
        raise ErrorLLM(f"Error de la API de Anthropic ({e.status_code}).") from e
    except anthropic.APIConnectionError as e:
        raise ErrorLLM("No hay conexión con la API de Anthropic.") from e

    if r.stop_reason == "refusal":
        raise ErrorLLM("El modelo declinó responder esta consulta.")
    if r.stop_reason == "max_tokens":
        raise ErrorLLM("La respuesta del modelo se cortó por longitud.")
    texto = next((b.text for b in r.content if b.type == "text"), None)
    if texto is None:
        raise ErrorLLM("El modelo no devolvió texto.")
    uso = Uso(r.model, r.usage.input_tokens, r.usage.output_tokens, time.perf_counter() - t0)
    return json.loads(texto), uso

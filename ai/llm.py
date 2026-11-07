"""Capa del LLM detrás de una interfaz (sesión 08: salidas estructuradas).

El resto del código solo usa `obtener_proveedor().json(tarea, sistema, usuario, esquema)`.
El proveedor se elige con la variable QMC_PROVEEDOR (st.secrets o entorno):

- "groq" (por defecto): openai/gpt-oss-120b en el plan gratuito de Groq, con Zero Data
  Retention activado en la cuenta. Groq no retiene datos de inferencia por defecto.
- "gemini": gemini-3.8-flash en el plan gratuito de Google AI Studio. Alternativa manual:
  en ese plan Google puede usar lo enviado para mejorar sus productos y personas pueden
  revisarlo, así que la interfaz lo advierte.

No hay respaldo automático: si el proveedor elegido falla o llega a su límite, se informa
(LimiteAlcanzado / ProveedorNoDisponible) y la app decide qué mostrar. Nunca cambia de
modelo ni de proveedor por su cuenta. Las claves vienen de .env o st.secrets.
"""

from __future__ import annotations

import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

Tarea = Literal["normalizacion", "respuesta"]

ESPERA_MAXIMA_REINTENTO = 8.0  # s: si el proveedor pide esperar más, se avisa en vez de esperar


class ErrorLLM(RuntimeError):
    """El proveedor no devolvió una salida utilizable."""


class LimiteAlcanzado(ErrorLLM):
    """El plan gratuito llegó a su límite (HTTP 429)."""

    def __init__(self, mensaje: str, espera_segundos: float | None = None):
        super().__init__(mensaje)
        self.espera_segundos = espera_segundos


class ProveedorNoDisponible(ErrorLLM):
    """Sin conexión, tiempo agotado o error del servidor del proveedor."""


def config(nombre: str, defecto: str | None = None) -> str | None:
    """Lee una variable de st.secrets (Streamlit) o del entorno (.env en local)."""
    try:
        import streamlit as st

        if nombre in st.secrets:
            return str(st.secrets[nombre])
    except Exception:  # noqa: BLE001 - fuera de Streamlit, o sin secrets.toml
        pass
    return os.environ.get(nombre, defecto)


@dataclass
class Uso:
    proveedor: str
    modelo: str
    tokens_entrada: int
    tokens_salida: int
    segundos: float

    @property
    def costo_usd(self) -> float:
        return 0.0  # plan gratuito del proveedor: no hay cobro por token

    def a_dict(self) -> dict:
        return {
            "proveedor": self.proveedor,
            "modelo": self.modelo,
            "tokens_entrada": self.tokens_entrada,
            "tokens_salida": self.tokens_salida,
            "segundos": round(self.segundos, 2),
            "costo_usd": self.costo_usd,
        }


class Proveedor(ABC):
    nombre: str
    variable_clave: str
    modelos: dict[str, str]  # tarea -> modelo
    reutiliza_datos: bool
    aviso: str  # lo que la interfaz debe decir sobre lo que se envía

    def __init__(self) -> None:
        self.clave = config(self.variable_clave)
        if not self.clave:
            raise ErrorLLM(f"Falta {self.variable_clave} (en .env en local o en Settings > Secrets en Streamlit Cloud).")

    @abstractmethod
    def _llamar(self, tarea: Tarea, modelo: str, sistema: str, usuario: str, esquema: dict) -> tuple[str, int, int]:
        """Devuelve (texto JSON, tokens de entrada, tokens de salida)."""

    def json(self, tarea: Tarea, sistema: str, usuario: str, esquema: dict) -> tuple[dict, Uso]:
        modelo = self.modelos[tarea]
        t0 = time.perf_counter()
        texto, t_in, t_out = self._llamar(tarea, modelo, sistema, usuario, esquema)
        try:
            datos = json.loads(texto)
        except json.JSONDecodeError as e:
            raise ErrorLLM("El modelo devolvió un JSON inválido.") from e
        return datos, Uso(self.nombre, modelo, t_in, t_out, time.perf_counter() - t0)


# ---------------------------------------------------------------------------
# Groq (por defecto)
# ---------------------------------------------------------------------------


class ProveedorGroq(Proveedor):
    nombre = "groq"
    variable_clave = "GROQ_API_KEY"
    reutiliza_datos = False
    aviso = (
        "Tu pregunta y los fragmentos de la póliza que encontré se envían a Groq para redactar la "
        "respuesta (modelo openai/gpt-oss-120b). La cuenta tiene activada la retención cero de datos: "
        "Groq no los guarda ni los reutiliza."
    )
    # max_completion_tokens moderado: el plan gratuito limita los tokens por minuto
    _ESFUERZO = {"normalizacion": "low", "respuesta": "medium"}
    _MAX_TOKENS = {"normalizacion": 1200, "respuesta": 3000}

    def __init__(self) -> None:
        super().__init__()
        modelo = config("QMC_MODELO", "openai/gpt-oss-120b")
        self.modelos = {"normalizacion": config("QMC_MODELO_NORMALIZACION", modelo), "respuesta": modelo}
        from groq import Groq

        # max_retries=0: el SDK reintentaría los 429 esperando hasta un minuto; aquí se decide abajo.
        self.cliente = Groq(api_key=self.clave, max_retries=0, timeout=60.0)

    def _llamar(self, tarea, modelo, sistema, usuario, esquema):
        import groq

        def pedir():
            return self.cliente.chat.completions.create(
                model=modelo,
                messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": tarea, "strict": True, "schema": esquema},
                },
                reasoning_effort=self._ESFUERZO[tarea],
                include_reasoning=False,
                max_completion_tokens=self._MAX_TOKENS[tarea],
            )

        for intento in (1, 2):
            try:
                r = pedir()
                break
            except groq.RateLimitError as e:
                espera = _segundos(e.response.headers.get("retry-after"))
                if intento == 1 and espera is not None and espera <= ESPERA_MAXIMA_REINTENTO:
                    time.sleep(espera)
                    continue
                raise LimiteAlcanzado("Groq: se alcanzó el límite del plan gratuito.", espera) from e
            except groq.AuthenticationError as e:
                raise ErrorLLM("La clave de Groq no es válida.") from e
            except (groq.APIConnectionError, groq.APITimeoutError, groq.InternalServerError) as e:
                raise ProveedorNoDisponible("Groq no responde en este momento.") from e
            except groq.APIStatusError as e:
                raise ErrorLLM(f"Groq rechazó la solicitud ({e.status_code}).") from e

        eleccion = r.choices[0]
        if eleccion.finish_reason == "length":
            raise ErrorLLM("La respuesta del modelo se cortó por longitud.")
        return eleccion.message.content or "", r.usage.prompt_tokens, r.usage.completion_tokens


# ---------------------------------------------------------------------------
# Gemini (alternativa manual)
# ---------------------------------------------------------------------------


class ProveedorGemini(Proveedor):
    nombre = "gemini"
    variable_clave = "GEMINI_API_KEY"
    reutiliza_datos = True
    aviso = (
        "Atención: estás usando el plan gratuito de Google Gemini. Tu pregunta y los fragmentos de la "
        "póliza se envían a Google, que puede usarlos para mejorar sus productos, y personas pueden "
        "revisarlos. No subas pólizas con datos personales mientras uses este proveedor."
    )

    def __init__(self) -> None:
        super().__init__()
        self.modelos = {
            "normalizacion": config("QMC_MODELO_NORMALIZACION", "gemini-3.5-flash-lite"),
            "respuesta": config("QMC_MODELO", "gemini-3.8-flash"),
        }
        from google import genai
        from google.genai import types

        # attempts=1: sin reintentos automáticos
        self.cliente = genai.Client(
            api_key=self.clave,
            http_options=types.HttpOptions(timeout=60_000, retry_options=types.HttpRetryOptions(attempts=1)),
        )

    def _llamar(self, tarea, modelo, sistema, usuario, esquema):
        from google.genai import errors, types

        ajustes = {
            "system_instruction": sistema,
            "response_mime_type": "application/json",
            "response_json_schema": esquema,
        }
        if tarea == "respuesta":
            ajustes["thinking_config"] = types.ThinkingConfig(thinking_level="medium")
        try:
            r = self.cliente.models.generate_content(
                model=modelo, contents=usuario, config=types.GenerateContentConfig(**ajustes)
            )
        except errors.ClientError as e:
            if e.code == 429:
                raise LimiteAlcanzado("Gemini: se alcanzó el límite del plan gratuito.") from e
            if e.code in (401, 403):
                raise ErrorLLM("La clave de Gemini no es válida.") from e
            raise ErrorLLM(f"Gemini rechazó la solicitud ({e.code}).") from e
        except errors.ServerError as e:
            raise ProveedorNoDisponible("Gemini no responde en este momento.") from e
        u = r.usage_metadata
        salida = (u.candidates_token_count or 0) + (u.thoughts_token_count or 0) if u else 0
        return r.text or "", (u.prompt_token_count or 0) if u else 0, salida


# ---------------------------------------------------------------------------

PROVEEDORES: dict[str, type[Proveedor]] = {"groq": ProveedorGroq, "gemini": ProveedorGemini}


def nombre_proveedor() -> str:
    return (config("QMC_PROVEEDOR", "groq") or "groq").strip().lower()


def obtener_proveedor() -> Proveedor:
    nombre = nombre_proveedor()
    if nombre not in PROVEEDORES:
        raise ErrorLLM(f"QMC_PROVEEDOR='{nombre}' no existe; usa: {', '.join(PROVEEDORES)}.")
    return PROVEEDORES[nombre]()


def _segundos(valor: str | None) -> float | None:
    try:
        return float(valor) if valor is not None else None
    except ValueError:
        return None

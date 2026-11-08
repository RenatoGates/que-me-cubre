"""Capa del LLM detrás de una interfaz (sesión 08: salidas estructuradas).

El resto del código solo usa `obtener_proveedor().json(tarea, sistema, usuario, esquema)`.
El proveedor se elige con la variable QMC_PROVEEDOR (st.secrets o entorno):

- "groq" (por defecto): openai/gpt-oss-120b en el plan gratuito de Groq, con Zero Data
  Retention activado en la cuenta. Groq no retiene datos de inferencia por defecto.
- "gemini": gemini-3.8-flash en el plan gratuito de Google AI Studio. Alternativa manual:
  en ese plan Google puede usar lo enviado para mejorar sus productos y personas pueden
  revisarlo, así que la interfaz lo advierte.

No hay respaldo automático: si el proveedor elegido falla, llega a su límite o el modelo no
genera un JSON válido, se informa (LimiteAlcanzado / ProveedorNoDisponible / SalidaInvalida)
y la app decide qué mostrar. Nunca cambia de
modelo ni de proveedor por su cuenta. Las claves vienen de .env o st.secrets.

Registro: cada falla de una llamada deja una línea en stderr (en Streamlit Cloud, los logs
de "Manage app") con la tarea, el código HTTP, el código de error de Groq y su mensaje.
Nunca la pregunta, los pasajes ni lo que generó el modelo: del mensaje se borran los
valores entre comillas (pueden ser texto generado) y el id de la organización.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

Tarea = Literal["normalizacion", "respuesta"]

ESPERA_MAXIMA_REINTENTO = 8.0  # s: si el proveedor pide esperar más, se avisa en vez de esperar

log = logging.getLogger("qmc.llm")
if not log.handlers:  # Streamlit no configura el registro raíz: sin esto, INFO no se vería
    _manejador = logging.StreamHandler(sys.stderr)
    _manejador.setFormatter(logging.Formatter("%(asctime)s qmc.llm %(levelname)s %(message)s"))
    log.addHandler(_manejador)
    log.setLevel(logging.INFO)
    log.propagate = False

_ENTRE_COMILLAS = re.compile(r"'([^'\n]*)'|\"([^\"\n]*)\"")
_CAMPO = re.compile(r"[a-z_]{1,40}")  # nombres de campo del esquema ("podrian_aplicar"): se dejan
_ORGANIZACION = re.compile(r"org_[A-Za-z0-9]+")


def mensaje_seguro(texto: str | None, limite: int = 400) -> str:
    """El mensaje de error del proveedor, sin nada que pueda venir de la pregunta, de la
    póliza o de lo generado: los valores entre comillas se reemplazan por '...' (salvo nombres
    de campo) y el id de la organización también."""

    def cambiar(m: re.Match) -> str:
        valor = m.group(1) if m.group(1) is not None else m.group(2)
        return m.group(0) if _CAMPO.fullmatch(valor) else "'...'"

    limpio = _ORGANIZACION.sub("org_...", _ENTRE_COMILLAS.sub(cambiar, texto or ""))
    return " ".join(limpio.split())[:limite]


class ErrorLLM(RuntimeError):
    """El proveedor no devolvió una salida utilizable."""


class LimiteAlcanzado(ErrorLLM):
    """El plan gratuito llegó a su límite (HTTP 429)."""

    def __init__(self, mensaje: str, espera_segundos: float | None = None):
        super().__init__(mensaje)
        self.espera_segundos = espera_segundos


class ProveedorNoDisponible(ErrorLLM):
    """Sin conexión, tiempo agotado o error del servidor del proveedor."""


class SalidaInvalida(ErrorLLM):
    """El modelo no produjo un JSON válido: se cortó al llegar al tope de tokens, no cumplió
    el esquema o no se pudo leer. Ojo: con json_schema, Groq informa el corte por tope como
    400 json_validate_failed ("max completion tokens reached…"), no como finish_reason
    "length"; por eso "JSON inválido" casi siempre es "se acabó el tope"."""


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
    tokens_salida: int  # incluye el razonamiento: el plan gratuito lo cuenta igual
    segundos: float
    tokens_razonamiento: int = 0

    @property
    def costo_usd(self) -> float:
        return 0.0  # plan gratuito del proveedor: no hay cobro por token

    def a_dict(self) -> dict:
        return {
            "proveedor": self.proveedor,
            "modelo": self.modelo,
            "tokens_entrada": self.tokens_entrada,
            "tokens_salida": self.tokens_salida,
            "tokens_razonamiento": self.tokens_razonamiento,
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
    def _llamar(self, tarea: Tarea, modelo: str, sistema: str, usuario: str, esquema: dict) -> tuple[str, int, int, int]:
        """Devuelve (texto JSON, tokens de entrada, tokens de salida, de ellos de razonamiento)."""

    def json(self, tarea: Tarea, sistema: str, usuario: str, esquema: dict) -> tuple[dict, Uso]:
        modelo = self.modelos[tarea]
        t0 = time.perf_counter()
        texto, t_in, t_out, t_razon = self._llamar(tarea, modelo, sistema, usuario, esquema)
        try:
            datos = json.loads(texto)
        except json.JSONDecodeError as e:
            log.warning("%s %s: JSON ilegible | %d caracteres | %d+%d tokens", self.nombre, tarea, len(texto), t_in, t_out)
            raise SalidaInvalida("El modelo devolvió un JSON inválido.") from e
        return datos, Uso(self.nombre, modelo, t_in, t_out, time.perf_counter() - t0, t_razon)


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

        tope, esfuerzo = self._MAX_TOKENS[tarea], self._ESFUERZO[tarea]
        for intento in (1, 2):
            try:
                r = pedir()
                break
            except groq.RateLimitError as e:  # un 429 no gasta tokens: esperar ≤ 8 s no gasta cuota
                espera = _segundos(e.response.headers.get("retry-after"))
                _registrar(tarea, tope, esfuerzo, e, f"retry-after {espera}")
                if intento == 1 and espera is not None and espera <= ESPERA_MAXIMA_REINTENTO:
                    time.sleep(espera)
                    continue
                raise LimiteAlcanzado("Groq: se alcanzó el límite del plan gratuito.", espera) from e
            except groq.AuthenticationError as e:
                _registrar(tarea, tope, esfuerzo, e)
                raise ErrorLLM("La clave de Groq no es válida.") from e
            except (groq.APIConnectionError, groq.APITimeoutError, groq.InternalServerError) as e:
                _registrar(tarea, tope, esfuerzo, e)
                raise ProveedorNoDisponible("Groq no responde en este momento.") from e
            except groq.APIStatusError as e:
                codigo, mensaje = _registrar(tarea, tope, esfuerzo, e)
                if e.status_code == 413:  # la petición sola supera los tokens por minuto del plan
                    raise LimiteAlcanzado("Groq: la consulta supera el límite por minuto del plan gratuito.") from e
                if e.status_code == 400 and (codigo == "json_validate_failed" or "json_validate_failed" in (e.response.text or "")):
                    if "max completion tokens" in mensaje:
                        raise SalidaInvalida(f"Groq: la respuesta se cortó al llegar al tope de {tope} tokens.") from e
                    raise SalidaInvalida("Groq: el modelo no generó un JSON que cumpla el esquema.") from e
                raise ErrorLLM(f"Groq rechazó la solicitud ({e.status_code}).") from e

        eleccion = r.choices[0]
        if eleccion.finish_reason == "length":
            log.warning("groq %s: finish_reason length | %d+%d tokens | tope %d | razonamiento %s",
                        tarea, r.usage.prompt_tokens, r.usage.completion_tokens, tope, esfuerzo)
            raise SalidaInvalida("La respuesta del modelo se cortó por longitud.")
        detalle = getattr(r.usage, "completion_tokens_details", None)
        razon = getattr(detalle, "reasoning_tokens", 0) or 0
        return eleccion.message.content or "", r.usage.prompt_tokens, r.usage.completion_tokens, razon


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
        razon = (u.thoughts_token_count or 0) if u else 0
        salida = (u.candidates_token_count or 0) + razon if u else 0
        return r.text or "", (u.prompt_token_count or 0) if u else 0, salida, razon


# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Grabado: para maquetar y sacar capturas sin gastar cuota (nunca en la app desplegada)
# ---------------------------------------------------------------------------


class ProveedorGrabado(Proveedor):
    """Devuelve la salida cruda que el modelo ya dio para esa misma pregunta, guardada en
    pruebas/salidas/ (y, si no está ahí, en pruebas/estabilidad/). Todo lo demás corre de
    verdad con el código actual: la búsqueda, la verificación de citas contra el PDF y el
    bloque de lo mencionado pero ausente. Una pregunta sin grabación se comporta como un
    proveedor caído (red de seguridad). Se elige a mano con QMC_PROVEEDOR=grabado; con
    QMC_GRABACIONES="estabilidad/P02_3" se fuerza una grabación concreta."""

    nombre = "grabado"
    variable_clave = ""
    reutiliza_datos = False
    aviso = "Respuesta grabada en pruebas/: no se llamó al modelo ahora (sirve para maquetar sin gastar cuota)."
    modelos = {"normalizacion": "grabado", "respuesta": "grabado"}

    def __init__(self) -> None:  # noqa: D107 - no necesita clave
        from pathlib import Path

        from ai.cache_normalizacion import texto_clave

        pruebas = Path(__file__).resolve().parent.parent / "pruebas"
        forzadas = [pruebas / f"{x.strip()}.json" for x in (config("QMC_GRABACIONES", "") or "").split(",") if x.strip()]
        rutas = forzadas + sorted((pruebas / "salidas").glob("P*.json")) + sorted((pruebas / "estabilidad").glob("P*.json"))
        self._texto_clave = texto_clave
        self._grabadas: dict[str, dict] = {}
        for ruta in rutas:
            r = json.loads(ruta.read_text(encoding="utf-8"))
            if r.get("modelo_crudo"):
                self._grabadas.setdefault(texto_clave(r["pregunta"]), r["modelo_crudo"])

    def _llamar(self, tarea, modelo, sistema, usuario, esquema):  # pragma: no cover - no se usa
        raise NotImplementedError

    def json(self, tarea: Tarea, sistema: str, usuario: str, esquema: dict) -> tuple[dict, Uso]:
        if tarea == "respuesta" and "<pregunta>" in usuario:
            pregunta = usuario.rsplit("<pregunta>", 1)[1].split("</pregunta>")[0].strip()
            crudo = self._grabadas.get(self._texto_clave(pregunta))
            if crudo is not None:
                return json.loads(json.dumps(crudo)), Uso(self.nombre, "grabado", 0, 0, 0.0)
        raise ProveedorNoDisponible("No hay una respuesta grabada para esta pregunta (proveedor de maqueta).")


PROVEEDORES: dict[str, type[Proveedor]] = {"groq": ProveedorGroq, "gemini": ProveedorGemini, "grabado": ProveedorGrabado}


def nombre_proveedor() -> str:
    return (config("QMC_PROVEEDOR", "groq") or "groq").strip().lower()


def obtener_proveedor() -> Proveedor:
    nombre = nombre_proveedor()
    if nombre not in PROVEEDORES:
        raise ErrorLLM(f"QMC_PROVEEDOR='{nombre}' no existe; usa: {', '.join(PROVEEDORES)}.")
    return PROVEEDORES[nombre]()


def _registrar(tarea: str, tope: int, esfuerzo: str, e: Exception, extra: str = "") -> tuple[str | None, str]:
    """Una línea en stderr por cada falla de Groq: tarea, HTTP, código y mensaje de Groq
    (limpio con mensaje_seguro). No incluye la pregunta, los pasajes ni failed_generation.
    Devuelve (código de error, mensaje limpio) para clasificar la falla."""
    status = getattr(e, "status_code", None)
    codigo, mensaje = None, ""
    respuesta = getattr(e, "response", None)
    if respuesta is not None:
        try:
            error = json.loads(respuesta.text or "{}").get("error") or {}
            codigo, mensaje = error.get("code"), mensaje_seguro(error.get("message"))
        except (ValueError, AttributeError):
            mensaje = ""
    log.warning("groq %s: %s %s %s | tope %d | razonamiento %s%s | %s", tarea, type(e).__name__, status or "-",
                codigo or "-", tope, esfuerzo, f" | {extra}" if extra else "", mensaje or "(sin mensaje)")
    return codigo, mensaje


def _segundos(valor: str | None) -> float | None:
    try:
        return float(valor) if valor is not None else None
    except ValueError:
        return None

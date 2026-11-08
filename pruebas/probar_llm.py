"""Prueba, sin red y sin gastar cuota, cómo se clasifican y registran las fallas de Groq.

Simula las respuestas de error de Groq con las excepciones reales del SDK y comprueba:
- la clasificación (SalidaInvalida, LimiteAlcanzado, ProveedorNoDisponible, ErrorLLM);
- que el corte por tope de tokens, que Groq informa como 400 json_validate_failed, se
  distingue del JSON que no cumple el esquema;
- que el registro (stderr, los logs de Streamlit Cloud) trae la tarea, el código y el
  mensaje de Groq, y nunca la pregunta, los pasajes, lo generado ni el id de organización;
- que responder() cae en la red de seguridad sin lanzar excepción y sin reintentar.

    python pruebas/probar_llm.py      # termina con código 1 si algo falla
"""

from __future__ import annotations

import io
import logging
import os

from comun import poliza, preguntas, utf8

os.environ.setdefault("GROQ_API_KEY", "clave-de-prueba-sin-red")
os.environ["QMC_PROVEEDOR"] = "groq"

import groq  # noqa: E402
import httpx  # noqa: E402

from ai.llm import ErrorLLM, LimiteAlcanzado, ProveedorGroq, ProveedorNoDisponible, SalidaInvalida, log  # noqa: E402
from ai.respuesta import responder  # noqa: E402

FALLAS: list[str] = []
URL = "https://api.groq.com/openai/v1/chat/completions"
GENERADO = '{"citas":[{"n":1,"pasaje":"P3","texto_literal":"Los gastos médicos por accidente o enfermedad se limitan'
PREGUNTA = "Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos?"
ORG = "org_01abcdefghijklmnop"

TOPE = ProveedorGroq._MAX_TOKENS["respuesta"]

# El cuerpo que devolvió Groq el 2026-11-08 al reproducir P01 con el tope de 3000 (recortado)
CORTE = {"error": {
    "message": "max completion tokens reached before generating a valid document: the output was truncated to fit "
               "max_completion_tokens and is missing required content. Increase max_completion_tokens. See "
               "'failed_generation' for the truncated output. Error: jsonschema: '' does not validate with "
               "/required: missing properties: 'podrian_aplicar', 'no_incluido_en_documento'",
    "type": "invalid_request_error", "code": "json_validate_failed", "failed_generation": GENERADO}}
ESQUEMA = {"error": {
    "message": "Generated JSON does not match the expected schema. Error: jsonschema: '/cubre' does not validate: "
               "'Sí, la radiografía está cubierta en Tarapoto' is not one of ['si', 'con_limites', 'no', 'no_encontrado']",
    "type": "invalid_request_error", "code": "json_validate_failed", "failed_generation": GENERADO}}
POR_MINUTO = {"error": {
    "message": f"Rate limit reached for model `openai/gpt-oss-120b` in organization `{ORG}` service tier `on_demand` "
               "on tokens per minute (TPM): Limit 8000, Used 6236, Requested 5428. Please try again in 27.48s.",
    "type": "tokens", "code": "rate_limit_exceeded"}}
MUY_GRANDE = {"error": {
    "message": f"Request too large for model `openai/gpt-oss-120b` in organization `{ORG}` service tier `on_demand` on "
               "tokens per minute (TPM): Limit 8000, Requested 8531, please reduce your message size and try again.",
    "type": "tokens", "code": "rate_limit_exceeded"}}


def caso(nombre: str, ok: bool, detalle: str = "") -> None:
    print(f"{'✓' if ok else '✗'} {nombre}" + ("" if ok else f"  ({detalle})"))
    if not ok:
        FALLAS.append(nombre)


def error_http(clase, status: int, cuerpo: dict, cabeceras: dict | None = None):
    req = httpx.Request("POST", URL)
    resp = httpx.Response(status, request=req, json=cuerpo, headers=cabeceras or {})
    return clase(cuerpo["error"]["message"], response=resp, body=cuerpo["error"])


class _Uso:
    prompt_tokens, completion_tokens, completion_tokens_details = 3222, 3000, None


class _Eleccion:
    finish_reason = "length"

    class message:  # noqa: N801 - imita el objeto del SDK
        content = GENERADO


class _Cortada:
    choices = [_Eleccion()]
    usage = _Uso()


def con_falla(falla):
    """Un ProveedorGroq de verdad cuyo cliente, en vez de ir a la red, lanza `falla` o
    devuelve una respuesta cortada. Cuenta cuántas veces se llamó."""
    prov = ProveedorGroq()
    llamadas = []

    def crear(**kw):
        llamadas.append(kw["response_format"]["json_schema"]["name"])
        if isinstance(falla, Exception):
            raise falla
        return falla

    prov.cliente.chat.completions.create = crear
    return prov, llamadas


def registrar():
    salida = io.StringIO()
    manejador = logging.StreamHandler(salida)
    log.addHandler(manejador)
    return salida, manejador


def probar(nombre: str, falla, esperada: type, mensaje_contiene: str = "", log_contiene: tuple[str, ...] = ()) -> None:
    prov, llamadas = con_falla(falla)
    salida, manejador = registrar()
    try:
        prov.json("respuesta", "sistema", f"<pregunta>{PREGUNTA}</pregunta>", {"type": "object"})
        lanzada = None
    except Exception as e:  # noqa: BLE001
        lanzada = e
    finally:
        log.removeHandler(manejador)
    texto = salida.getvalue()
    caso(f"{nombre}: {esperada.__name__}", type(lanzada) is esperada, repr(lanzada))
    if mensaje_contiene:
        caso(f"{nombre}: el error dice «{mensaje_contiene}»", mensaje_contiene in str(lanzada), str(lanzada))
    caso(f"{nombre}: queda en el registro con su código", all(x in texto for x in log_contiene), texto)
    caso(f"{nombre}: el registro no trae lo generado, la pregunta ni la organización",
         "texto_literal" not in texto and "Tarapoto" not in texto and "radiografía" not in texto and ORG not in texto, texto)
    caso(f"{nombre}: una sola llamada (sin reintento)", llamadas == ["respuesta"], str(llamadas))


def main() -> int:
    utf8()
    probar("corte por tope (400 json_validate_failed)", error_http(groq.BadRequestError, 400, CORTE), SalidaInvalida,
           f"tope de {TOPE} tokens", ("respuesta", "BadRequestError 400 json_validate_failed", "max completion tokens reached",
                                      f"tope {TOPE}", "razonamiento medium", "'podrian_aplicar'"))
    probar("JSON fuera del esquema (400 json_validate_failed)", error_http(groq.BadRequestError, 400, ESQUEMA),
           SalidaInvalida, "no generó un JSON que cumpla el esquema",
           ("json_validate_failed", "does not match the expected schema", "'con_limites'"))
    probar("límite por minuto (429, espera larga)",
           error_http(groq.RateLimitError, 429, POR_MINUTO, {"retry-after": "27"}), LimiteAlcanzado, "",
           ("RateLimitError 429 rate_limit_exceeded", "Used 6236, Requested 5428", "retry-after 27"))
    probar("consulta más grande que el límite por minuto (413)",
           error_http(groq.APIStatusError, 413, MUY_GRANDE), LimiteAlcanzado, "", ("413", "Requested 8531"))
    probar("otro 400", error_http(groq.BadRequestError, 400, {"error": {"message": "model 'x' not found",
                                                                         "code": "model_not_found"}}),
           ErrorLLM, "(400)", ("model_not_found",))
    probar("sin conexión", groq.APIConnectionError(request=httpx.Request("POST", URL)), ProveedorNoDisponible, "",
           ("APIConnectionError",))
    probar("finish_reason length", _Cortada(), SalidaInvalida, "se cortó por longitud",
           ("finish_reason length", "3222+3000"))

    # De punta a punta: P01 con el corte de hoy cae en la red de seguridad, sin excepción ni reintento
    q = next(x for x in preguntas() if x["id"] == "P01")
    prov, llamadas = con_falla(error_http(groq.BadRequestError, 400, CORTE))
    salida, manejador = registrar()
    try:
        r = responder(q["pregunta"], poliza(q["poliza"]), prov)
    finally:
        log.removeHandler(manejador)
    texto = salida.getvalue()
    caso("responder: red de seguridad con 'Sin veredicto'", r["modo"] == "solo_clausulas" and r["error"] == "SalidaInvalida"
         and r["etiqueta_veredicto"] == "Sin veredicto", f"{r['modo']} {r.get('error')}")
    caso("responder: normalización de la caché y una sola llamada al modelo",
         r["uso"]["normalizacion_desde_cache"] and llamadas == ["respuesta"], str(llamadas))
    caso("responder: el bloque de ausentes sale igual (B4)", any("B4" in m["nombre"] for m in r["mencionadas_ausentes"]))
    caso("responder: el registro no trae la pregunta ni los pasajes",
         "Tarapoto" not in texto and "dedo" not in texto and r["pasajes"][0]["texto"][:40] not in texto, texto)

    print(f"\n{'Todo bien' if not FALLAS else f'{len(FALLAS)} fallas'}.")
    return 1 if FALLAS else 0


if __name__ == "__main__":
    raise SystemExit(main())

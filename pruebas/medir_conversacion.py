"""Memoria de la conversación: ¿la segunda pregunta recuerda la primera, y cuánto cuesta más?

Con Claude Haiku (gasta de verdad, unos centavos): en la póliza de Chubb, la persona pregunta
"me doblé el tobillo" y después "es que me accidenté". La segunda se responde dos veces: sin
la conversación previa y con ella (los turnos que manda la app, como máximo MAX_TURNOS).

    python pruebas/medir_conversacion.py      # escribe pruebas/conversacion.md
"""

from __future__ import annotations

import json

from comun import PRUEBAS, RAIZ, utf8
from dotenv import load_dotenv

load_dotenv(RAIZ / ".env")

import anthropic

from ai.llm import config
from ai.prompts import ESQUEMA_RESPUESTA, mensaje_respuesta, sistema_respuesta
from ai.recuperacion import recuperar_normalizada
from ai.respuesta import MAX_TURNOS, SIN_NORMALIZACION, pasajes_xml, responder
from backend import almacen

PRIMERA = "Me doblé el tobillo caminando en Cusco durante el viaje, ¿me cubre?"
SEGUNDA = "Es que me accidenté bajando del bus turístico."


def tokens(r: dict) -> tuple[int, int, float]:
    d = r["uso"]["detalle"][-1]
    return d["tokens_entrada"], d["tokens_salida"], r["uso"]["costo_usd"]


def menciona(r: dict, palabra: str) -> bool:
    return palabra in json.dumps({k: r.get(k) for k in ("razonamiento", "respuesta")}, ensure_ascii=False).lower()


def contar(usuario: str) -> int:
    """Tokens de entrada de la respuesta, contados por Anthropic (el conteo no se cobra)."""
    cliente = anthropic.Anthropic(api_key=config("ANTHROPIC_API_KEY"))
    return cliente.messages.count_tokens(model=config("QMC_MODELO", "claude-haiku-5-5") or "claude-haiku-5-5",
                                         system=sistema_respuesta(), messages=[{"role": "user", "content": usuario}]).input_tokens


def main() -> None:
    utf8()
    poliza = almacen.precargada("chubb_viajes_jetsmart")
    r1 = responder(PRIMERA, poliza)
    turno = {"pregunta": PRIMERA, "veredicto": r1["etiqueta_veredicto"], "razonamiento": r1.get("razonamiento") or ""}
    sin = responder(SEGUNDA, poliza)
    con = responder(SEGUNDA, poliza, turnos=[turno])
    ts, tc = tokens(sin), tokens(con)
    filas = [
        ("Primera pregunta", PRIMERA, r1),
        ("Segunda, sin conversación previa", SEGUNDA, sin),
        ("Segunda, con la conversación previa", SEGUNDA, con),
    ]
    texto = ["# Memoria de la conversación", "",
             f"Generado por `pruebas/medir_conversacion.py` con Claude Haiku. La app manda como máximo {MAX_TURNOS} turnos",
             "anteriores (pregunta, veredicto y razonamiento de cada uno).", "",
             "| Consulta | Veredicto | ¿Habla del tobillo? | Tokens de entrada | Costo USD | Razonamiento |", "|---|---|---|---:|---:|---|"]
    for nombre, _, r in filas:
        e, _, c = tokens(r)
        texto.append(f"| {nombre} | {r['etiqueta_veredicto']} | {'sí' if menciona(r, 'tobillo') else 'no'} | {e} | {c:.5f} | "
                     f"{r.get('razonamiento') or '—'} |")
    # El costo del contexto, aislado: la misma consulta con los mismos pasajes, con 0, 1 y 3 turnos.
    pasajes = pasajes_xml(recuperar_normalizada(poliza.indice, PRIMERA + chr(10) + SEGUNDA, SIN_NORMALIZACION, k=5))
    base = contar(mensaje_respuesta(SEGUNDA, [], poliza.secciones, pasajes))
    uno = contar(mensaje_respuesta(SEGUNDA, [], poliza.secciones, pasajes, turnos=[turno]))
    tres = contar(mensaje_respuesta(SEGUNDA, [], poliza.secciones, pasajes, turnos=[turno] * MAX_TURNOS))
    costo = con["uso"]["costo_usd"]
    texto += ["", "Costo del contexto, aislado (misma consulta y mismos pasajes, tokens contados por Anthropic):", "",
              "| Turnos previos | Tokens de entrada | Más que sin contexto | USD más por consulta |", "|---:|---:|---:|---:|",
              f"| 0 | {base} | — | — |",
              f"| 1 | {uno} | {uno - base} | {(uno - base) * 0.10 / 1e6:.6f} |",
              f"| {MAX_TURNOS} | {tres} | {tres - base} | {(tres - base) * 0.10 / 1e6:.6f} |", "",
              f"- Con {MAX_TURNOS} turnos, la consulta cuesta USD {(tres - base) * 0.10 / 1e6:.6f} más: "
              f"{(tres - base) * 0.10 / 1e6 / costo:.1%} de lo que costó la consulta con conversación (USD {costo:.5f}).", ""]
    (PRUEBAS / "conversacion.md").write_text("\n".join(texto), encoding="utf-8")
    print("\n".join(texto))


if __name__ == "__main__":
    main()

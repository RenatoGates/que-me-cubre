"""Mide cuántos tokens gasta una consulta y cómo los cuenta el límite por minuto de Groq.

Usa los mismos parámetros que la app (ai/llm.py) pero lee además las cabeceras
x-ratelimit-* de cada respuesta y, si Groq rechaza la llamada, el cuerpo del error.

    python pruebas/medir_cuota.py P01               # normalización + respuesta, con cabeceras
    python pruebas/medir_cuota.py P01 --admision    # dos respuestas seguidas: si la segunda da 429,
                                                    # su mensaje dice cuánto pide Groq ("Requested")
    python pruebas/medir_cuota.py P08 --modelo openai/gpt-oss-20b   # otro modelo; muestra 400/413

Normalización: con --normalizar llama al LLM; si no, usa la de la caché versionada.
Gasta cuota real del plan gratuito (una consulta ~5000-7000 tokens de 8000 por minuto).
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from comun import RAIZ, poliza, preguntas, utf8

from ai import cache_normalizacion
from ai.llm import ProveedorGroq
from ai.prompts import ESQUEMA_NORMALIZACION, ESQUEMA_RESPUESTA, SISTEMA_NORMALIZACION, SISTEMA_RESPUESTA, mensaje_respuesta
from ai.recuperacion import pasajes_xml, recuperar


def llamar(cliente, modelo: str, tarea: str, sistema: str, usuario: str, esquema: dict, esfuerzo: str, max_tokens: int) -> dict:
    import groq

    t0 = time.perf_counter()
    try:
        raw = cliente.chat.completions.with_raw_response.create(
            model=modelo,
            messages=[{"role": "system", "content": sistema}, {"role": "user", "content": usuario}],
            response_format={"type": "json_schema", "json_schema": {"name": tarea, "strict": True, "schema": esquema}},
            reasoning_effort=esfuerzo,
            include_reasoning=False,
            max_completion_tokens=max_tokens,
        )
    except groq.APIStatusError as e:
        cabeceras = {k: v for k, v in e.response.headers.items() if k.startswith("x-ratelimit") or k == "retry-after"}
        print(f"[{tarea}] {e.status_code} en {time.perf_counter() - t0:.1f} s · {json.dumps(cabeceras)}")
        print("   ", e.response.text[:800])
        return {"tarea": tarea, "error": e.status_code, "cuerpo": e.response.text[:800], "cabeceras": cabeceras}
    r = raw.parse()
    cabeceras = {k: v for k, v in raw.headers.items() if k.startswith("x-ratelimit")}
    uso = r.usage.model_dump() if r.usage else {}
    print(f"[{tarea}] {time.perf_counter() - t0:.1f} s · fin={r.choices[0].finish_reason}")
    print("   uso:", json.dumps({k: uso.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}),
          "razonamiento:", (uso.get("completion_tokens_details") or {}).get("reasoning_tokens"))
    print("   cabeceras:", json.dumps(cabeceras))
    return {"tarea": tarea, "uso": uso, "cabeceras": cabeceras, "contenido": r.choices[0].message.content}


def main() -> int:
    utf8()
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
    p = argparse.ArgumentParser()
    p.add_argument("id")
    p.add_argument("--modelo", default="openai/gpt-oss-120b")
    p.add_argument("--esfuerzo", default=ProveedorGroq._ESFUERZO["respuesta"])
    p.add_argument("--max-salida", type=int, default=ProveedorGroq._MAX_TOKENS["respuesta"])
    p.add_argument("--k", type=int, default=5)
    p.add_argument("--continuar", type=int, default=2)
    p.add_argument("--presupuesto", type=int, default=6500)
    p.add_argument("--normalizar", action="store_true", help="llamar al LLM para normalizar en vez de usar la caché")
    p.add_argument("--admision", action="store_true", help="enviar la respuesta dos veces seguidas")
    p.add_argument("--salida", type=Path)
    a = p.parse_args()

    import groq

    q = next(x for x in preguntas() if x["id"] == a.id)
    pol = poliza(q["poliza"])
    cliente = groq.Groq(api_key=os.environ["GROQ_API_KEY"], max_retries=0, timeout=60)
    registro = []

    if a.normalizar:
        r = llamar(cliente, a.modelo, "normalizacion", SISTEMA_NORMALIZACION, q["pregunta"], ESQUEMA_NORMALIZACION,
                   ProveedorGroq._ESFUERZO["normalizacion"], ProveedorGroq._MAX_TOKENS["normalizacion"])
        registro.append(r)
        if "error" in r:
            return 1
        norm = json.loads(r["contenido"])
    else:
        norm = cache_normalizacion.buscar(q["pregunta"], pol.sha256)
        if norm is None:
            print("Esa pregunta no está en la caché: usa --normalizar o corre python -m ai.preparar_demo")
            return 1

    pasajes = recuperar(pol.indice, q["pregunta"], norm["variantes"], norm["terminos"], k=a.k,
                        continuar=a.continuar, presupuesto_caracteres=a.presupuesto)
    xml = pasajes_xml(pasajes)
    usuario = mensaje_respuesta(q["pregunta"], norm["hechos"], pol.secciones, xml)
    print(f"{len(pasajes)} pasajes · {len(xml)} caracteres de pasajes · {len(usuario)} del mensaje · "
          f"{len(SISTEMA_RESPUESTA)} del sistema · {len(json.dumps(ESQUEMA_RESPUESTA))} del esquema")
    for _ in range(2 if a.admision else 1):
        registro.append(llamar(cliente, a.modelo, "respuesta", SISTEMA_RESPUESTA, usuario, ESQUEMA_RESPUESTA,
                               a.esfuerzo, a.max_salida))
    if a.salida:
        a.salida.write_text(json.dumps({"pregunta": q["id"], "config": {k: str(v) for k, v in vars(a).items()},
                                        "registro": registro}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

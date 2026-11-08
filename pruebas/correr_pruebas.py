"""Corre el flujo completo sobre pruebas/preguntas.json y guarda cada salida en pruebas/salidas/.

    python pruebas/correr_pruebas.py            # solo las que no tienen salida guardada
    python pruebas/correr_pruebas.py --rehacer  # todas de nuevo
    python pruebas/correr_pruebas.py --solo P02

Usa el proveedor de QMC_PROVEEDOR (groq por defecto) con su clave en .env. Antes normaliza
las preguntas que falten en la caché versionada (data/cache/), así las pruebas y el demo
usan exactamente las mismas variantes y cada respuesta gasta una sola llamada.

Ritmo: después de cada pregunta espera lo que el plan gratuito tarda en reponer los tokens
que gastó (8000 por minuto), así ninguna prueba cae en el modo sin texto generado por culpa
de la anterior. Si se acaba el límite diario, espera lo que Groq indique (ProveedorPaciente).
"""

from __future__ import annotations

import argparse
import json
import statistics
import time

from comun import PRUEBAS, RAIZ, SALIDAS, ProveedorPaciente, aceptable, bloque_txt, guardar_json, poliza, preguntas, utf8

from ai import cache_normalizacion
from ai.llm import ErrorLLM, obtener_proveedor
from ai.preparar_demo import asegurar
from ai.respuesta import responder

ETIQUETA = {"si": "sí", "no": "no", "con_limites": "con límites", "no_encontrado": "no encontrado", None: "sin respuesta"}
TPM = 8000  # tokens por minuto del plan gratuito de Groq (cabecera x-ratelimit-limit-tokens)
ESPERA_REINTENTO = 60  # s: con el balde vacío, en un minuto se repone entero


def resumen_md(filas: list[dict], proveedor: str, modelo: str) -> str:
    lineas = [
        "# Resultados de las 10 preguntas",
        "",
        f"Proveedor: {proveedor} · modelo: `{modelo}` (plan gratuito: costo USD 0 por consulta).",
        "Generado por `pruebas/correr_pruebas.py`. Cada salida completa (variantes de la normalización,",
        "pasajes, respuesta cruda del modelo, citas verificadas y descartes) está en `pruebas/salidas/`.",
        "",
        "Tokens: lo que cuenta el límite de tokens por minuto del plan gratuito (entrada + salida; la",
        "salida incluye el razonamiento del modelo). *Normalización* es lo que costó generar la entrada",
        "de la caché: una pregunta nueva en vivo lo gasta además de la respuesta.",
        "",
        "*Mencionadas pero ausentes* es el bloque que calcula el código (ai/referencias.py), sin el modelo;",
        "*No incluido* es lo que el modelo señaló y sobrevivió a la validación.",
        "",
        "| # | Pregunta | Veredicto | ¿Aceptable? | Citas válidas / propuestas | Mencionadas pero ausentes (código) "
        "| No incluido (modelo) | Pasajes | Normalización | Respuesta: entrada | salida (razonamiento) | Consulta completa | Segundos |",
        "|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|",
    ]
    for f in filas:
        lineas.append(
            f"| {f['id']} | {f['pregunta']} | {ETIQUETA[f['cubre']]} | {'sí' if f['aceptable'] else '**no**'} | "
            f"{f['citas_validas']} / {f['citas_propuestas']} | {f['ausentes']} | {f['no_incluido'] or '—'} | {f['pasajes']} | "
            f"{f['tokens_normalizacion'] or '—'} | {f['entrada']} | {f['salida']} ({f['razonamiento']}) | "
            f"{f['consulta_completa']} | {f['segundos']:.1f} |"
        )
    n = len(filas)
    if n:
        resp = [f["tokens"] for f in filas]
        completa = [f["consulta_completa"] for f in filas]
        lineas += [
            "",
            f"- Veredictos aceptables: {sum(f['aceptable'] for f in filas)} de {n}.",
            f"- Citas propuestas por el modelo: {sum(f['citas_propuestas'] for f in filas)}; "
            f"aceptadas tras verificar contra el pasaje y el PDF: {sum(f['citas_validas'] for f in filas)}.",
            f"- Tokens por respuesta (normalización desde la caché, una llamada): promedio {statistics.mean(resp):.0f}, "
            f"mínimo {min(resp)}, máximo {max(resp)}.",
            f"- Tokens por consulta completa (pregunta nueva, dos llamadas): promedio {statistics.mean(completa):.0f}, "
            f"máximo {max(completa)}.",
            f"- De la salida, razonamiento: {sum(f['razonamiento'] for f in filas) / max(1, sum(f['salida'] for f in filas)):.0%}.",
            f"- Tiempo promedio por respuesta: {statistics.mean(f['segundos'] for f in filas):.1f} s.",
        ]
    return "\n".join(lineas) + "\n"


def fila(q: dict, r: dict) -> dict:
    respuesta = r["uso"]["detalle"][-1]
    norm = cache_normalizacion.tokens_generacion(q["pregunta"], poliza(q["poliza"]).sha256)
    t_norm = norm["entrada"] + norm["salida"] if norm else 0
    return {
        "id": q["id"],
        "pregunta": q["pregunta"],
        "cubre": r["cubre"],
        "aceptable": aceptable(q, r),
        "citas_propuestas": len(r.get("modelo_crudo", {}).get("citas", [])),
        "citas_validas": len(r["citas"]),
        "no_incluido": "; ".join(m["nombre"] for m in r["no_incluido_en_documento"]),
        "ausentes": bloque_txt(r),
        "pasajes": len(r["pasajes"]),
        "entrada": respuesta["tokens_entrada"],
        "salida": respuesta["tokens_salida"],
        "razonamiento": respuesta.get("tokens_razonamiento", 0),
        "tokens": r["uso"]["tokens"],
        "tokens_normalizacion": t_norm,
        "consulta_completa": r["uso"]["tokens"] + (0 if len(r["uso"]["detalle"]) > 1 else t_norm),
        "segundos": r["uso"]["segundos"],
    }


def main() -> int:
    utf8()
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
    p = argparse.ArgumentParser()
    p.add_argument("--rehacer", action="store_true")
    p.add_argument("--solo", action="append")
    args = p.parse_args()
    try:
        proveedor = ProveedorPaciente(obtener_proveedor())  # espera los límites en vez de fallar
    except ErrorLLM as e:
        print(f"✗ {e}")
        return 1

    todas = preguntas()
    elegidas = [q for q in todas if not args.solo or q["id"] in args.solo]
    pendientes = [q for q in elegidas if args.rehacer or not (SALIDAS / f"{q['id']}.json").exists()]
    if pendientes:
        print("Normalizaciones (caché versionada):")
        nuevas, faltan = asegurar([(q["poliza"], q["pregunta"]) for q in pendientes], proveedor)
        if faltan:
            return 1
        if nuevas:
            time.sleep(ESPERA_REINTENTO)  # las normalizaciones seguidas dejan el balde casi vacío

    filas, problemas = [], []
    for q in todas:
        ruta = SALIDAS / f"{q['id']}.json"
        if q in pendientes:
            print(f"▶ {q['id']}: {q['pregunta']}", flush=True)
            try:
                r = responder(q["pregunta"], poliza(q["poliza"]), proveedor)
                if r["modo"] != "completo":
                    print(f"  límite alcanzado; espero {ESPERA_REINTENTO} s y reintento una vez", flush=True)
                    time.sleep(ESPERA_REINTENTO)
                    r = responder(q["pregunta"], poliza(q["poliza"]), proveedor)
            except ErrorLLM as e:
                print(f"  ✗ {e}")
                problemas.append(q["id"])
                continue
            if r["modo"] != "completo":
                print(f"  ✗ sin respuesta generada: {r['aviso']}")
                problemas.append(q["id"])
                continue
            r["prueba"] = {k: q[k] for k in ("id", "poliza", "origen", "veredictos_aceptables", "que_deberia_pasar")}
            guardar_json(ruta, r)
            time.sleep(r["uso"]["tokens"] * 60 / TPM)  # lo que el plan tarda en reponer lo gastado
        elif ruta.exists():
            r = json.loads(ruta.read_text(encoding="utf-8"))
        else:
            continue
        f = fila(q, r)
        filas.append(f)
        print(
            f"  {f['id']} {ETIQUETA[f['cubre']]:<14} aceptable={'sí' if f['aceptable'] else 'NO'} "
            f"citas {f['citas_validas']}/{f['citas_propuestas']} · {f['pasajes']} pasajes · "
            f"{f['entrada']}+{f['salida']} ({f['razonamiento']} razon.) = {f['tokens']} tokens "
            f"(+{f['tokens_normalizacion']} normalización) · {f['segundos']:.1f}s"
            + (f" · no incluido: {f['no_incluido']}" if f["no_incluido"] else ""),
            flush=True,
        )

    (PRUEBAS / "resultados.md").write_text(
        resumen_md(filas, proveedor.nombre, proveedor.modelos["respuesta"]), encoding="utf-8", newline="\n"
    )
    print("\nResumen en pruebas/resultados.md" + (f" · sin completar: {problemas}" if problemas else ""))
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())

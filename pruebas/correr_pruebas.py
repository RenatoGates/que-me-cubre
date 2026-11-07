"""Corre el flujo completo sobre pruebas/preguntas.json y guarda cada salida en pruebas/salidas/.

    python pruebas/correr_pruebas.py            # solo las que no tienen salida guardada
    python pruebas/correr_pruebas.py --rehacer  # todas de nuevo
    python pruebas/correr_pruebas.py --solo P02

Usa el proveedor de QMC_PROVEEDOR (groq por defecto) con su clave en .env. Antes normaliza
las preguntas que falten en la caché versionada (data/cache/), así las pruebas y el demo
usan exactamente las mismas variantes y cada respuesta gasta una sola llamada.
"""

from __future__ import annotations

import argparse
import json
import time

from comun import PRUEBAS, RAIZ, SALIDAS, guardar_json, poliza, preguntas, utf8

from ai.llm import ErrorLLM, obtener_proveedor
from ai.preparar_demo import asegurar
from ai.respuesta import responder

ETIQUETA = {"si": "sí", "no": "no", "con_limites": "con límites", "no_encontrado": "no encontrado", None: "sin respuesta"}
PAUSA = 20  # s entre preguntas: el plan gratuito limita tokens por minuto


def resumen_md(filas: list[dict], proveedor: str, modelo: str) -> str:
    lineas = [
        "# Resultados de las 10 preguntas",
        "",
        f"Proveedor: {proveedor} · modelo: `{modelo}` (plan gratuito: costo USD 0 por consulta).",
        "Generado por `pruebas/correr_pruebas.py`. Cada salida completa (variantes de la normalización,",
        "pasajes, respuesta cruda del modelo, citas verificadas y descartes) está en `pruebas/salidas/`.",
        "",
        "| # | Pregunta | Veredicto | ¿Aceptable? | Citas válidas / propuestas | No incluido en el documento | Tokens | Segundos |",
        "|---|---|---|---|---|---|---:|---:|",
    ]
    for f in filas:
        lineas.append(
            f"| {f['id']} | {f['pregunta']} | {ETIQUETA[f['cubre']]} | {'sí' if f['aceptable'] else '**no**'} | "
            f"{f['citas_validas']} / {f['citas_propuestas']} | {f['no_incluido'] or '—'} | {f['tokens']} | {f['segundos']:.1f} |"
        )
    n = len(filas)
    if n:
        lineas += [
            "",
            f"- Veredictos aceptables: {sum(f['aceptable'] for f in filas)} de {n}.",
            f"- Citas propuestas por el modelo: {sum(f['citas_propuestas'] for f in filas)}; "
            f"aceptadas tras verificar contra el pasaje y el PDF: {sum(f['citas_validas'] for f in filas)}.",
            f"- Tokens promedio por respuesta (una llamada, normalización desde la caché): "
            f"{sum(f['tokens'] for f in filas) / n:.0f}; tiempo promedio: {sum(f['segundos'] for f in filas) / n:.1f} s.",
        ]
    return "\n".join(lineas) + "\n"


def fila(q: dict, r: dict) -> dict:
    exige = q.get("debe_mencionar_no_incluido")
    return {
        "id": q["id"],
        "pregunta": q["pregunta"],
        "cubre": r["cubre"],
        "aceptable": r["cubre"] in q["veredictos_aceptables"]
        and (not exige or any(exige in m["nombre"] for m in r["no_incluido_en_documento"])),
        "citas_propuestas": len(r.get("modelo_crudo", {}).get("citas", [])),
        "citas_validas": len(r["citas"]),
        "no_incluido": "; ".join(m["nombre"] for m in r["no_incluido_en_documento"]),
        "tokens": r["uso"]["tokens"],
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
        proveedor = obtener_proveedor()
    except ErrorLLM as e:
        print(f"✗ {e}")
        return 1

    todas = preguntas()
    elegidas = [q for q in todas if not args.solo or q["id"] in args.solo]
    pendientes = [q for q in elegidas if args.rehacer or not (SALIDAS / f"{q['id']}.json").exists()]
    if pendientes:
        print("Normalizaciones (caché versionada):")
        _, faltan = asegurar([(q["poliza"], q["pregunta"]) for q in pendientes], proveedor)
        if faltan:
            return 1

    filas, problemas = [], []
    for q in todas:
        ruta = SALIDAS / f"{q['id']}.json"
        if q in pendientes:
            print(f"▶ {q['id']}: {q['pregunta']}")
            try:
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
            time.sleep(PAUSA)
        elif ruta.exists():
            r = json.loads(ruta.read_text(encoding="utf-8"))
        else:
            continue
        f = fila(q, r)
        filas.append(f)
        print(
            f"  {f['id']} {ETIQUETA[f['cubre']]:<14} aceptable={'sí' if f['aceptable'] else 'NO'} "
            f"citas {f['citas_validas']}/{f['citas_propuestas']} · {f['tokens']} tokens · {f['segundos']:.1f}s"
            + (f" · no incluido: {f['no_incluido']}" if f["no_incluido"] else "")
        )

    (PRUEBAS / "resultados.md").write_text(
        resumen_md(filas, proveedor.nombre, proveedor.modelos["respuesta"]), encoding="utf-8", newline="\n"
    )
    print("\nResumen en pruebas/resultados.md" + (f" · sin completar: {problemas}" if problemas else ""))
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())

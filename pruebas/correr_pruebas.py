"""Corre el flujo completo sobre pruebas/preguntas.json y guarda cada salida en pruebas/salidas/.

    python pruebas/correr_pruebas.py            # solo las que no tienen salida guardada
    python pruebas/correr_pruebas.py --rehacer  # todas de nuevo (cuesta tokens)
    python pruebas/correr_pruebas.py --solo P02

Necesita ANTHROPIC_API_KEY en .env (no se sube al repo).
"""

from __future__ import annotations

import argparse
import json

from comun import PRUEBAS, SALIDAS, guardar_json, poliza, preguntas, utf8

from ai.llm import ErrorLLM, hay_clave
from ai.respuesta import responder

ETIQUETA = {"si": "sí", "no": "no", "con_limites": "con límites", "no_encontrado": "no encontrado"}


def resumen_md(filas: list[dict]) -> str:
    lineas = [
        "# Resultados de las 10 preguntas",
        "",
        "Generado por `pruebas/correr_pruebas.py`. Cada salida completa (variantes de la normalización, pasajes,",
        "respuesta cruda del modelo, citas verificadas y descartes) está en `pruebas/salidas/`.",
        "",
        "| # | Pregunta | Veredicto | ¿Aceptable? | Citas válidas / propuestas | No incluido en el documento | Costo USD | Segundos |",
        "|---|---|---|---|---|---|---:|---:|",
    ]
    for f in filas:
        lineas.append(
            f"| {f['id']} | {f['pregunta']} | {ETIQUETA[f['cubre']]} | {'sí' if f['aceptable'] else '**no**'} | "
            f"{f['citas_validas']} / {f['citas_propuestas']} | {f['no_incluido'] or '—'} | {f['costo']:.4f} | {f['segundos']:.1f} |"
        )
    n = len(filas)
    if n:
        lineas += [
            "",
            f"- Veredictos aceptables: {sum(f['aceptable'] for f in filas)} de {n}.",
            f"- Citas propuestas por el modelo: {sum(f['citas_propuestas'] for f in filas)}; "
            f"aceptadas tras verificar contra el pasaje y el PDF: {sum(f['citas_validas'] for f in filas)}.",
            f"- Costo promedio por consulta: USD {sum(f['costo'] for f in filas) / n:.4f}; "
            f"tiempo promedio: {sum(f['segundos'] for f in filas) / n:.1f} s.",
        ]
    return "\n".join(lineas) + "\n"


def fila(q: dict, r: dict) -> dict:
    return {
        "id": q["id"],
        "pregunta": q["pregunta"],
        "cubre": r["cubre"],
        "aceptable": r["cubre"] in q["veredictos_aceptables"]
        and (not q.get("debe_mencionar_no_incluido") or any(q["debe_mencionar_no_incluido"] in m["nombre"] for m in r["no_incluido_en_documento"])),
        "citas_propuestas": len(r["modelo_crudo"]["citas"]),
        "citas_validas": len(r["citas"]),
        "no_incluido": "; ".join(m["nombre"] for m in r["no_incluido_en_documento"]),
        "costo": r["uso"]["costo_usd"],
        "segundos": r["uso"]["segundos"],
    }


def main() -> int:
    utf8()
    from dotenv import load_dotenv

    load_dotenv(PRUEBAS.parent / ".env")
    p = argparse.ArgumentParser()
    p.add_argument("--rehacer", action="store_true")
    p.add_argument("--solo", action="append")
    args = p.parse_args()
    if not hay_clave():
        print("Falta ANTHROPIC_API_KEY en .env")
        return 1

    filas, fallos = [], []
    for q in preguntas():
        ruta = SALIDAS / f"{q['id']}.json"
        if args.solo and q["id"] not in args.solo:
            if ruta.exists():
                filas.append(fila(q, json.loads(ruta.read_text(encoding="utf-8"))))
            continue
        if ruta.exists() and not args.rehacer:
            r = json.loads(ruta.read_text(encoding="utf-8"))
        else:
            print(f"▶ {q['id']}: {q['pregunta']}")
            try:
                r = responder(q["pregunta"], poliza(q["poliza"]))
            except ErrorLLM as e:
                print(f"  ✗ {e}")
                fallos.append(q["id"])
                continue
            r["prueba"] = {k: q[k] for k in ("id", "poliza", "origen", "veredictos_aceptables", "que_deberia_pasar")}
            guardar_json(ruta, r)
        f = fila(q, r)
        filas.append(f)
        print(
            f"  {f['id']} {ETIQUETA[f['cubre']]:<14} aceptable={'sí' if f['aceptable'] else 'NO'} "
            f"citas {f['citas_validas']}/{f['citas_propuestas']} · USD {f['costo']:.4f} · {f['segundos']:.1f}s"
            + (f" · no incluido: {f['no_incluido']}" if f["no_incluido"] else "")
        )

    (PRUEBAS / "resultados.md").write_text(resumen_md(filas), encoding="utf-8", newline="\n")
    print(f"\nResumen en pruebas/resultados.md" + (f" · fallaron: {fallos}" if fallos else ""))
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())

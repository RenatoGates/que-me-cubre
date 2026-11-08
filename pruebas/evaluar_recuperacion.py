"""¿Cuántas de las preguntas acierta cada método de recuperación?

Acierta = el artículo esperado (definido en preguntas.json antes de correr nada) está
entre los k pasajes que recibe el modelo. Todos los métodos usan las mismas variantes de
la normalización, leídas de pruebas/salidas/ (no se vuelve a llamar al LLM).

Métodos:
- bm25_pregunta:  BM25 con la pregunta tal como la escribió la persona.
- bm25_variantes: BM25 con las 3-5 variantes + términos + pregunta, fusionadas (lo que usa la app).
- emb_pregunta:   embeddings e5-small con la pregunta (lo que se descartó por memoria).
- emb_variantes:  embeddings con las mismas consultas que bm25_variantes.

    python pruebas/evaluar_recuperacion.py     # necesita sentence-transformers (requirements-dev.txt)
"""

from __future__ import annotations

import json

from comun import PRUEBAS, SALIDAS, acierta, guardar_json, poliza, preguntas, utf8

from ai.recuperacion import METODOS, top_k

KS = (3, 5, 8)
NOMBRES = {
    "bm25_pregunta": "BM25, pregunta original",
    "bm25_variantes": "BM25, 3-5 variantes normalizadas (app)",
    "emb_pregunta": "Embeddings e5-small, pregunta original",
    "emb_variantes": "Embeddings e5-small, mismas variantes",
}


def main() -> int:
    utf8()
    filas, detalle = [], {}
    evaluables = []
    for q in preguntas():
        ruta = SALIDAS / f"{q['id']}.json"
        if not ruta.exists():
            print(f"falta {ruta.name}: corre antes pruebas/correr_pruebas.py")
            return 1
        if q["modo"] == "ninguno":
            continue
        evaluables.append(q)
        norm = json.loads(ruta.read_text(encoding="utf-8"))["normalizacion"]
        pol = poliza(q["poliza"])
        detalle[q["id"]] = {}
        for metodo in METODOS:
            ranking = top_k(pol.indice, q["pregunta"], norm["variantes"], norm["terminos"], metodo, max(KS))
            trozos = [pol.indice.trozos[i] for i, _ in ranking]
            detalle[q["id"]][metodo] = {
                f"k{k}": acierta(trozos[:k], q["esperados"], q["modo"]) for k in KS
            } | {"top5": [f"{t.seccion} › {t.articulo}" for t in trozos[:5]]}

    n = len(evaluables)
    lineas = [
        "# Recuperación: BM25 con variantes frente a embeddings",
        "",
        f"{n} de las 10 preguntas tienen un artículo esperado (la P08 es de control: la respuesta",
        "correcta es no encontrar nada, así que no se puede acertar ni fallar en la búsqueda).",
        "Acierta = el artículo esperado está entre los k primeros pasajes (sin repetir textos idénticos).",
        "La app manda al modelo k = 5 (opción A de `pruebas/opciones.md`).",
        "",
        "| Método | " + " | ".join(f"Aciertos con k = {k}" for k in KS) + " |",
        "|---|" + "---:|" * len(KS),
    ]
    for metodo in METODOS:
        cuentas = [sum(bool(detalle[q["id"]][metodo][f"k{k}"]) for q in evaluables) for k in KS]
        lineas.append(f"| {NOMBRES[metodo]} | " + " | ".join(f"{c} de {n}" for c in cuentas) + " |")
        filas.append({"metodo": metodo, **{f"k{k}": c for k, c in zip(KS, cuentas)}, "n": n})

    lineas += ["", "## Por pregunta (k = 5)", "", "| Pregunta | " + " | ".join(METODOS) + " |", "|---|" + "---|" * len(METODOS)]
    for q in evaluables:
        lineas.append(f"| {q['id']} | " + " | ".join("✓" if detalle[q["id"]][m]["k5"] else "✗" for m in METODOS) + " |")

    (PRUEBAS / "recuperacion.md").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    guardar_json(PRUEBAS / "recuperacion.json", {"resumen": filas, "detalle": detalle})
    print("\n".join(lineas[7 : 9 + len(METODOS)]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

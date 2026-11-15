"""¿Cuántas de las preguntas acierta cada método de recuperación?

Acierta = el artículo esperado (definido en preguntas.json antes de correr nada) está
entre los k pasajes que recibe el modelo. Todos los métodos usan las mismas variantes de
la normalización, leídas de data/cache/normalizaciones.json (no se vuelve a llamar al LLM).

Métodos:
- bm25_pregunta:  BM25 con la pregunta tal como la escribió la persona.
- bm25_variantes: BM25 con las 3-5 variantes + la cláusula elegida + pregunta, fusionadas, con los
                  pasajes de la cláusula elegida al doble (lo que usa la app).
- emb_pregunta:   embeddings por API (Voyage) con la pregunta.
- emb_variantes:  embeddings con las mismas consultas y el mismo filtro suave que bm25_variantes.
- hibrido_variantes: BM25 y embeddings fusionados con RRF.

Los métodos con embeddings necesitan VOYAGE_API_KEY y los índices reconstruidos con ese
modelo (python -m ai.ingesta); si falta algo, se miden solo los de BM25 y el resumen lo dice.
La medición anterior, con el modelo local e5-small y la normalización de Groq, está en el
historial de git de pruebas/recuperacion.md (commit 6570fd9): 7 de 9 con k = 5 para BM25 con
variantes y para e5 con variantes.

    python pruebas/evaluar_recuperacion.py
"""

from __future__ import annotations

import json

from comun import PRUEBAS, RAIZ, acierta, guardar_json, poliza, preguntas, utf8

from ai import cache_normalizacion, embeddings
from ai.recuperacion import METODOS, top_k

KS = (3, 5, 8)
NOMBRES = {
    "bm25_pregunta": "BM25, pregunta original",
    "bm25_variantes": "BM25, 3-5 variantes normalizadas (respaldo)",
    "emb_pregunta": "Embeddings por API, pregunta original (app)",
    "emb_variantes": "Embeddings por API, mismas variantes",
    "hibrido_variantes": "Híbrido: BM25 + embeddings, mismas variantes",
}


def main() -> int:
    utf8()
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
    con_vectores = embeddings.disponible() and all(poliza(q["poliza"]).indice.con_vectores() for q in preguntas())
    metodos = [m for m in METODOS if con_vectores or m.startswith("bm25")]
    filas, detalle = [], {}
    evaluables = []
    for q in preguntas():
        if q["modo"] == "ninguno":
            continue
        pol = poliza(q["poliza"])
        norm = cache_normalizacion.buscar(q["pregunta"], pol.sha256)
        if norm is None:
            print(f"falta la normalización de {q['id']} en la caché: corre antes python -m ai.preparar_demo")
            return 1
        evaluables.append(q)
        detalle[q["id"]] = {}
        for metodo in metodos:
            ranking = top_k(pol.indice, q["pregunta"], norm["variantes"], norm.get("terminos", []), metodo, max(KS),
                            titulos=norm.get("clausulas"), clausulas=norm.get("clausulas"))
            trozos = [pol.indice.trozos[i] for i, _ in ranking]
            detalle[q["id"]][metodo] = {
                f"k{k}": acierta(trozos[:k], q["esperados"], q["modo"]) for k in KS
            } | {"top5": [f"{t.seccion} › {t.articulo}" for t in trozos[:5]]}

    n = len(evaluables)
    lineas = [
        "# Recuperación: BM25 con variantes frente a embeddings",
        "",
        "Generado por `pruebas/evaluar_recuperacion.py` con las variantes de la caché de normalizaciones (Claude Haiku)."
        + (f" Embeddings: `{embeddings.modelo()}`." if con_vectores else
           " **Sin medir los embeddings por API:** falta VOYAGE_API_KEY o los índices no tienen vectores de ese modelo."),
        "",
        f"{n} de las 10 preguntas tienen un artículo esperado (la P08 es de control: la respuesta",
        "correcta es no encontrar nada, así que no se puede acertar ni fallar en la búsqueda).",
        "Acierta = el artículo esperado está entre los k primeros pasajes (sin repetir textos idénticos).",
        "La app manda al modelo k = 5 (opción A de `pruebas/opciones.md`).",
        "",
        "| Método | " + " | ".join(f"Aciertos con k = {k}" for k in KS) + " |",
        "|---|" + "---:|" * len(KS),
    ]
    for metodo in metodos:
        cuentas = [sum(bool(detalle[q["id"]][metodo][f"k{k}"]) for q in evaluables) for k in KS]
        lineas.append(f"| {NOMBRES[metodo]} | " + " | ".join(f"{c} de {n}" for c in cuentas) + " |")
        filas.append({"metodo": metodo, **{f"k{k}": c for k, c in zip(KS, cuentas)}, "n": n})

    lineas += ["", "## Por pregunta (k = 5)", "", "| Pregunta | " + " | ".join(metodos) + " |", "|---|" + "---|" * len(metodos)]
    for q in evaluables:
        lineas.append(f"| {q['id']} | " + " | ".join("✓" if detalle[q["id"]][m]["k5"] else "✗" for m in metodos) + " |")

    (PRUEBAS / "recuperacion.md").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    guardar_json(PRUEBAS / "recuperacion.json", {"resumen": filas, "detalle": detalle})
    print("\n".join(lineas[2 : 11 + len(metodos)]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

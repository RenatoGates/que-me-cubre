"""Antes y después de anclar la búsqueda al documento, en las 9 preguntas con artículo esperado.

Dos arreglos, medidos por separado y juntos:
1. Normalización anclada (v2): el modelo elige títulos de cláusula y de artículo del índice
   del documento y escribe las variantes con esas palabras. Antes (v1) inventaba vocabulario
   genérico de seguros ("lesión accidental" donde la póliza dice "Accidentes").
2. Peso a los títulos en BM25: cada consulta se busca también en un índice que solo tiene
   los títulos de cada trozo (PESO_TITULO en ai/recuperacion.py).
3. Filtro suave por cláusula: los pasajes de la cláusula que eligió la normalización
   multiplican su puntaje (FACTOR_CLAUSULA); el resto no se excluye. Configuración fijada
   antes de medir: ×2, consultas = variantes + cláusula elegida (los artículos elegidos no se
   usan) y sin peso a títulos. Las demás filas de "suave" son sensibilidad, no la decisión.

Normalizaciones: v1 en pruebas/normalizaciones_v1.json (las de la corrida del 2026-11-07),
v2 en la caché vigente (data/cache/normalizaciones.json). No llama al LLM.

    python pruebas/comparar_normalizacion.py   # escribe pruebas/normalizacion.md y .json
"""

from __future__ import annotations

import json

from comun import PRUEBAS, coincide, guardar_json, poliza, preguntas, utf8

from ai import cache_normalizacion
from ai.indice import titulos_de
from ai.recuperacion import top_k

V1 = PRUEBAS / "normalizaciones_v1.json"
K_APP = 5
# nombre, normalización, peso a títulos, títulos como consultas, factor de cláusula, etiqueta
CONFIGS = [
    ("antes", "v1", 0.0, None, 1.0, "Antes: normalización v1, BM25 solo en el texto"),
    ("solo_titulos", "v1", 1.0, None, 1.0, "Solo arreglo 2: v1 + peso a títulos"),
    ("solo_anclada", "v2", 0.0, "titulos", 1.0, "Solo arreglo 1: normalización anclada, BM25 solo en el texto"),
    ("despues", "v2", 1.0, "titulos", 1.0, "Arreglos 1 + 2: normalización anclada + peso a títulos"),
    ("suave_x2", "v2", 0.0, "clausulas", 2.0, "**Filtro suave ×2** (fijado antes de medir)"),
    ("suave_x3", "v2", 0.0, "clausulas", 3.0, "Sensibilidad: filtro suave ×3"),
    ("suave_x5", "v2", 0.0, "clausulas", 5.0, "Sensibilidad: filtro suave ×5"),
    ("duro", "v2", 0.0, "clausulas", 1e6, "Referencia: filtro duro (solo la cláusula elegida arriba)"),
    ("suave_x2_titulos", "v2", 1.0, "clausulas", 2.0, "Sensibilidad: filtro suave ×2 + peso a títulos"),
    ("suave_x2_articulos", "v2", 0.0, "titulos", 2.0, "Sensibilidad: filtro suave ×2 usando también los artículos elegidos"),
]


def normalizaciones_v1() -> dict:
    return json.loads(V1.read_text(encoding="utf-8"))


def norm(version: str, q: dict, v1: dict) -> dict | None:
    sha = poliza(q["poliza"]).sha256
    if version == "v2":
        return cache_normalizacion.buscar(q["pregunta"], sha)
    e = v1.get(cache_normalizacion.clave(q["pregunta"], sha))
    return {"variantes": e["variantes"], "terminos": e["terminos"], "titulos": None, "clausulas": None} if e else None


def main() -> int:
    utf8()
    v1 = normalizaciones_v1()
    evaluables = [q for q in preguntas() if q["modo"] != "ninguno"]
    detalle: dict[str, dict] = {}
    faltan = []
    for q in evaluables:
        pol = poliza(q["poliza"])
        detalle[q["id"]] = {}
        for nombre, version, peso, consultas_titulo, factor, _ in CONFIGS:
            n = norm(version, q, v1)
            if n is None:
                faltan.append(f"{q['id']} ({version})")
                continue
            titulos = n.get(consultas_titulo) if consultas_titulo else None
            ranking = top_k(pol.indice, q["pregunta"], n["variantes"], n.get("terminos", []), "bm25_variantes", 60,
                            titulos, peso, n.get("clausulas"), factor)
            trozos = [pol.indice.trozos[i] for i, _ in ranking]
            puestos = [next((r + 1 for r, t in enumerate(trozos) if coincide(t, e)), None) for e in q["esperados"]]
            # "todos": cuenta el peor puesto; "alguno": el mejor
            validos = [p for p in puestos if p is not None]
            if q["modo"] == "todos":
                clave = max(puestos) if None not in puestos else None
            else:
                clave = min(validos) if validos else None
            detalle[q["id"]][nombre] = {
                "puestos": puestos,
                "puesto": clave,
                "top5": clave is not None and clave <= K_APP,
                "top8": clave is not None and clave <= 8,
                "primeros5": [" › ".join(titulos_de(t)) for t in trozos[:K_APP]],
            }
    if faltan:
        print("faltan normalizaciones:", ", ".join(faltan), "· corre python -m ai.preparar_demo")
        return 1

    n = len(evaluables)
    lineas = [
        "# Normalización anclada al documento y peso a títulos: antes y después",
        "",
        "Generado por `pruebas/comparar_normalizacion.py` (sin LLM). Puesto = lugar del artículo",
        "esperado en el ranking, sin repetir textos idénticos; en P02 se piden dos artículos y cuenta",
        f"el peor. La app manda al modelo los {K_APP} primeros.",
        "",
        "Una sola normalización por pregunta y versión: el modelo no es determinista, así que un",
        "puesto puede cambiar de una corrida a otra.",
        "",
        "| Configuración | En los 5 primeros | En los 8 primeros | P01 | P02 |",
        "|---|---:|---:|---:|---:|",
    ]
    resumen = []
    for nombre, version, peso, _, factor, etiqueta in CONFIGS:
        c5 = sum(detalle[q["id"]][nombre]["top5"] for q in evaluables)
        c8 = sum(detalle[q["id"]][nombre]["top8"] for q in evaluables)
        p01 = detalle["P01"][nombre]["puesto"]
        p02 = detalle["P02"][nombre]["puestos"]
        lineas.append(f"| {etiqueta} | {c5} de {n} | {c8} de {n} | {p01 or '—'} | {' y '.join(str(p or '—') for p in p02)} |")
        resumen.append({"config": nombre, "normalizacion": version, "peso_titulo": peso, "factor_clausula": factor,
                        "top5": c5, "top8": c8, "n": n, "P01": p01, "P02": p02})

    lineas += ["", "## Puesto del artículo esperado por pregunta", "",
               "| Pregunta | " + " | ".join(c[0] for c in CONFIGS) + " |", "|---|" + "---:|" * len(CONFIGS)]
    for q in evaluables:
        celdas = []
        for nombre, *_ in CONFIGS:
            d = detalle[q["id"]][nombre]
            txt = " y ".join(str(p or "—") for p in d["puestos"])
            celdas.append(f"**{txt}**" if d["top5"] else txt)
        lineas.append(f"| {q['id']} | " + " | ".join(celdas) + " |")
    lineas += ["", "En negrita: dentro de los 5 pasajes que recibe el modelo.", "",
               "## Títulos que eligió la normalización anclada", ""]
    for q in evaluables:
        e = cache_normalizacion.buscar(q["pregunta"], poliza(q["poliza"]).sha256)
        lineas.append(f"- **{q['id']}** cláusulas: {' · '.join(e['clausulas'])} — artículos: {' · '.join(e['articulos'])}")

    (PRUEBAS / "normalizacion.md").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    guardar_json(PRUEBAS / "normalizacion.json", {"resumen": resumen, "detalle": detalle})
    print("\n".join(lineas[9 : 11 + len(CONFIGS)]))
    print("\n".join(lineas[12 + len(CONFIGS) : 15 + len(CONFIGS) + len(evaluables)]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

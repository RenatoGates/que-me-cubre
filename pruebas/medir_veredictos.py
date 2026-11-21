"""Veredictos de las 10 preguntas antes y después de exigir un límite concreto para «con límites».

Antes: pruebas/salidas_antes_veredicto/ (las salidas con el prompt anterior, guardadas tal cual).
Después: dos corridas del prompt final con Claude Haiku, al primer intento: la primera guardada
en pruebas/salidas_corrida_1/ y la segunda en pruebas/salidas/ (correr_pruebas.py --rehacer).

    python pruebas/medir_veredictos.py      # escribe pruebas/veredictos.md; código 1 si más de la mitad sigue en «con límites»
"""

from __future__ import annotations

import json
from collections import Counter

from comun import PRUEBAS, utf8

NOMBRE = {"si": "Cubre", "con_limites": "Cubre con límites", "no": "No cubre", "no_encontrado": "No está en tu póliza",
          "fuera_de_alcance": "Fuera de alcance"}


def leer(carpeta: str) -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted((PRUEBAS / carpeta).glob("P*.json"))}


def main() -> int:
    utf8()
    antes, primera, despues = leer("salidas_antes_veredicto"), leer("salidas_corrida_1"), leer("salidas")
    ca, c1, cd = (Counter(r["cubre"] for r in x.values()) for x in (antes, primera, despues))
    filas = [f"| {NOMBRE[k]} | {ca.get(k, 0)} | {c1.get(k, 0)} | {cd.get(k, 0)} |" for k in NOMBRE if ca.get(k) or c1.get(k) or cd.get(k)]
    detalle = []
    for i, r in despues.items():
        limite = (r.get("limite") or {}).get("descripcion") or "—"
        detalle.append(f"| {i} | {NOMBRE[antes[i]['cubre']]} | {NOMBRE[primera[i]['cubre']]} | {NOMBRE[r['cubre']]} | {limite} | "
                       f"{r.get('razonamiento') or '—'} |")
    ajustados = sum(1 for r in despues.values() if r.get("veredicto_ajustado"))
    con_limites = max(cd.get("con_limites", 0), c1.get("con_limites", 0))
    texto = ["# Veredictos antes y después", "",
             "Generado por `pruebas/medir_veredictos.py`. Antes: el prompt anterior. Después: «con límites» exige un límite",
             "concreto escrito en una cita (si el modelo no lo da, el código lo pasa a «cubre»), y cada respuesta trae un",
             "razonamiento corto. Claude Haiku, primer intento.", "",
             "| Veredicto | Antes | Después, corrida 1 | Después, corrida 2 |", "|---|---:|---:|---:|", *filas, "",
             f"- «Con límites» después: **{c1.get('con_limites', 0)} y {con_limites} de {len(despues)}**"
             f"{' (más de la mitad: algo sigue mal)' if con_limites > len(despues) / 2 else ''}.",
             f"- Veredictos que el código tuvo que pasar de «con límites» a «cubre» por no traer límite citado: {ajustados}.", "",
             "| # | Antes | Corrida 1 | Corrida 2 | Límite concreto (corrida 2) | Razonamiento (corrida 2) |",
             "|---|---|---|---|---|---|", *detalle, ""]
    (PRUEBAS / "veredictos.md").write_text("\n".join(texto), encoding="utf-8")
    print("\n".join(texto[:12]))
    return 1 if con_limites > len(despues) / 2 else 0


if __name__ == "__main__":
    raise SystemExit(main())

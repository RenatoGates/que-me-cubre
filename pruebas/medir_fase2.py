"""Mide las funciones de la Fase 2 con el modelo real y escribe pruebas/fase2.md.

- Triage: ¿repregunta en las preguntas vagas?, ¿deja pasar las claras?, ¿separa las que traen
  varias? (pruebas/preguntas_fase2.json y, de control, las 10 de pruebas/preguntas.json).
- Pasos para reclamar en los cinco condicionados: plazos aceptados (con el número en su
  cita), elementos con cita verificada, costo y tiempo.
- Radiografías versionadas: qué trae cada una.
- Superposiciones entre Chubb, Pacífico y Rimac.

    python pruebas/medir_fase2.py     # llama a Claude: cuesta centavos
"""

from __future__ import annotations

import json
import statistics
from datetime import date

from comun import PRUEBAS, RAIZ, guardar_json, poliza, preguntas, utf8


def main() -> int:
    utf8()
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
    from ai import consulta, pasos, radiografia
    from ai.llm import obtener_proveedor
    from backend import almacen

    prov = obtener_proveedor()
    datos = json.loads((PRUEBAS / "preguntas_fase2.json").read_text(encoding="utf-8"))
    L = ["# Funciones de la Fase 2, medidas", "",
         f"Generado por `pruebas/medir_fase2.py` con `{prov.modelos['respuesta']}`. Una corrida por caso.", ""]
    detalle: dict = {}

    # --- Triage ---
    filas, usos = [], []

    def clasificar(grupo: str, texto: str, espera_falta: bool, espera_n: int) -> None:
        a, uso = consulta.triage(texto, prov)
        n = len(a["preguntas"])
        ok = a["falta_informacion"] == espera_falta and (espera_falta or n == espera_n) and a["error"] is None
        filas.append((grupo, texto, a["falta_informacion"], n, ok, a["repreguntas"]))
        if uso:
            usos.append(uso)
        print(f"{'✓' if ok else '✗'} {grupo}: {texto[:70]} → falta={a['falta_informacion']} preguntas={n}")

    for t in datos["vagas"]:
        clasificar("vaga", t, True, 1)
    for t in datos["claras"] + [q["pregunta"] for q in preguntas()]:
        clasificar("clara", t, False, 1)
    for v in datos["varias"]:
        clasificar("varias", v["texto"], False, v["preguntas"])
    detalle["triage"] = [{"grupo": g, "texto": t, "falta": f, "preguntas": n, "ok": ok, "repreguntas": r} for g, t, f, n, ok, r in filas]

    def cuenta(grupo: str) -> str:
        del_grupo = [f for f in filas if f[0] == grupo]
        return f"{sum(f[4] for f in del_grupo)} de {len(del_grupo)}"

    L += ["## Repregunta y varias preguntas (triage)", "",
          f"- Preguntas vagas en las que repregunta en vez de responder: **{cuenta('vaga')}**.",
          f"- Preguntas claras que deja pasar sin repreguntar ni partir: **{cuenta('clara')}**.",
          f"- Textos con varias preguntas separados en el número esperado: **{cuenta('varias')}**.",
          f"- Costo del paso: USD {statistics.mean(u.costo_usd for u in usos):.5f} en promedio; "
          f"tiempo: {statistics.mean(u.segundos for u in usos):.1f} s en promedio, {max(u.segundos for u in usos):.1f} s el más largo.",
          "", "| Grupo | Texto | ¿Repregunta? | Preguntas | ¿Como se esperaba? |", "|---|---|---|---:|---|"]
    L += [f"| {g} | {t} | {'sí' if f else 'no'} | {n} | {'sí' if ok else '**no**'} |" for g, t, f, n, ok, _ in filas]

    # --- Pasos ---
    L += ["", "## Qué hacer ahora: pasos y plazo", "",
          "Situación: «Tuve un accidente durante el viaje», con fecha del hecho 2026-11-10. Un plazo se acepta solo si su "
          "número está escrito en su cita, y cada elemento, solo si su cita está en su página del PDF.", "",
          "| Póliza | Plazos aceptados | Fecha límite del primero | A quién avisar | Documentos | Pasos | Citas | Descartes | USD | Segundos |",
          "|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    detalle["pasos"] = {}
    for doc_id in almacen.fuentes():
        r = pasos.que_hacer(poliza(doc_id), "Tuve un accidente durante el viaje", date(2026, 11, 10), prov)
        plazos = "; ".join(f"{p['cantidad']} {p['unidad']} ({p['para']}), pág. {next(c['pagina'] for c in r['citas'] if c['n'] == p['cita'])}"
                           for p in r["plazos"]) or "ninguno"
        limite = r["plazos"][0]["calculo"]["fecha_limite"] if r["plazos"] else "—"
        L.append(f"| {doc_id} | {plazos} | {limite} | {len(r['a_quien_avisar'])} | {len(r['documentos'])} | {len(r['pasos'])} | "
                 f"{len(r['citas'])} | {len(r.get('descartes', []))} | {r['uso']['costo_usd']:.4f} | {r['uso']['segundos']:.1f} |")
        detalle["pasos"][doc_id] = {k: r.get(k) for k in ("modo", "plazos", "a_quien_avisar", "documentos", "pasos", "descartes", "uso")}
        print(f"pasos {doc_id}: {r['modo']} · plazos: {plazos} · {r['uso']['segundos']} s")

    # --- Radiografías ---
    L += ["", "## Radiografía de cada condicionado", "",
          "Las versionadas en `data/cache/radiografias/` (`python -m ai.radiografia`). Cada punto lleva citas verificadas contra el PDF; "
          "es un resumen de los pasajes revisados, no la póliza entera.", "",
          "| Póliza | Coberturas | Con monto escrito | Exclusiones | Deducibles | Carencias | Citas | Mencionado pero ausente | USD | Segundos |",
          "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|"]
    radios = {}
    for doc_id in almacen.fuentes():
        rg = radiografia.guardada(doc_id)
        radios[doc_id] = rg
        L.append(f"| {doc_id} | {len(rg['coberturas'])} | {sum(1 for c in rg['coberturas'] if c['limite'])} | {len(rg['exclusiones'])} | "
                 f"{len(rg['deducibles'])} | {len(rg['carencias'])} | {len(rg['citas'])} | {len(rg['mencionadas_ausentes'])} | "
                 f"{rg['uso']['costo_usd']:.4f} | {rg['uso']['segundos']:.1f} |")

    # --- Superposiciones ---
    ids = ["chubb_viajes_jetsmart", "pacifico_viajes", "rimac_viajes"]
    r = radiografia.superposiciones([(almacen.fuentes()[i]["aseguradora"], radios[i]) for i in ids], prov)
    detalle["superposiciones"] = r
    L += ["", "## ¿Estás pagando doble?", "",
          f"Comparando las radiografías de Chubb, Pacífico y Rimac (los tres son seguros de viaje): **{len(r['pares'])} posibles "
          f"superposiciones**, USD {r.get('uso', {}).get('costo_usd', 0):.4f}, {r.get('uso', {}).get('segundos', 0):.1f} s. "
          "Cada lado es una cobertura de la radiografía, con sus citas verificadas; el porqué lo redacta el modelo y no está verificado.", "",
          "| Póliza A | Cobertura | Póliza B | Cobertura | Por qué (modelo) |", "|---|---|---|---|---|"]
    L += [f"| {p['a']['poliza']} | {p['a']['cobertura']} | {p['b']['poliza']} | {p['b']['cobertura']} | {p['por_que']} |" for p in r["pares"]]

    (PRUEBAS / "fase2.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    guardar_json(PRUEBAS / "fase2.json", detalle)
    print("\nResumen en pruebas/fase2.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

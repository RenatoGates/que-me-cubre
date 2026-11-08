"""¿Sale lo mismo cada vez? Repite la consulta completa de una pregunta N veces.

La búsqueda es determinista (misma normalización en caché -> mismos pasajes -> mismo
mensaje al modelo); la respuesta del modelo no. Este script mide cuánto varía: veredicto,
si es aceptable según pruebas/preguntas.json, qué citas sobreviven a la verificación y qué
se recorta del texto libre.

    python pruebas/medir_estabilidad.py --veces 5 P02 P01    # en ese orden; P02 primero

Cada intento se guarda en pruebas/estabilidad/<id>_<n>.json (los que ya existen no se
repiten) y el resumen en pruebas/estabilidad.md. Usa el mismo flujo que la app (responder)
y espera los límites del plan gratuito en vez de fallar.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time

from comun import PRUEBAS, RAIZ, ProveedorPaciente, guardar_json, poliza, preguntas, utf8

from ai.llm import ErrorLLM, obtener_proveedor
from ai.respuesta import responder

CARPETA = PRUEBAS / "estabilidad"
TPM = 8000
ETIQUETA = {"si": "sí", "no": "no", "con_limites": "con límites", "no_encontrado": "no encontrado", None: "sin respuesta"}


def aceptable(q: dict, r: dict) -> bool:
    exige = q.get("debe_mencionar_no_incluido")
    return r["cubre"] in q["veredictos_aceptables"] and (
        not exige or any(exige in m["nombre"] for m in r["no_incluido_en_documento"]))


def resumen(qs: list[dict], veces: int) -> str:
    lineas = [
        "# Estabilidad de la respuesta: la misma pregunta varias veces",
        "",
        "Generado por `pruebas/medir_estabilidad.py`. Misma normalización (caché), mismos pasajes",
        "y mismo mensaje al modelo en cada intento; lo que cambia es lo que el modelo genera.",
        "*Aceptable* es el criterio de `pruebas/preguntas.json`, fijado antes de correr nada.",
        "",
    ]
    for q in qs:
        intentos = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(CARPETA.glob(f"{q['id']}_*.json"))][:veces]
        if not intentos:
            continue
        completos = [r for r in intentos if r["modo"] == "completo"]
        mensajes = {r["estabilidad"]["huella_pasajes"] for r in intentos}
        respuestas = {r["respuesta"] for r in completos}
        lineas += [
            f"## {q['id']}: {q['pregunta']}",
            "",
            f"- Aceptables: **{sum(aceptable(q, r) for r in completos)} de {len(intentos)}**"
            + (f" ({len(intentos) - len(completos)} sin texto generado)" if len(completos) < len(intentos) else ""),
            f"- Pasajes enviados al modelo: {'idénticos en todos los intentos' if len(mensajes) == 1 else f'{len(mensajes)} combinaciones distintas'}",
            f"- Respuestas distintas: {len(respuestas)} de {len(completos)}",
            f"- Qué debería pasar: {q['que_deberia_pasar']}",
            "",
            "| Intento | Veredicto | ¿Aceptable? | Citas válidas / propuestas | Signo final ignorado | No incluido | "
            "Podrían aplicar | Oraciones recortadas | Tokens |",
            "|---:|---|---|---:|---:|---|---:|---:|---:|",
        ]
        for n, r in enumerate(intentos, 1):
            if r["modo"] != "completo":
                lineas.append(f"| {n} | sin respuesta ({r.get('error', '?')}: {r['aviso'][:60]}…) | **no** | — | — | — | — | — | — |")
                continue
            ignorados = sum(bool(c["verificacion"].get("puntuacion_final_ignorada")) for c in r["citas"])
            recortes = sum(d["tipo"] == "texto" for d in r["descartes"])
            lineas.append(
                f"| {n} | {ETIQUETA[r['cubre']]} | {'sí' if aceptable(q, r) else '**no**'} | "
                f"{len(r['citas'])} / {len(r['modelo_crudo']['citas'])} | {ignorados} | "
                f"{'; '.join(m['nombre'] for m in r['no_incluido_en_documento']) or '—'} | {len(r.get('podrian_aplicar', []))} | "
                f"{recortes} | {r['uso']['tokens']} |"
            )
        lineas += ["", "Respuestas:", ""]
        for n, r in enumerate(intentos, 1):
            sin_texto = f"(sin texto generado: {r.get('error', '?')})"
            lineas.append(f"{n}. {r['respuesta'] or sin_texto}")
        lineas.append("")
    return "\n".join(lineas) + "\n"


def main() -> int:
    utf8()
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
    p = argparse.ArgumentParser()
    p.add_argument("ids", nargs="+")
    p.add_argument("--veces", type=int, default=5)
    a = p.parse_args()
    todas = {q["id"]: q for q in preguntas()}
    qs = [todas[i] for i in a.ids]
    proveedor = ProveedorPaciente(obtener_proveedor())
    for q in qs:
        pol = poliza(q["poliza"])
        for n in range(1, a.veces + 1):
            ruta = CARPETA / f"{q['id']}_{n}.json"
            if ruta.exists():
                continue
            try:
                r = responder(q["pregunta"], pol, proveedor)
            except ErrorLLM as e:
                print(f"{q['id']} intento {n}: ✗ {e}", flush=True)
                return 1
            if not r["uso"]["normalizacion_desde_cache"]:
                print(f"{q['id']}: la normalización no vino de la caché; corre antes python -m ai.preparar_demo")
                return 1
            r["estabilidad"] = {
                "intento": n,
                "huella_pasajes": hashlib.sha256(json.dumps([x["trozo_id"] for x in r["pasajes"]]).encode()).hexdigest()[:16],
            }
            guardar_json(ruta, r)
            print(f"{q['id']} intento {n}: {ETIQUETA[r['cubre']] if r['modo'] == 'completo' else 'sin texto (' + r.get('error', '?') + ')':<14} "
                  f"aceptable={'sí' if r['modo'] == 'completo' and aceptable(q, r) else 'NO'} "
                  f"citas {len(r['citas'])}/{len(r.get('modelo_crudo', {}).get('citas', []))} · {r['uso']['tokens']} tokens", flush=True)
            time.sleep(r["uso"]["tokens"] * 60 / TPM)
        (PRUEBAS / "estabilidad.md").write_text(resumen(qs, a.veces), encoding="utf-8", newline="\n")
        hechos = [json.loads(x.read_text(encoding="utf-8")) for x in sorted(CARPETA.glob(f"{q['id']}_*.json"))][: a.veces]
        print(f"== {q['id']}: aceptables {sum(r['modo'] == 'completo' and aceptable(q, r) for r in hechos)} de {len(hechos)}", flush=True)
    print("Resumen en pruebas/estabilidad.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

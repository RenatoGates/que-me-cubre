"""Corre el flujo completo sobre pruebas/preguntas.json y guarda cada salida en pruebas/salidas/.

    python pruebas/correr_pruebas.py            # solo las que no tienen salida guardada
    python pruebas/correr_pruebas.py --rehacer  # todas de nuevo
    python pruebas/correr_pruebas.py --solo P02

    python pruebas/correr_pruebas.py --rehacer --esfuerzo low --salidas salidas_low --resumen resultados_low.md

Usa el proveedor de QMC_PROVEEDOR (claude por defecto) con su clave en .env. Antes normaliza
las preguntas que falten en la caché versionada (data/cache/), así las pruebas y el demo
usan exactamente las mismas variantes y cada respuesta gasta una sola llamada.

Ritmo: solo con Groq, después de cada pregunta espera lo que el plan gratuito tarda en
reponer los tokens que gastó (8000 por minuto). Con Claude, de pago por token, no hay espera.

Primer intento y reintento: si una respuesta sale sin texto generado, el script reintenta
una vez para poder avanzar, pero guarda lo que pasó en el primer intento ("primer_intento"
en la salida) y el resumen da los dos números por separado. El que cuenta es el del primer
intento: la app no reintenta, eso es lo que vive el usuario. Esperar un límite de Groq
(ProveedorPaciente) no es un reintento: un 429 no genera nada ni gasta tokens.
"""

from __future__ import annotations

import argparse
import json
import statistics
import time

from comun import PRUEBAS, RAIZ, ProveedorPaciente, aceptable, apertura_txt, bloque_txt, guardar_json, poliza, preguntas, utf8

from ai import cache_normalizacion
from ai.llm import ErrorLLM, obtener_proveedor
from ai.preparar_demo import asegurar
from ai.respuesta import responder

ETIQUETA = {"si": "sí", "no": "no", "con_limites": "con límites", "no_encontrado": "no encontrado",
            "fuera_de_alcance": "fuera de alcance", None: "sin respuesta"}
TPM = 8000  # tokens por minuto del plan gratuito de Groq (cabecera x-ratelimit-limit-tokens)
ESPERA_REINTENTO = 60  # s: con el balde vacío, en un minuto se repone entero


def resumen_md(filas: list[dict], proveedor: str, modelo: str, precios: tuple[float, float], nota: str) -> str:
    lineas = [
        "# Resultados de las 10 preguntas",
        "",
        f"Proveedor: {proveedor} · modelo: `{modelo}` · {nota} · precio USD {precios[0]:g} por millón de tokens de "
        f"entrada y {precios[1]:g} de salida.",
        "Generado por `pruebas/correr_pruebas.py`. Cada salida completa (variantes de la normalización,",
        "pasajes, respuesta cruda del modelo, citas verificadas y descartes) está en `pruebas/salidas/`.",
        "",
        "Tokens: entrada + salida (la salida incluye el razonamiento del modelo, que Claude no informa",
        "por separado: sale 0). *Normalización* es lo que costó generar la entrada",
        "de la caché: una pregunta nueva en vivo lo gasta además de la respuesta.",
        "",
        "*Mencionadas pero ausentes* es el bloque que calcula el código (ai/referencias.py), sin el modelo;",
        "*No incluido* es lo que el modelo señaló y sobrevivió a la validación.",
        "",
        "| # | Pregunta | Veredicto | ¿Aceptable? | Citas válidas / propuestas | Mencionadas pero ausentes (código) "
        "| No incluido (modelo) | Pasajes | Normalización | Respuesta: entrada | salida (razonamiento) | Consulta completa | USD consulta completa | Segundos |",
        "|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for f in filas:
        primero = "" if f["primer_intento"] is None else f" (al primer intento: sin texto, {f['primer_intento']})"
        lineas.append(
            f"| {f['id']} | {f['pregunta']} | {ETIQUETA[f['cubre']]} | {'sí' if f['aceptable'] else '**no**'}{primero} | "
            f"{f['citas_validas']} / {f['citas_propuestas']} | {f['ausentes']} | {f['no_incluido'] or '—'} | {f['pasajes']} | "
            f"{f['tokens_normalizacion'] or '—'} | {f['entrada']} | {f['salida']} ({f['razonamiento']}) | "
            f"{f['consulta_completa']} | {f['usd_completa']:.4f} | {f['segundos']:.1f} |"
        )
    n = len(filas)
    if n:
        resp = [f["tokens"] for f in filas]
        completa = [f["consulta_completa"] for f in filas]
        al_primero = sum(f["aceptable"] and f["primer_intento"] is None for f in filas)
        sin_texto = [f"{f['id']} ({f['primer_intento']})" for f in filas if f["primer_intento"] is not None]
        lineas += [
            "",
            f"- **Veredictos aceptables al primer intento: {al_primero} de {n}.** Es el número que cuenta: la app "
            "no reintenta, así que es lo que vive el usuario.",
            f"- Con un reintento del script (solo para avanzar la corrida): {sum(f['aceptable'] for f in filas)} de {n}.",
            f"- Sin texto generado al primer intento: {len(sin_texto)} de {n}"
            + (f": {', '.join(sin_texto)}." if sin_texto else "."),
            f"- Citas propuestas por el modelo: {sum(f['citas_propuestas'] for f in filas)}; "
            f"aceptadas tras verificar contra el pasaje y el PDF: {sum(f['citas_validas'] for f in filas)}.",
            f"- Tokens por respuesta (normalización desde la caché, una llamada): promedio {statistics.mean(resp):.0f}, "
            f"mínimo {min(resp)}, máximo {max(resp)}.",
            f"- Tokens por consulta completa (pregunta nueva, dos llamadas): promedio {statistics.mean(completa):.0f}, "
            f"máximo {max(completa)}.",
            f"- De la salida, razonamiento: {sum(f['razonamiento'] for f in filas) / max(1, sum(f['salida'] for f in filas)):.0%}.",
            f"- Costo por consulta completa (pregunta nueva, dos llamadas): promedio USD "
            f"{statistics.mean(f['usd_completa'] for f in filas):.4f}, máximo USD {max(f['usd_completa'] for f in filas):.4f}.",
            f"- Tiempo por respuesta (sin la normalización): promedio {statistics.mean(f['segundos'] for f in filas):.1f} s, "
            f"máximo {max(f['segundos'] for f in filas):.1f} s.",
            f"- Respuestas que abren con «Sí» o «No» contra el veredicto (ahora se marcan; las salidas "
            "generadas antes de ese cambio las tienen recortadas): "
            f"{sum(f['apertura'] for f in filas)} de {n}.",
        ]
    return "\n".join(lineas) + "\n"


def fila(q: dict, r: dict, precios: tuple[float, float] = (0.0, 0.0)) -> dict:
    vacio = {"tokens_entrada": 0, "tokens_salida": 0, "tokens_razonamiento": 0}
    respuesta = r["uso"]["detalle"][-1] if r["modo"] == "completo" else vacio
    primero = r.get("primer_intento")
    norm = cache_normalizacion.tokens_generacion(q["pregunta"], poliza(q["poliza"]).sha256)
    t_norm = norm["entrada"] + norm["salida"] if norm else 0
    en_cache = len(r["uso"]["detalle"]) <= 1
    usd_norm = (norm["entrada"] * precios[0] + norm["salida"] * precios[1]) / 1e6 if norm and en_cache else 0.0
    return {
        "usd_completa": r["uso"].get("costo_usd", 0.0) + usd_norm,
        "id": q["id"],
        "pregunta": q["pregunta"],
        "cubre": r["cubre"],
        "aceptable": aceptable(q, r),
        "primer_intento": None if primero is None else (primero.get("error_detalle") or primero.get("error") or "?"),
        "citas_propuestas": len((r.get("modelo_crudo") or {}).get("citas", [])),
        "citas_validas": len(r["citas"]),
        "no_incluido": "; ".join(m["nombre"] for m in r["no_incluido_en_documento"]),
        "ausentes": bloque_txt(r),
        "apertura": apertura_txt(r) != "—",
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
    p.add_argument("--esfuerzo", help="esfuerzo de razonamiento de la respuesta (low, medium, high)")
    p.add_argument("--salidas", default="salidas", help="carpeta dentro de pruebas/ para las salidas")
    p.add_argument("--resumen", default="resultados.md")
    args = p.parse_args()
    salidas = PRUEBAS / args.salidas
    try:
        proveedor = ProveedorPaciente(obtener_proveedor())  # espera los límites en vez de fallar
        if args.esfuerzo:
            proveedor._ESFUERZO["respuesta"] = args.esfuerzo
    except ErrorLLM as e:
        print(f"✗ {e}")
        return 1

    todas = preguntas()
    elegidas = [q for q in todas if not args.solo or q["id"] in args.solo]
    con_cuota = proveedor.nombre == "groq"
    espera_reintento = ESPERA_REINTENTO if con_cuota else 2
    pendientes = [q for q in elegidas if args.rehacer or not (salidas / f"{q['id']}.json").exists()]
    if pendientes:
        print("Normalizaciones (caché versionada):")
        nuevas, faltan = asegurar([(q["poliza"], q["pregunta"]) for q in pendientes], proveedor)
        if faltan:
            return 1
        if nuevas and con_cuota:
            time.sleep(ESPERA_REINTENTO)  # las normalizaciones seguidas dejan el balde casi vacío

    filas, problemas = [], []
    for q in todas:
        ruta = salidas / f"{q['id']}.json"
        if q in pendientes:
            print(f"▶ {q['id']}: {q['pregunta']}", flush=True)
            try:
                r = responder(q["pregunta"], poliza(q["poliza"]), proveedor)
                if r["modo"] != "completo":
                    primero = {k: r.get(k) for k in ("modo", "error", "error_detalle")}
                    print(f"  sin texto al primer intento ({r.get('error_detalle') or r.get('error')}); espero "
                          f"{espera_reintento} s y reintento una vez (cuenta como falla al primer intento)", flush=True)
                    time.sleep(espera_reintento)
                    r = responder(q["pregunta"], poliza(q["poliza"]), proveedor)
                    r["primer_intento"] = primero
            except ErrorLLM as e:
                print(f"  ✗ {e}")
                problemas.append(q["id"])
                continue
            if r["modo"] != "completo":  # se guarda igual: cuenta como no aceptable en los dos números
                print(f"  ✗ sin respuesta generada tampoco al reintentar: {r.get('error_detalle') or r['aviso']}")
                problemas.append(q["id"])
            r["prueba"] = {k: q[k] for k in ("id", "poliza", "origen", "veredictos_aceptables", "que_deberia_pasar")}
            guardar_json(ruta, r)
            if con_cuota:
                time.sleep(r["uso"]["tokens"] * 60 / TPM)  # lo que el plan tarda en reponer lo gastado
        elif ruta.exists():
            r = json.loads(ruta.read_text(encoding="utf-8"))
        else:
            continue
        f = fila(q, r, proveedor.precios)
        filas.append(f)
        print(
            f"  {f['id']} {ETIQUETA[f['cubre']]:<14} aceptable={'sí' if f['aceptable'] else 'NO'} "
            f"citas {f['citas_validas']}/{f['citas_propuestas']} · {f['pasajes']} pasajes · "
            f"{f['entrada']}+{f['salida']} ({f['razonamiento']} razon.) = {f['tokens']} tokens "
            f"(+{f['tokens_normalizacion']} normalización) · {f['segundos']:.1f}s"
            + (f" · no incluido: {f['no_incluido']}" if f["no_incluido"] else ""),
            flush=True,
        )

    nota = f"esfuerzo de razonamiento de la respuesta: {getattr(proveedor, '_ESFUERZO', {}).get('respuesta', '—')}"
    (PRUEBAS / args.resumen).write_text(
        resumen_md(filas, proveedor.nombre, proveedor.modelos["respuesta"], proveedor.precios, nota),
        encoding="utf-8", newline="\n"
    )
    print(f"\nResumen en pruebas/{args.resumen}" + (f" · sin completar: {problemas}" if problemas else ""))
    return 1 if problemas else 0


if __name__ == "__main__":
    raise SystemExit(main())

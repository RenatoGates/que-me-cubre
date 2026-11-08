"""¿Cómo recortar tokens por consulta para el límite de 8000 por minuto, y qué se pierde?

Corre la respuesta de las 10 preguntas con una configuración alternativa, con las mismas
normalizaciones de la caché, y resume todas las configuraciones en pruebas/opciones.md.

    python pruebas/comparar_opciones.py importar base_k8          # la corrida de correr_pruebas.py (k = 8)
    python pruebas/comparar_opciones.py correr A_k5 --k 5 --continuar 2 --presupuesto 6500
    python pruebas/comparar_opciones.py correr AB_k5_low --k 5 --continuar 2 --presupuesto 6500 --esfuerzo low
    python pruebas/comparar_opciones.py correr C_20b --modelo openai/gpt-oss-20b
    python pruebas/comparar_opciones.py resumen                   # escribe pruebas/opciones.md

Cada corrida guarda una salida por pregunta en pruebas/opciones/<nombre>/. Gasta cuota real
(unos 35 000 a 70 000 tokens por corrida de 10) y espera lo que el plan tarda en reponer lo
gastado. Las observaciones sueltas (errores 400/413 y el 429 de admisión) están en
pruebas/opciones/sondas.json, copiadas de las salidas de pruebas/medir_cuota.py.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics as st
import time

from comun import PRUEBAS, RAIZ, SALIDAS, acierta, poliza, preguntas, utf8
from simular_cuota import cuantas_entran, delta_minimo

from ai import cache_normalizacion
from ai.prompts import mensaje_respuesta
from ai.recuperacion import pasajes_xml, recuperar, recuperar_normalizada

OPCIONES = PRUEBAS / "opciones"
TPM = 8000
SEPARACION = 36  # s: 5 consultas en 3 minutos
DESCRIPCION = {
    "base_k8": "Actual al medir: k = 8 (+3 continuaciones, 13 000 caracteres), razonamiento medio, 120b",
    "A_k5": "A. Menos pasajes: k = 5 (+2 continuaciones, 6500 caracteres)",
    "AB_k5_low": "A + B. Menos pasajes y razonamiento bajo",
    "C_20b": "C. gpt-oss-20b con la configuración actual",
}
ORDEN = list(DESCRIPCION)
K_OFFLINE = {
    "k = 8 (actual al medir)": dict(k=8, continuar=3, presupuesto_caracteres=13000),
    "k = 6, 8000 caracteres": dict(k=6, continuar=2, presupuesto_caracteres=8000),
    "k = 5, 6500 caracteres (A)": dict(k=5, continuar=2, presupuesto_caracteres=6500),
    "k = 4, 5500 caracteres": dict(k=4, continuar=2, presupuesto_caracteres=5500),
    "k = 3, 4500 caracteres": dict(k=3, continuar=2, presupuesto_caracteres=4500),
}


def _aceptable(q: dict, final: dict) -> bool:
    exige = q.get("debe_mencionar_no_incluido")
    return final["cubre"] in q["veredictos_aceptables"] and (
        not exige or any(exige in m["nombre"] for m in final["no_incluido_en_documento"]))


# ---------------------------------------------------------------------------
# correr / importar
# ---------------------------------------------------------------------------


def correr(a: argparse.Namespace) -> int:
    from dotenv import load_dotenv

    from ai.llm import ErrorLLM, LimiteAlcanzado, ProveedorGroq
    from ai.prompts import ESQUEMA_RESPUESTA, SISTEMA_RESPUESTA
    from ai.respuesta import _validar

    load_dotenv(RAIZ / ".env")
    os.environ["QMC_MODELO"] = a.modelo
    prov = ProveedorGroq()
    prov._ESFUERZO = {**ProveedorGroq._ESFUERZO, "respuesta": a.esfuerzo}
    prov._MAX_TOKENS = {**ProveedorGroq._MAX_TOKENS, "respuesta": a.max_salida}
    carpeta = OPCIONES / a.nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    config = {k: v for k, v in vars(a).items() if k not in ("accion", "solo")}

    for q in preguntas():
        ruta = carpeta / f"{q['id']}.json"
        if (a.solo and q["id"] not in a.solo) or ruta.exists():
            continue
        pol = poliza(q["poliza"])
        norm = cache_normalizacion.buscar(q["pregunta"], pol.sha256)
        if norm is None:
            print(f"{q['id']}: falta la normalización en la caché (python -m ai.preparar_demo)")
            return 1
        pas = recuperar_normalizada(pol.indice, q["pregunta"], norm, k=a.k,
                                    continuar=a.continuar, presupuesto_caracteres=a.presupuesto)
        usuario = mensaje_respuesta(q["pregunta"], norm["hechos"], pol.secciones, pasajes_xml(pas))
        crudo, error = None, None
        for _ in range(3):
            try:
                crudo, uso = prov.json("respuesta", SISTEMA_RESPUESTA, usuario, ESQUEMA_RESPUESTA)
                break
            except LimiteAlcanzado as e:
                print(f"  {q['id']} límite ({e.espera_segundos} s); espero 60 s", flush=True)
                time.sleep(60)
            except ErrorLLM as e:
                error = str(e)
                break
        if crudo is None:
            print(f"  {q['id']} ✗ {error or 'límite alcanzado tres veces'}", flush=True)
            ruta.write_text(json.dumps({"id": q["id"], "config": config, "error": error or "limite"}, ensure_ascii=False),
                            encoding="utf-8")
            time.sleep(60)  # la llamada fallida también pudo gastar cuota
            continue
        final, descartes = _validar(crudo, pas, pol)
        salida = {
            "id": q["id"], "config": config, "cubre": final["cubre"], "aceptable": _aceptable(q, final),
            "recuperacion_acierta": acierta([x.trozo for x in pas], q["esperados"], q["modo"]),
            "citas_validas": len(final["citas"]), "citas_propuestas": len(crudo["citas"]),
            "no_incluido": [m["nombre"] for m in final["no_incluido_en_documento"]],
            "pasajes": len(pas), "chars_usuario": len(usuario), "uso": uso.a_dict(),
            "respuesta": final["respuesta"], "final": final, "crudo": crudo, "descartes": descartes,
        }
        ruta.write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
        total = uso.tokens_entrada + uso.tokens_salida
        print(f"{a.nombre} {q['id']} {final['cubre']:<13} aceptable={'sí' if salida['aceptable'] else 'NO'} "
              f"citas {salida['citas_validas']}/{salida['citas_propuestas']} · {len(pas)} pasajes · "
              f"{uso.tokens_entrada}+{uso.tokens_salida} ({uso.tokens_razonamiento} razon.) = {total}", flush=True)
        time.sleep(total * 60 / TPM)
    return 0


def importar(a: argparse.Namespace) -> int:
    """Copia la corrida de correr_pruebas.py (pruebas/salidas/) al formato de las opciones."""
    carpeta = OPCIONES / a.nombre
    carpeta.mkdir(parents=True, exist_ok=True)
    for q in preguntas():
        r = json.loads((SALIDAS / f"{q['id']}.json").read_text(encoding="utf-8"))
        pol = poliza(q["poliza"])
        por_id = {t.id: t for t in pol.indice.trozos}
        salida = {
            "id": q["id"], "config": {"origen": "pruebas/salidas (correr_pruebas.py)", "k": 8, "continuar": 3,
                                      "presupuesto": 13000, "esfuerzo": "medium", "modelo": r["uso"]["detalle"][-1]["modelo"]},
            "cubre": r["cubre"], "aceptable": _aceptable(q, r),
            "recuperacion_acierta": acierta([por_id[p["trozo_id"]] for p in r["pasajes"]], q["esperados"], q["modo"]),
            "citas_validas": len(r["citas"]), "citas_propuestas": len(r["modelo_crudo"]["citas"]),
            "no_incluido": [m["nombre"] for m in r["no_incluido_en_documento"]],
            "pasajes": len(r["pasajes"]), "uso": r["uso"]["detalle"][-1], "respuesta": r["respuesta"],
            "crudo": r["modelo_crudo"], "descartes": r["descartes"],
        }
        (carpeta / f"{q['id']}.json").write_text(json.dumps(salida, ensure_ascii=False, indent=2) + "\n",
                                                 encoding="utf-8", newline="\n")
    print(f"importadas {len(preguntas())} salidas en {carpeta.relative_to(RAIZ)}")
    return 0


# ---------------------------------------------------------------------------
# resumen
# ---------------------------------------------------------------------------


def _tokens_normalizacion(q: dict) -> tuple[int, int]:
    t = cache_normalizacion.tokens_generacion(q["pregunta"], poliza(q["poliza"]).sha256) or {"entrada": 0, "salida": 0}
    return t["entrada"], t["salida"]


def _cargar(nombre: str) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted((OPCIONES / nombre).glob("P*.json"))]


def resumen(_a: argparse.Namespace) -> int:
    qs = {q["id"]: q for q in preguntas()}
    nombres = [n for n in ORDEN if (OPCIONES / n).is_dir()] + sorted(
        p.name for p in OPCIONES.iterdir() if p.is_dir() and p.name not in ORDEN)
    lineas = [
        "# Recortar tokens por consulta: opciones medidas",
        "",
        "Generado por `pruebas/comparar_opciones.py resumen`. Corridas del 2026-11-07 con las mismas",
        "normalizaciones de la caché (una llamada por respuesta) y `openai/gpt-oss-120b` salvo en C.",
        "",
        f"Meta: 5 consultas en 3 minutos = una cada {SEPARACION} s. En {SEPARACION} s el plan repone "
        f"{SEPARACION * TPM // 60} tokens, así que cada consulta tiene que gastar unos 4800 o menos.",
        "Separación mínima calculada con `pruebas/simular_cuota.py` sobre las 5 consultas más caras de",
        "cada configuración. *Balde recién usado*: alguien acaba de hacer una consulta antes de empezar.",
        "",
        "| Configuración | Aceptables | Citas válidas / propuestas | Pasajes | Entrada | Salida (razonamiento) "
        "| Tokens por respuesta | Pregunta nueva | Separación mínima, en caché | …nuevas | …balde recién usado "
        f"| A {SEPARACION} s con el balde recién usado, entran (de 5) | Errores |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    grilla = {}
    for n in nombres:
        filas = _cargar(n)
        ok = [f for f in filas if "error" not in f]
        errores = len(filas) - len(ok)
        grilla[n] = {f["id"]: f for f in filas}
        if not ok:
            continue
        tot = [f["uso"]["tokens_entrada"] + f["uso"]["tokens_salida"] for f in ok]
        peor = sorted(ok, key=lambda f: -(f["uso"]["tokens_entrada"] + f["uso"]["tokens_salida"]))[:5]
        cache = [[(f["uso"]["tokens_entrada"], f["uso"]["tokens_salida"])] for f in peor]
        nuevas = [[_tokens_normalizacion(qs[f["id"]]), (f["uso"]["tokens_entrada"], f["uso"]["tokens_salida"])] for f in peor]
        sal = sum(f["uso"]["tokens_salida"] for f in ok)
        raz = sum(f["uso"].get("tokens_razonamiento", 0) for f in ok)
        nueva_prom = st.mean(t + sum(_tokens_normalizacion(qs[f["id"]])) for t, f in zip(tot, ok))
        es_20b = any(str(f["config"].get("modelo", "")).endswith("gpt-oss-20b") for f in ok)
        sep = (f"{delta_minimo(cache):.0f} s", f"{delta_minimo(nuevas):.0f} s", f"{delta_minimo(cache, 0):.0f} s",
               f"{cuantas_entran(cache, SEPARACION, 0)}") if not es_20b else ("no aplica",) * 4
        lineas.append(
            f"| {DESCRIPCION.get(n, n)} | {sum(f['aceptable'] for f in ok)} de {len(ok)} | "
            f"{sum(f['citas_validas'] for f in ok)} / {sum(f['citas_propuestas'] for f in ok)} | "
            f"{st.mean(f['pasajes'] for f in ok):.1f} | {st.mean(f['uso']['tokens_entrada'] for f in ok):.0f} | "
            f"{sal / len(ok):.0f} ({raz / max(1, sal):.0%}) | {st.mean(tot):.0f} (máx. {max(tot)}) | {nueva_prom:.0f} | "
            f"{sep[0]} | {sep[1]} | {sep[2]} | {sep[3]} | {errores or '—'} |"
        )
    lineas += [
        "",
        "Con gpt-oss-20b la separación no se puede simular con la regla de 120b: Groq le suma el máximo",
        "de salida (3000) a lo pedido, así que cada llamada necesita casi el balde entero (ver abajo).",
        "",
        "## Veredicto por pregunta",
        "",
        "| Pregunta | " + " | ".join(nombres) + " |",
        "|---|" + "---|" * len(nombres),
    ]
    for qid in qs:
        celdas = []
        for n in nombres:
            f = grilla[n].get(qid)
            if f is None:
                celdas.append("")
            elif "error" in f:
                celdas.append("error")
            else:
                celdas.append(f"{f['cubre']} {'✓' if f['aceptable'] else '✗'}")
        lineas.append(f"| {qid} | " + " | ".join(celdas) + " |")

    lineas += ["", "## Pasajes según k (sin LLM)", "",
               "Lo que de verdad llega al modelo (con continuaciones) y si el artículo esperado está entre",
               "eso, en las 9 preguntas con artículo esperado.", "",
               "| Pasajes | Pasajes promedio | Caracteres del mensaje (prom. / máx.) | Artículo esperado presente | Falla en |",
               "|---|---:|---:|---:|---|"]
    for etiqueta, cfg in K_OFFLINE.items():
        fs = []
        for q in qs.values():
            pol = poliza(q["poliza"])
            norm = cache_normalizacion.buscar(q["pregunta"], pol.sha256)
            pas = recuperar_normalizada(pol.indice, q["pregunta"], norm, **cfg)
            usuario = mensaje_respuesta(q["pregunta"], norm["hechos"], pol.secciones, pasajes_xml(pas))
            fs.append((q["id"], len(pas), len(usuario), acierta([p.trozo for p in pas], q["esperados"], q["modo"])))
        ev = [f for f in fs if f[3] is not None]
        lineas.append(f"| {etiqueta} | {st.mean(f[1] for f in fs):.1f} | {st.mean(f[2] for f in fs):.0f} / {max(f[2] for f in fs)} | "
                      f"{sum(f[3] for f in ev)} de {len(ev)} | {', '.join(f[0] for f in ev if not f[3]) or '—'} |")

    sondas = OPCIONES / "sondas.json"
    if sondas.exists():
        lineas += ["", "## Observaciones sueltas", ""]
        for s in json.loads(sondas.read_text(encoding="utf-8")):
            lineas.append(f"- **{s['modelo']}**, {s['prueba']}: {s['resultado']}. {s.get('mensaje', '')}".rstrip())

    (PRUEBAS / "opciones.md").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lineas[9 : 11 + len(nombres)]))
    return 0


def main() -> int:
    utf8()
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="accion", required=True)
    c = sub.add_parser("correr")
    c.add_argument("nombre")
    c.add_argument("--k", type=int, default=8)
    c.add_argument("--continuar", type=int, default=3)
    c.add_argument("--presupuesto", type=int, default=13000)
    c.add_argument("--esfuerzo", default="medium")
    c.add_argument("--max-salida", type=int, default=3000)
    c.add_argument("--modelo", default="openai/gpt-oss-120b")
    c.add_argument("--solo", action="append")
    i = sub.add_parser("importar")
    i.add_argument("nombre", nargs="?", default="base_k8")
    sub.add_parser("resumen")
    a = p.parse_args()
    return {"correr": correr, "importar": importar, "resumen": resumen}[a.accion](a)


if __name__ == "__main__":
    raise SystemExit(main())

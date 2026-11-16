"""Prueba el flujo completo contra el backend desplegado (no en local).

Sube el condicionado de Chubb como si fuera la póliza de un usuario, hace las dos preguntas
de Tarapoto, revisa que cada cita venga verificada contra el PDF y con su página, pide el
mapa de Tarapoto y borra la póliza. Gasta 2 consultas reales (centavos) y cuenta para el
tope diario del dispositivo de prueba.

    python pruebas/probar_desplegado.py --url https://que-me-cubre-api.onrender.com
"""

from __future__ import annotations

import argparse
import datetime as dt
import time

import httpx
from comun import PRUEBAS, RAIZ, preguntas, utf8

FALLAS: list[str] = []
LINEAS: list[str] = []


def caso(nombre: str, ok: bool, detalle: object = "") -> None:
    print(f"{'✓' if ok else '✗'} {nombre}" + ("" if ok else f"  ({detalle})"))
    LINEAS.append(f"| {nombre} | {'sí' if ok else '**no**'} |")
    if not ok:
        FALLAS.append(nombre)


def main() -> int:
    utf8()
    p = argparse.ArgumentParser()
    p.add_argument("--url", required=True)
    args = p.parse_args()
    url = args.url.rstrip("/")
    api = httpx.Client(base_url=url, timeout=180, headers={"X-Dispositivo": f"prueba-desplegado-{dt.date.today():%Y%m%d}"})

    info = api.get("/info").json()
    caso("el servidor responde y usa Claude Haiku con embeddings de Voyage",
         info["proveedor"] == "claude" and bool(info["embeddings"]), info)

    pdf = (RAIZ / "data" / "polizas" / "chubb_viajes_jetsmart.pdf").read_bytes()
    t0 = time.perf_counter()
    r = api.post("/polizas", files=[("archivos", ("mi_poliza.pdf", pdf, "application/pdf"))])
    t_subida = time.perf_counter() - t0
    poliza = r.json()
    caso("subir un PDF de 62 páginas: indexado con embeddings",
         r.status_code == 201 and poliza.get("paginas") == 62 and poliza.get("busqueda") == "emb_pregunta", r.text[:300])

    filas = []
    for q in [x for x in preguntas() if x["id"] in ("P01", "P02")]:
        t0 = time.perf_counter()
        r = api.post("/preguntar", json={"poliza_id": poliza["poliza_id"], "pregunta": q["pregunta"]})
        segundos = time.perf_counter() - t0
        d = r.json()
        citas = d.get("citas", [])
        verificadas = [c for c in citas if c["verificacion"]["en_pasaje"] and (c["verificacion"].get("pdfplumber") or c["verificacion"].get("pypdf"))]
        con_pagina = [c for c in citas if isinstance(c.get("pagina"), int) and c["pagina"] >= 1 and c.get("articulo")]
        caso(f"{q['id']}: veredicto aceptable ({d.get('cubre')})",
             r.status_code == 200 and d.get("modo") == "completo" and d.get("cubre") in q["veredictos_aceptables"],
             (r.status_code, d.get("modo"), d.get("cubre"), d.get("error_detalle")))
        caso(f"{q['id']}: las {len(citas)} citas vienen verificadas contra el PDF y con artículo y página",
             len(citas) > 0 and len(verificadas) == len(citas) and len(con_pagina) == len(citas),
             (len(citas), len(verificadas), len(con_pagina)))
        if q["id"] == "P02":
            caso("P02: B4 aparece en el bloque de lo mencionado pero ausente, con su página",
                 any("B4" in m["nombre"] and m.get("pagina") for m in d.get("mencionadas_ausentes", [])))
        filas.append((q["id"], d.get("cubre"), len(citas), [c["pagina"] for c in citas], d.get("uso", {}).get("costo_usd"), segundos))

    mapa = api.get("/mapa/establecimientos", params={"departamento": "SAN MARTIN", "provincia": "SAN MARTIN", "distrito": "TARAPOTO"}).json()
    caso("mapa: establecimientos de Tarapoto con el aviso de que no es la red de la aseguradora",
         mapa.get("total", 0) > 0 and "no la red" in mapa.get("aviso", ""), str(mapa)[:200])
    caso("borrar la póliza subida", api.delete(f"/polizas/{poliza['poliza_id']}").json() == {"borrada": True})

    lineas = [
        "# Flujo completo contra el backend desplegado",
        "",
        f"Generado por `pruebas/probar_desplegado.py` contra `{url}` el {dt.datetime.now():%Y-%m-%d %H:%M}.",
        "",
        "| Comprobación | ¿Pasa? |",
        "|---|---|",
        *LINEAS,
        "",
        f"Subir e indexar la póliza de 62 páginas en el servidor: {t_subida:.1f} s.",
        "",
        "| Pregunta | Veredicto | Citas verificadas | Páginas citadas | USD | Segundos (ida y vuelta) |",
        "|---|---|---:|---|---:|---:|",
        *[f"| {i} | {c} | {n} | {', '.join(map(str, pags))} | {usd:.4f} | {seg:.1f} |" for i, c, n, pags, usd, seg in filas],
    ]
    (PRUEBAS / "desplegado.md").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    print(f"\n{'Todo bien' if not FALLAS else f'{len(FALLAS)} fallas'}. Resumen en pruebas/desplegado.md")
    return 1 if FALLAS else 0


if __name__ == "__main__":
    raise SystemExit(main())

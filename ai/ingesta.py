"""Ingesta de los condicionados públicos precargados: PDF -> trozos -> índice en disco.

Uso (desde la raíz del repo):

    python -m ai.ingesta                    # procesa todo lo de data/polizas/fuentes.json
    python -m ai.ingesta --descargar        # además baja los PDF que falten desde su URL
    python -m ai.ingesta --solo chubb_viajes_jetsmart --ejemplos 3
    python -m ai.ingesta --sin-embeddings   # solo extracción y troceado (rápido)

Solo para documentos públicos. Las pólizas personales (data/privado/ o subidas en la app)
nunca pasan por aquí: la app las procesa en memoria con las mismas funciones y no guarda nada.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import urllib.request
from pathlib import Path

from ai.extraccion import extraer
from ai.indice import Indice
from ai.troceado import trocear

RAIZ = Path(__file__).resolve().parent.parent
POLIZAS = RAIZ / "data" / "polizas"
INDICES = RAIZ / "data" / "indices"
MANIFIESTO = POLIZAS / "fuentes.json"


def nombre_documento(fuente: dict) -> str:
    return f"{fuente['aseguradora']} · {fuente['producto']}"


def descargar(url: str) -> bytes:
    pedido = urllib.request.Request(url, headers={"User-Agent": "que-me-cubre/ingesta"})
    with urllib.request.urlopen(pedido, timeout=60) as r:
        datos = r.read()
    if not datos.startswith(b"%PDF"):
        raise ValueError("la URL no devolvió un PDF")
    return datos


def obtener_pdf(fuente: dict, permitir_descarga: bool) -> bytes:
    ruta = POLIZAS / fuente["archivo"]
    if ruta.exists():
        return ruta.read_bytes()
    if not permitir_descarga:
        raise FileNotFoundError(f"falta {ruta.relative_to(RAIZ)}; corre con --descargar")
    if not fuente.get("url"):
        raise FileNotFoundError(f"falta {ruta.relative_to(RAIZ)} y no tiene URL: cópialo a mano")
    datos = descargar(fuente["url"])
    esperado = fuente.get("sha256")
    if esperado and hashlib.sha256(datos).hexdigest() != esperado:
        raise ValueError("el PDF descargado no coincide con el sha256 del manifiesto (¿la aseguradora lo cambió?)")
    ruta.write_bytes(datos)
    return datos


def procesar(fuente: dict, permitir_descarga: bool, con_embeddings: bool) -> tuple[Indice, dict]:
    t0 = time.perf_counter()
    datos = obtener_pdf(fuente, permitir_descarga)
    sha = hashlib.sha256(datos).hexdigest()
    aviso_hash = fuente.get("sha256") not in (None, sha)

    doc = extraer(datos)
    if doc.es_escaneado:
        raise ValueError("el PDF no tiene capa de texto en la mayoría de páginas: necesitaría OCR")
    t_extraccion = time.perf_counter() - t0

    documento = nombre_documento(fuente)
    trozos = trocear(doc.bloques, fuente["id"], documento)
    meta = {
        "doc_id": fuente["id"],
        "documento": documento,
        "archivo": fuente["archivo"],
        "sha256_pdf": sha,
        "paginas": doc.paginas_total,
        "paginas_sin_texto": doc.paginas_sin_texto,
        "paginas_dos_columnas": doc.paginas_dos_columnas,
        "membretes_quitados": doc.lineas_quitadas,
        "secciones": list(dict.fromkeys(b.seccion for b in doc.bloques)),
        "n_bloques": len(doc.bloques),
    }
    indice = Indice.construir(trozos, meta, con_embeddings=con_embeddings)
    stats = {
        "id": fuente["id"],
        "paginas": doc.paginas_total,
        "secciones": len(meta["secciones"]),
        "articulos": len(doc.bloques),
        "trozos": len(trozos),
        "partidos": sum(1 for t in trozos if t.partes > 1),
        "max_chars": max((len(t.texto) for t in trozos), default=0),
        "seg_extraccion": round(t_extraccion, 1),
        "seg_total": round(time.perf_counter() - t0, 1),
        "aviso_hash": aviso_hash,
    }
    return indice, stats


def mostrar_ejemplos(indice: Indice, n: int) -> None:
    if n <= 0 or not indice.trozos:
        return
    paso = max(1, len(indice.trozos) // n)
    for t in indice.trozos[::paso][:n]:
        print(f"\n  ── {t.id} · {t.paginas_texto}")
        print(f"     sección:  {t.seccion}")
        print(f"     artículo: {t.articulo}" + (f"  (parte {t.parte} de {t.partes})" if t.partes > 1 else ""))
        print("     texto:    " + t.texto[:400].replace("\n", "\n               ") + ("…" if len(t.texto) > 400 else ""))


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    p = argparse.ArgumentParser(description="Indexa los condicionados públicos de data/polizas/.")
    p.add_argument("--descargar", action="store_true", help="baja los PDF que falten desde su URL")
    p.add_argument("--solo", action="append", help="procesa solo este id (se puede repetir)")
    p.add_argument("--sin-embeddings", action="store_true", help="no calcula embeddings")
    p.add_argument("--ejemplos", type=int, default=0, help="muestra N trozos de ejemplo por documento")
    args = p.parse_args(argv)

    fuentes = json.loads(MANIFIESTO.read_text(encoding="utf-8"))
    if args.solo:
        fuentes = [f for f in fuentes if f["id"] in args.solo]

    fallos = []
    for fuente in fuentes:
        print(f"\n▶ {fuente['id']}: {nombre_documento(fuente)}")
        try:
            indice, s = procesar(fuente, args.descargar, not args.sin_embeddings)
        except Exception as e:  # noqa: BLE001 - se informa y se sigue con el siguiente
            print(f"  ✗ no se pudo procesar: {e}")
            fallos.append(fuente["id"])
            continue
        indice.guardar(INDICES, fuente["id"])
        print(
            f"  {s['paginas']} páginas · {s['secciones']} secciones · {s['articulos']} artículos/numerales"
            f" → {s['trozos']} trozos ({s['partidos']} de artículos partidos, máx. {s['max_chars']} caracteres)"
        )
        print(
            f"  extracción {s['seg_extraccion']} s · total {s['seg_total']} s · "
            f"embeddings: {indice.meta['modelo_embeddings'] or 'no'}"
        )
        if s["aviso_hash"]:
            print("  ⚠ el sha256 del PDF no coincide con el del manifiesto: revisa si cambió el documento")
        mostrar_ejemplos(indice, args.ejemplos)

    print(f"\nÍndices en {INDICES.relative_to(RAIZ)}/" + (f" · fallaron: {', '.join(fallos)}" if fallos else ""))
    return 1 if fallos else 0


if __name__ == "__main__":
    raise SystemExit(main())

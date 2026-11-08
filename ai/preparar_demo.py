"""Prepara la caché de normalizaciones para el ensayo y la demo (se corre a mano, en local).

    python -m ai.preparar_demo           # normaliza las preguntas que falten en la caché
    python -m ai.preparar_demo --listar  # muestra qué hay en la caché

Lee preguntas públicas de data/demo/preguntas_ensayo.json y pruebas/preguntas.json, llama
una vez al LLM por cada pregunta nueva y guarda el resultado en data/cache/normalizaciones.json,
que se versiona para que el demo desplegado lo tenga. La app nunca escribe en ese archivo.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import sys
import time
from pathlib import Path

from ai import cache_normalizacion
from ai.llm import ErrorLLM, LimiteAlcanzado, Proveedor, SalidaInvalida, obtener_proveedor

RAIZ = Path(__file__).resolve().parent.parent
ENSAYO = RAIZ / "data" / "demo" / "preguntas_ensayo.json"
PRUEBAS = RAIZ / "pruebas" / "preguntas.json"
ESPERA_MAXIMA = 65  # s: si el proveedor pide esperar más, se detiene y se vuelve a correr luego


def _sha_documentos() -> dict[str, str]:
    fuentes = json.loads((RAIZ / "data" / "polizas" / "fuentes.json").read_text(encoding="utf-8"))
    return {f["id"]: hashlib.sha256((RAIZ / "data" / "polizas" / f["archivo"]).read_bytes()).hexdigest() for f in fuentes}


def preguntas_publicas() -> list[tuple[str, str]]:
    """(id del documento, pregunta) de ensayo y de pruebas, sin repetir."""
    pares = []
    if ENSAYO.exists():
        pares += [(p["documento"], p["pregunta"]) for p in json.loads(ENSAYO.read_text(encoding="utf-8"))]
    if PRUEBAS.exists():
        pares += [(p["poliza"], p["pregunta"]) for p in json.loads(PRUEBAS.read_text(encoding="utf-8"))]
    return list(dict.fromkeys(pares))


def asegurar(pares: list[tuple[str, str]], proveedor: Proveedor | None = None) -> tuple[int, int]:
    """Normaliza y guarda las que falten. Devuelve (nuevas, pendientes por límite)."""
    from ai.indice import Indice
    from ai.respuesta import normalizar  # evita import circular

    shas = _sha_documentos()
    faltan = [(d, q) for d, q in pares if cache_normalizacion.buscar(q, shas[d]) is None]
    if not faltan:
        return 0, 0
    proveedor = proveedor or obtener_proveedor()
    indices: dict[str, Indice] = {}
    nuevas, saltadas = 0, 0
    for n, (doc, pregunta) in enumerate(faltan):
        if doc not in indices:
            indices[doc] = Indice.cargar(RAIZ / "data" / "indices", doc)
        intentos = 0
        while True:
            try:
                norm, uso = normalizar(pregunta, proveedor, indices[doc])
                break
            except LimiteAlcanzado as e:
                if e.espera_segundos is not None and e.espera_segundos <= ESPERA_MAXIMA:
                    print(f"  límite del plan gratuito: espero {e.espera_segundos:.0f} s", flush=True)
                    time.sleep(e.espera_segundos + 1)
                    continue
                print(f"  límite del plan gratuito: quedan {len(faltan) - n} por normalizar; vuelve a correr más tarde")
                return nuevas, len(faltan) - n + saltadas
            except SalidaInvalida as e:
                intentos += 1
                if intentos < 2:
                    print(f"  {e} Reintento una vez.", flush=True)
                    continue
                norm = None
                break
        if norm is None:
            print(f"  ✗ {doc}: {pregunta} (sin JSON válido; queda pendiente)")
            saltadas += 1
            continue
        if norm["ajuste"]:
            print(f"    ajuste: {norm['ajuste']}")
        cache_normalizacion.guardar(
            {
                cache_normalizacion.clave(pregunta, shas[doc]): {
                    "documento": doc,
                    "sha256_pdf": shas[doc],
                    "pregunta": pregunta,
                    **{k: norm[k] for k in cache_normalizacion.CAMPOS},
                    "ajuste": norm["ajuste"],
                    "proveedor": uso.proveedor,
                    "modelo": uso.modelo,
                    "fecha": dt.date.today().isoformat(),
                    # lo que costó generarla: una pregunta nueva en vivo gasta esto además de la respuesta
                    "tokens": {
                        "entrada": uso.tokens_entrada,
                        "salida": uso.tokens_salida,
                        "razonamiento": uso.tokens_razonamiento,
                    },
                }
            }
        )
        nuevas += 1
        print(f"  ✓ {doc}: {pregunta}  →  {' | '.join(norm['titulos'])}", flush=True)
    return nuevas, saltadas


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--listar", action="store_true")
    args = p.parse_args(argv)

    pares = preguntas_publicas()
    if args.listar:
        shas = _sha_documentos()
        for doc, q in pares:
            print(f"{'✓' if cache_normalizacion.buscar(q, shas[doc]) else '·'} {doc}: {q}")
        return 0
    try:
        nuevas, pendientes = asegurar(pares)
    except ErrorLLM as e:
        print(f"✗ {e}")
        return 1
    print(f"Caché: {nuevas} nuevas, {pendientes} pendientes. Archivo: {cache_normalizacion.RUTA.relative_to(RAIZ)}")
    return 1 if pendientes else 0


if __name__ == "__main__":
    raise SystemExit(main())

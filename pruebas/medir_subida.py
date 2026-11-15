"""Cuánto tarda subir una póliza con embeddings por API (lo que espera quien sube su PDF).

Indexa en memoria el condicionado de Chubb (62 páginas) como lo hace la API al recibirlo:
extracción, troceado, vectores de Voyage e índice. Mide el total, la parte de los
embeddings sola, sus tokens y una consulta. Llama a Voyage: gasta tokens del saldo gratuito.

    python pruebas/medir_subida.py
"""

from __future__ import annotations

import os
import time

from comun import PRUEBAS, RAIZ, utf8


def main() -> int:
    utf8()
    from dotenv import load_dotenv

    load_dotenv(RAIZ / ".env")
    os.environ["QMC_VOYAGE_PACIENTE"] = "0"
    from ai import embeddings, subida
    from ai.indice import embeber_pasajes

    pdf = (RAIZ / "data" / "polizas" / "chubb_viajes_jetsmart.pdf").read_bytes()
    t0 = time.perf_counter()
    poliza = subida.poliza_de_pdfs([("chubb.pdf", pdf)])
    total = time.perf_counter() - t0
    if poliza.indice.vectores is None:
        print("✗ la póliza quedó sin vectores: falta VOYAGE_API_KEY o Voyage rechazó la petición (límite por minuto)")
        return 1
    antes = embeddings.tokens_usados
    t0 = time.perf_counter()
    embeber_pasajes(poliza.indice.trozos)
    solo, tokens = time.perf_counter() - t0, embeddings.tokens_usados - antes
    t0 = time.perf_counter()
    embeddings.embeber(["me rompí el dedo en un accidente, ¿me cubre?"], "query")
    consulta = time.perf_counter() - t0

    n, paginas = len(poliza.indice.trozos), poliza.indice.meta["paginas"]
    lineas = [
        "# Subir una póliza con embeddings",
        "",
        f"Generado por `pruebas/medir_subida.py` con `{embeddings.modelo()}`, en esta máquina, con la cuenta de Voyage "
        "ya con medio de pago (límite normal por minuto).",
        "",
        f"- Subida completa de una póliza de {paginas} páginas ({n} pasajes): extracción, troceado, embeddings e índice: "
        f"**{total:.1f} s**.",
        f"- De eso, los embeddings de los {n} pasajes: {solo:.1f} s y {tokens} tokens.",
        f"- Embedding de una consulta: {consulta:.2f} s.",
        f"- Con el saldo gratuito de Voyage (200 millones de tokens) alcanza para unas {200_000_000 // tokens} pólizas de este tamaño.",
        "",
        "Sin medio de pago, Voyage limita la cuenta a 3 peticiones y 10 000 tokens por minuto: la misma póliza, en lotes "
        "con pausas (`python -m ai.ingesta --paciente`), tardó 400 s el 2026-11-15, y una subida en vivo se queda sin "
        "vectores (se busca con BM25).",
    ]
    (PRUEBAS / "subida.md").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lineas[4:9]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

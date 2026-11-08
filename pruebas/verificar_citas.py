"""Auditoría independiente de las citas guardadas en pruebas/salidas/.

Para cada cita, y para cada mención del bloque "mencionadas pero ausentes": abre el PDF
original desde data/polizas/, lee la(s) página(s) que dice y comprueba que el texto esté
ahí, literal. No usa los trozos ni el índice: solo el
JSON guardado y el PDF. Una cita que cruza de página se acepta si un prefijo está en la
primera página y el resto en la siguiente (entre ambas el PDF tiene pie y membrete).

    python pruebas/verificar_citas.py      # termina con código 1 si alguna cita no coincide
"""

from __future__ import annotations

import io
import json

from comun import PRUEBAS, RAIZ, SALIDAS, fuentes, utf8

from ai.extraccion import texto_de_paginas
from ai.verificacion import _normalizar, fragmentos


def paginas_pdf(pdf: bytes, numeros: list[int]) -> dict[str, dict[int, str]]:
    from pypdf import PdfReader

    lector = PdfReader(io.BytesIO(pdf))
    return {
        "pdfplumber": {n: _normalizar(texto_de_paginas(pdf, [n]))[0] for n in numeros},
        "pypdf": {n: _normalizar(lector.pages[n - 1].extract_text() or "")[0] for n in numeros},
    }


def esta(cita: str, paginas: list[int], textos: dict[int, str]) -> bool:
    """Cada fragmento de la cita está entero en una de sus páginas, o partido entre la
    primera y la segunda (una parte al final de una, el resto en la siguiente)."""
    for frag in fragmentos(cita):
        f = _normalizar(frag)[0]
        if any(f in textos[n] for n in paginas):
            continue
        if len(paginas) >= 2:
            a, b = paginas[0], paginas[1]
            if any(f[:s] in textos[a] and f[s:] in textos[b] for s in range(1, len(f))):
                continue
        return False
    return True


def main() -> int:
    utf8()
    filas, fallas, total, crudas, ignoradas = [], 0, 0, 0, 0
    filas_bloque, fallas_bloque, total_bloque = [], 0, 0
    for ruta in sorted(SALIDAS.glob("P*.json")):
        r = json.loads(ruta.read_text(encoding="utf-8"))
        pdf = (RAIZ / "data" / "polizas" / fuentes()[r["prueba"]["poliza"]]["archivo"]).read_bytes()
        crudas += len(r["modelo_crudo"]["citas"])
        for c in r["citas"]:
            total += 1
            ignoradas += bool(c["verificacion"].get("puntuacion_final_ignorada"))
            textos = paginas_pdf(pdf, c["paginas"])
            ok = {lector: esta(c["texto_literal"], c["paginas"], t) for lector, t in textos.items()}
            valida = any(ok.values())
            fallas += not valida
            filas.append(
                f"| {ruta.stem} | {c['n']} | {c['seccion']} › {c['articulo']} | {c['pagina'] if len(c['paginas']) == 1 else '–'.join(map(str, c['paginas']))} "
                f"| {'✓' if ok['pdfplumber'] else '✗'} | {'✓' if ok['pypdf'] else '✗'} | {'sí' if valida else '**NO**'} "
                f"| {repr(c['verificacion'].get('puntuacion_final_ignorada')) if c['verificacion'].get('puntuacion_final_ignorada') else '—'} |"
            )
        for m in r.get("mencionadas_ausentes", []):
            total_bloque += 1
            textos = paginas_pdf(pdf, m["paginas"])
            ok = {lector: esta(m["mencion"], m["paginas"], t) for lector, t in textos.items()}
            fallas_bloque += not any(ok.values())
            filas_bloque.append(
                f"| {ruta.stem} | {m['nombre']} | {m['seccion']} › {m['articulo']} | {'–'.join(map(str, m['paginas']))} "
                f"| {'✓' if ok['pdfplumber'] else '✗'} | {'✓' if ok['pypdf'] else '✗'} | {'sí' if any(ok.values()) else '**NO**'} |"
            )
        for d in r["descartes"]:
            if d["tipo"] == "cita":
                filas.append(f"| {ruta.stem} | (descartada) | {d['motivo']} | — | — | — | descartada por el flujo | — |")

    md = [
        "# Verificación de citas contra el PDF",
        "",
        "Generado por `pruebas/verificar_citas.py`: abre cada PDF y busca cada cita en la página que dice.",
        "Se comparan los caracteres en orden, ignorando solo espacios, saltos de línea y guiones (como siempre).",
        "La cita que se audita es la que muestra la app: si el flujo le quitó un signo final (. : ; ,) para",
        "encontrarla, la columna lo dice y lo auditado es el texto sin ese signo.",
        "",
        f"- Citas que propuso el modelo: {crudas}",
        f"- Citas que el flujo aceptó y mostró: {total}",
        f"- De esas, encontradas textualmente en su página: {total - fallas} de {total}",
        f"- Con un signo final ignorado: {ignoradas}",
        "",
        "| Prueba | Cita | Sección › artículo | Página | pdfplumber | pypdf | ¿En su página? | Signo final ignorado |",
        "|---|---|---|---|---|---|---|---|",
        *filas,
        "",
        "## Bloque \"mencionadas pero ausentes\"",
        "",
        "Lo calcula el código, no el modelo (ai/referencias.py). Se audita igual: la mención literal",
        "tiene que estar en la página que se muestra.",
        "",
        f"- Menciones mostradas: {total_bloque}; encontradas textualmente en su página: {total_bloque - fallas_bloque} de {total_bloque}",
        "",
        "| Prueba | Referencia | Sección › artículo | Página | pdfplumber | pypdf | ¿En su página? |",
        "|---|---|---|---|---|---|---|",
        *filas_bloque,
    ]
    (PRUEBAS / "verificacion_citas.md").write_text("\n".join(md) + "\n", encoding="utf-8", newline="\n")
    print(f"Citas mostradas: {total} · en su página: {total - fallas} · propuestas por el modelo: {crudas}")
    print(f"Menciones del bloque de ausentes: {total_bloque} · en su página: {total_bloque - fallas_bloque}")
    print("Detalle en pruebas/verificacion_citas.md")
    return 1 if fallas or fallas_bloque else 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Contraste de cada par texto/fondo que usa la app de Android, medido con la fórmula de WCAG 2.

Pide 4,5:1 para texto normal y 3:1 para texto grande (18,66 px en negrita o 24 px) y para
íconos que transmiten información. Los colores salen de movil/lib/tema.dart.

    python pruebas/medir_contraste.py      # escribe pruebas/contraste.md; código 1 si algún par no llega
"""

from __future__ import annotations

import re

from comun import PRUEBAS, RAIZ, utf8


def luminancia(hex_: str) -> float:
    canales = [int(hex_[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    lineal = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in canales]
    return 0.2126 * lineal[0] + 0.7152 * lineal[1] + 0.0722 * lineal[2]


def contraste(a: str, b: str) -> float:
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def main() -> int:
    utf8()
    tema = (RAIZ / "movil" / "lib" / "tema.dart").read_text(encoding="utf-8")
    p = {m.group(1): m.group(2)[2:] for m in re.finditer(r"static const (\w+) = Color\(0x([0-9A-Fa-f]{8})\)", tema)}
    pares = [  # (uso, texto, fondo, mínimo): app de Android y web de Streamlit, con la misma paleta
        ("Texto principal sobre el fondo crema", "texto", "fondo", 4.5),
        ("Texto principal sobre tarjetas", "texto", "superficie", 4.5),
        ("Texto citado sobre su bloque de cita", "texto", "citaFondo", 4.5),
        ("Texto secundario sobre el fondo crema", "textoSecundario", "fondo", 4.5),
        ("Texto secundario sobre tarjetas", "textoSecundario", "superficie", 4.5),
        ("Enlaces y botones de texto sobre el fondo crema", "accion", "fondo", 4.5),
        ("Enlaces y botones de texto sobre tarjetas", "accion", "superficie", 4.5),
        ("Texto blanco de los botones principales (y la banda de la web)", "sobreAccion", "accion", 4.5),
        ("Veredicto «Cubre» sobre el fondo crema", "cubierto", "fondo", 4.5),
        ("Veredicto «Cubre» sobre tarjetas", "cubierto", "superficie", 4.5),
        ("Veredicto «Cubre con límites» y su límite sobre el fondo crema", "parcial", "fondo", 4.5),
        ("Veredicto «Cubre con límites» y su límite sobre tarjetas", "parcial", "superficie", 4.5),
        ("Veredicto «No cubre» sobre el fondo crema", "noCubierto", "fondo", 4.5),
        ("Veredicto «No cubre» sobre tarjetas", "noCubierto", "superficie", 4.5),
        ("Descargo del martillo (ámbar) y «se borra el…»", "parcial", "superficie", 4.5),
        ("Avisos (snackbar): blanco sobre texto oscuro", "superficie", "texto", 4.5),
        ("Etiqueta «bloqueado» de la web sobre su fondo", "texto", "citaFondo", 4.5),
        ("Atribución de OpenStreetMap sobre su recuadro blanco", "texto", "FFFFFF", 4.5),
        # Los avisos amarillos de Streamlit pintan su fondo con el amarillo #FFBD45 al 10 % sobre el crema: #FBF1E1.
        ("Web: texto de los avisos amarillos sobre su fondo", "9A5C00", "FBF1E1", 4.5),
    ]
    # Lo que se cambió de la paleta pedida, y por qué: el par original no llegaba.
    ajustes = [
        ("«Con límites» pedido #B06A00 sobre tarjetas", "B06A00", "superficie"),
        ("«Con límites» pedido #B06A00 sobre el fondo crema", "B06A00", "fondo"),
        ("Web: #A36200 en los avisos amarillos (pasó a #9A5C00 solo ahí)", "parcial", "FBF1E1"),
    ]
    # Pares que no llegan y por eso no se usan: el bloque de cita lleva solo el texto citado.
    evitados = [
        ("Texto secundario sobre el bloque de cita", "textoSecundario", "citaFondo"),
        ("Azul de enlaces sobre el bloque de cita", "accion", "citaFondo"),
    ]
    filas, malos = [], []
    for uso, a, b, minimo in pares:
        ca, cb = p.get(a, a)[-6:], p.get(b, b)[-6:]
        r = contraste(ca, cb)
        ok = r >= minimo
        if not ok:
            malos.append(uso)
        filas.append(f"| {uso} | #{ca.upper()} | #{cb.upper()} | {r:.2f}:1 | {minimo:g}:1 | {'sí' if ok else '**no**'} |")
    def fila(uso: str, a: str, b: str) -> str:
        ca, cb = p.get(a, a)[-6:], p.get(b, b)[-6:]
        return f"| {uso} | #{ca.upper()} | #{cb.upper()} | {contraste(ca, cb):.2f}:1 |"

    texto = ["# Contraste de la paleta clara", "",
             "Generado por `pruebas/medir_contraste.py` con los colores de `movil/lib/tema.dart` (los mismos de la web, "
             "`.streamlit/config.toml`).", "",
             "| Uso | Texto | Fondo | Contraste | Mínimo WCAG | Cumple |", "|---|---|---|---:|---:|---|", *filas, "",
             f"- **{len(pares) - len(malos)} de {len(pares)} pares cumplen.**", "",
             "## Colores ajustados", "", "| Par original | Texto | Fondo | Contraste |", "|---|---|---|---:|",
             *[fila(*x) for x in ajustes], "",
             f"«Con límites» pasó de #B06A00 a #{p['parcial'][-6:].upper()}, un ámbar algo más oscuro que llega a 4,5:1 sobre ambos fondos.", "",
             "## Pares que no llegan y por eso no se usan", "", "| Par | Texto | Fondo | Contraste |", "|---|---|---|---:|",
             *[fila(*x) for x in evitados], "",
             "Sobre el bloque de cita (#F3EDE4) va solo el texto citado, en el color principal; la verificación y el botón "
             "para abrir el PDF van debajo, sobre blanco.", ""]
    (PRUEBAS / "contraste.md").write_text("\n".join(texto), encoding="utf-8")
    print("\n".join(texto))
    return 1 if malos else 0


if __name__ == "__main__":
    raise SystemExit(main())

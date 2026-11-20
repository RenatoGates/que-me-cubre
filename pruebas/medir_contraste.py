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
    cabecera = "16304A"  # inicio del degradado del encabezado de inicio
    pares = [  # (uso, texto, fondo, mínimo)
        ("Texto principal sobre el fondo", "texto", "fondo", 4.5),
        ("Texto principal sobre tarjetas", "texto", "superficie", 4.5),
        ("Texto principal sobre el encabezado", "texto", cabecera, 4.5),
        ("Texto secundario sobre el fondo", "textoSecundario", "fondo", 4.5),
        ("Texto secundario sobre tarjetas", "textoSecundario", "superficie", 4.5),
        ("Texto secundario sobre el encabezado", "textoSecundario", cabecera, 4.5),
        ("Enlaces y botones de texto sobre el fondo", "accion", "fondo", 4.5),
        ("Enlaces y botones de texto sobre tarjetas", "accion", "superficie", 4.5),
        ("Texto de los botones principales", "fondo", "accion", 4.5),
        ("Veredicto «Cubre» (21 px negrita) sobre el fondo", "cubierto", "fondo", 3.0),
        ("Veredicto «Cubre con límites» sobre el fondo", "parcial", "fondo", 3.0),
        ("Veredicto «No cubre» sobre el fondo", "noCubierto", "fondo", 3.0),
        ("«se borra el…» (13 px) sobre el fondo", "parcial", "fondo", 4.5),
        ("Botones de borrar (texto claro) sobre tarjetas", "texto", "superficie", 4.5),
        ("Texto del botón de borrar todo (fondo claro)", "fondo", "texto", 4.5),
        ("Plazo urgente (ámbar) sobre el fondo", "parcial", "fondo", 4.5),
        ("Ícono de verificada sobre el fondo", "cubierto", "fondo", 3.0),
        ("Avisos (snackbar): fondo sobre texto", "fondo", "texto", 4.5),
        ("Atribución de OpenStreetMap sobre su recuadro blanco", "1A1A1A", "FFFFFF", 4.5),
    ]
    filas, malos = [], []
    for uso, a, b, minimo in pares:
        ca, cb = p.get(a, a)[-6:], p.get(b, b)[-6:]
        r = contraste(ca, cb)
        ok = r >= minimo
        if not ok:
            malos.append(uso)
        filas.append(f"| {uso} | #{ca.upper()} | #{cb.upper()} | {r:.2f}:1 | {minimo:g}:1 | {'sí' if ok else '**no**'} |")
    texto = ["# Contraste de la app de Android", "", "Generado por `pruebas/medir_contraste.py` con los colores de `movil/lib/tema.dart`.", "",
             "| Uso | Texto | Fondo | Contraste | Mínimo WCAG | Cumple |", "|---|---|---|---:|---:|---|", *filas, "",
             f"- **{len(pares) - len(malos)} de {len(pares)} pares cumplen.**", ""]
    (PRUEBAS / "contraste.md").write_text("\n".join(texto), encoding="utf-8")
    print("\n".join(texto))
    return 1 if malos else 0


if __name__ == "__main__":
    raise SystemExit(main())

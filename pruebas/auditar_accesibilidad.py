"""Etiquetas de accesibilidad de la app de Android, en el dispositivo conectado por USB.

Recorre las pantallas tocando la app con adb y, en cada una, lee el árbol de accesibilidad
(el mismo que lee TalkBack, con uiautomator). Cuenta los controles que se pueden tocar y revisa
que cada uno tenga una etiqueta (texto o descripción). Necesita la app abierta y la pantalla
desbloqueada, y que el backend responda.

    python pruebas/auditar_accesibilidad.py      # escribe pruebas/accesibilidad.md; código 1 si falta alguna etiqueta
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import time
from pathlib import Path

from comun import PRUEBAS, utf8

ADB = str(Path(os.environ.get("LOCALAPPDATA", "")) / "Android" / "Sdk" / "platform-tools" / "adb.exe")
NODO = re.compile(r"<node ([^>]*)>|<node ([^>]*)/>")


def adb(*args: str) -> str:
    return subprocess.run([ADB, *args], capture_output=True, text=True, encoding="utf-8", errors="replace", check=False).stdout


def arbol() -> list[dict]:
    adb("shell", "uiautomator", "dump", "/sdcard/qmc_ui.xml")
    destino = Path(tempfile.mkdtemp()) / "ui.xml"
    adb("pull", "/sdcard/qmc_ui.xml", str(destino))
    xml = destino.read_text(encoding="utf-8")
    nodos = []
    for m in NODO.finditer(xml):
        attrs = dict(re.findall(r'([\w-]+)="([^"]*)"', m.group(1) or m.group(2)))
        nodos.append(attrs)
    return nodos


def tocar(etiqueta: str, columna: int | None = None) -> bool:
    """Toca el control con esa etiqueta; si no se ve, desplaza la pantalla (o la columna) y busca de nuevo."""
    for _ in range(8):
        for n in arbol():
            if etiqueta.lower() in (n.get("content-desc", "") + n.get("text", "")).lower() and n.get("clickable") == "true":
                x1, y1, x2, y2 = map(int, re.findall(r"\d+", n["bounds"]))
                adb("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
                time.sleep(4)
                return True
        x = str(columna or 1280)
        adb("shell", "input", "swipe", x, "1150", x, "450", "400")
        time.sleep(1)
    return False


def revisar(nombre: str) -> tuple[str, int, list[str]]:
    nodos = [n for n in arbol() if n.get("package") == "com.renatogates.quecubre"]
    if not nodos:
        raise SystemExit(f"{nombre}: la app no está al frente o no se pudo leer la pantalla")
    tocables = [n for n in nodos if n.get("clickable") == "true" or n.get("long-clickable") == "true"]
    # Un campo de texto lleva su etiqueta como "texto de ayuda" de Android, que TalkBack lee y
    # uiautomator no muestra: se cuenta aparte y se comprueba en movil/test/accesibilidad_test.dart.
    campos = [n for n in tocables if n.get("class") == "android.widget.EditText"]
    sin = [n["bounds"] for n in tocables if n not in campos and not (n.get("content-desc") or n.get("text")).strip()]
    return nombre, len(tocables), sin, len(campos)


def main() -> int:
    utf8()
    resultados = []
    adb("shell", "am", "start", "-n", "com.renatogates.quecubre/.MainActivity")
    time.sleep(3)
    resultados.append(revisar("Inicio (Tu póliza)"))
    assert tocar("Chubb Seguros", columna=600), "no encontré el ejemplo de Chubb"
    resultados.append(revisar("Con una póliza elegida"))
    assert tocar("Me torcí el dedo", columna=600), "no encontré la pregunta de ejemplo"
    time.sleep(8)
    resultados.append(revisar("Con una respuesta"))
    assert tocar("Ver esta cláusula en tu póliza", columna=1800), "no encontré el botón de la cita"
    resultados.append(revisar("Cómo encontrar la cláusula en el PDF"))
    adb("shell", "input", "keyevent", "KEYCODE_BACK")
    time.sleep(2)
    assert tocar("Cerca de ti"), "no encontré la pestaña Cerca de ti"
    time.sleep(8)
    resultados.append(revisar("Cerca de ti"))
    assert tocar("Mi cuenta"), "no encontré la pestaña Mi cuenta"
    resultados.append(revisar("Mi cuenta (sin sesión)"))
    filas = [f"| {n} | {t} | {t - len(s) - c} | {c} | {', '.join(s) or '—'} |" for n, t, s, c in resultados]
    faltan = sum(len(s) for _, _, s, _ in resultados)
    total = sum(t for _, t, _, _ in resultados)
    campos = sum(c for *_, c in resultados)
    texto = ["# Etiquetas de accesibilidad (TalkBack)", "",
             "Generado por `pruebas/auditar_accesibilidad.py` en el dispositivo conectado: el árbol de accesibilidad de cada",
             "pantalla, leído con uiautomator, que es lo que recorre TalkBack.", "",
             "| Pantalla | Controles que se pueden tocar | Con etiqueta visible | Campos de texto | Sin etiqueta (posición) |",
             "|---|---:|---:|---:|---|", *filas, "",
             f"- **{total - faltan} de {total} controles tienen etiqueta.** De ellos, {campos} son campos de texto: su etiqueta va como",
             "  texto de ayuda de Android (TalkBack la lee, uiautomator no la muestra) y la confirma `movil/test/accesibilidad_test.dart`.", ""]
    (PRUEBAS / "accesibilidad.md").write_text("\n".join(texto), encoding="utf-8")
    print("\n".join(texto))
    return 1 if faltan else 0


if __name__ == "__main__":
    raise SystemExit(main())

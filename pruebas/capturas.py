"""Capturas del flujo de la app con un navegador headless (Playwright).

Sirve para docs/ y para comprobar que la app desplegada corre de punta a punta:

    python pruebas/capturas.py --url http://localhost:8501 --salida docs/capturas
    python pruebas/capturas.py --url https://<app>.streamlit.app --salida docs/capturas

Hace cuatro capturas: la pantalla inicial, la respuesta a la pregunta de la radiografía
(P02: veredicto, explicación y lo mencionado pero ausente), la de la torcedura (P01) con
una cita desplegada y "podrían aplicar", y la pestaña "Dónde atenderte" en Tarapoto. El
mapa se dibuja con WebGL por software: con la GPU del modo headless el mapa base sale en
blanco en la captura (en un navegador normal se ve). Cada consulta a una app con Groq gasta cuota
(unos 5000 tokens si la pregunta está en la caché). Necesita `pip install playwright` y
`python -m playwright install chromium` (solo en local; no va en la app).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ANCHO, ALTO = 1000, 2600  # alto: Streamlit hace scroll dentro de su contenedor, no de la página


def esperar_app(pagina, timeout: int = 180_000) -> None:
    """Streamlit Cloud puede estar dormida: espera a que la póliza esté cargada (la caja de pregunta)."""
    pagina.get_by_role("heading", name="¿Qué me cubre?").wait_for(timeout=timeout)
    pagina.get_by_label("Tu pregunta").wait_for(timeout=timeout)


def esperar_respuesta(pagina, timeout: int = 120_000) -> None:
    pagina.locator(".qmc-veredicto").first.wait_for(timeout=timeout)
    pagina.wait_for_timeout(1500)  # que terminen de pintarse los bloques de abajo


def capturar(pagina, marco, ruta: Path) -> None:
    """La página hasta donde termina el contenido de la app (sin el blanco de abajo)."""
    caja = marco.locator('[data-testid="stMainBlockContainer"]').first.bounding_box()
    alto = min(ALTO, int(caja["y"] + caja["height"] + 40)) if caja else ALTO
    pagina.screenshot(path=str(ruta), clip={"x": 0, "y": 0, "width": ANCHO, "height": alto})


def main() -> int:
    from playwright.sync_api import sync_playwright

    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8501")
    p.add_argument("--salida", default="docs/capturas")
    a = p.parse_args()
    salida = Path(a.salida)
    salida.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as pw:
        navegador = pw.chromium.launch(args=["--use-angle=swiftshader", "--enable-unsafe-swiftshader"])
        pagina = navegador.new_page(viewport={"width": ANCHO, "height": ALTO}, device_scale_factor=1)
        pagina.goto(a.url, wait_until="domcontentloaded")
        marco = pagina
        if ".streamlit.app" in a.url:  # en Streamlit Cloud la app va dentro de un iframe
            pagina.wait_for_selector("iframe", timeout=180_000)
            marco = pagina.frame_locator("iframe").first
        esperar_app(marco)
        pagina.wait_for_timeout(1500)
        capturar(pagina, marco, salida / "1_inicio.png")
        print("1_inicio.png")

        marco.get_by_role("button", name="Me dijeron que me saque una radiografía").click()
        esperar_respuesta(marco)
        marco.locator(".qmc-veredicto").first.scroll_into_view_if_needed()
        capturar(pagina, marco, salida / "2_respuesta_radiografia.png")
        print("2_respuesta_radiografia.png:", marco.locator(".qmc-veredicto").first.inner_text())

        marco.get_by_role("button", name="Me torcí el dedo en Tarapoto").click()
        marco.get_by_text("Pregunta: Me torcí el dedo").wait_for(timeout=120_000)
        esperar_respuesta(marco)
        cita = marco.get_by_text("Cita 1 ·").first
        cita.click()
        pagina.wait_for_timeout(800)
        capturar(pagina, marco, salida / "3_respuesta_torcedura_citas.png")
        print("3_respuesta_torcedura_citas.png:", marco.locator(".qmc-veredicto").first.inner_text())

        marco.get_by_role("tab", name="Dónde atenderte").click()
        marco.get_by_text("no la red de tu aseguradora").wait_for(timeout=60_000)
        pagina.wait_for_timeout(6000)  # teselas del mapa base
        capturar(pagina, marco, salida / "4_donde_atenderte.png")
        print("4_donde_atenderte.png")
        navegador.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())

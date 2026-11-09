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

En vivo, contra la app desplegada:

    python pruebas/capturas.py --url https://queqbre.streamlit.app --salida <carpeta> --espera 45

--espera deja pasar el límite por minuto entre P02 y P01 (si no, P01 cae en la red de
seguridad). Si una respuesta sale sin veredicto o sin el bloque de B4, el script se detiene
sin dar por buenas las capturas: no reintenta (sería gastar otra consulta sin decidirlo).
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ANCHO, ALTO = 1000, 3600  # alto: Streamlit hace scroll dentro de su contenedor, no de la página


def esperar_app(pagina, timeout: int = 180_000) -> None:
    """Streamlit Cloud puede estar dormida: espera a que la póliza esté cargada (la caja de pregunta)."""
    pagina.get_by_role("heading", name="¿Qué me cubre?").wait_for(timeout=timeout)
    pagina.get_by_label("Tu pregunta").wait_for(timeout=timeout)


def esperar_respuesta(pagina, timeout: int = 120_000) -> None:
    pagina.locator(".qmc-veredicto").first.wait_for(timeout=timeout)
    time.sleep(1.5)  # que terminen de pintarse los bloques de abajo (en la nube, `pagina` es el iframe)


def comprobar(marco, caso: str) -> str:
    """La respuesta tiene que estar completa y con B4 en el bloque; si no, se detiene."""
    etiqueta = marco.locator(".qmc-veredicto").first.inner_text().strip()
    if etiqueta == "Sin veredicto":
        aviso = marco.locator("[data-testid='stAlert']").nth(1).inner_text()
        raise SystemExit(f"{caso}: cayó en la red de seguridad, no se guarda. Aviso: {aviso[:160]}")
    if not marco.get_by_text("B4 - Continuación de Tratamiento").count():
        raise SystemExit(f"{caso}: la respuesta no muestra el bloque de B4, no se guarda.")
    return etiqueta


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
    p.add_argument("--espera", type=int, default=0, help="segundos entre P02 y P01 (límite por minuto)")
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
        etiqueta = comprobar(marco, "P02")
        marco.locator(".qmc-veredicto").first.scroll_into_view_if_needed()
        capturar(pagina, marco, salida / "2_respuesta_radiografia.png")
        print("2_respuesta_radiografia.png:", etiqueta)

        if a.espera:
            print(f"espero {a.espera} s (límite por minuto) antes de P01")
            pagina.wait_for_timeout(a.espera * 1000)
        marco.get_by_role("button", name="Me torcí el dedo en Tarapoto").click()
        marco.get_by_text("Pregunta: Me torcí el dedo").wait_for(timeout=120_000)
        esperar_respuesta(marco)
        comprobar(marco, "P01")
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

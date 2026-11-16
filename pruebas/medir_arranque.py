"""Cuánto tarda en arrancar la API y cuánta memoria ocupa (el plan gratuito de Render da 512 MB).

Levanta uvicorn en un proceso aparte, mide el tiempo hasta que /salud responde, carga los
condicionados precargados y el mapa (lo que queda en memoria en uso normal), sube una
póliza de 62 páginas y anota la memoria residente en cada paso. Sin llamar al modelo.

    python pruebas/medir_arranque.py                      # en esta máquina
    python pruebas/medir_arranque.py --url https://...    # arranque en frío de un servidor desplegado
"""

from __future__ import annotations

import argparse
import os
import platform
import socket
import subprocess
import sys
import time

import httpx
import psutil
from comun import PRUEBAS, RAIZ, utf8


def esperar(url: str, tope: float = 300.0) -> float:
    t0 = time.perf_counter()
    while time.perf_counter() - t0 < tope:
        try:
            if httpx.get(url + "/salud", timeout=tope).status_code == 200:
                return time.perf_counter() - t0
        except httpx.HTTPError:
            time.sleep(0.2)
    raise RuntimeError("la API no respondió")


def remoto(url: str, minutos_quieto: float) -> int:
    """Primera respuesta de un servidor que estaba dormido y, enseguida, una segunda ya despierto."""
    import datetime as dt

    frio = esperar(url)
    t0 = time.perf_counter()
    httpx.get(url + "/salud", timeout=60)
    tibio = time.perf_counter() - t0
    lineas = [
        "# Arranque en frío del backend desplegado",
        "",
        f"Generado por `pruebas/medir_arranque.py --url {url}` el {dt.datetime.now():%Y-%m-%d %H:%M}, después de "
        f"{minutos_quieto:.0f} minutos sin enviarle ninguna petición (Render duerme el plan gratuito a los 15).",
        "",
        f"- Primera respuesta de `/salud` (servidor dormido): **{frio:.1f} s**.",
        f"- Segunda respuesta, ya despierto: {tibio:.2f} s.",
    ]
    (PRUEBAS / "arranque_render.md").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lineas[4:]))
    return 0


def main() -> int:
    utf8()
    p = argparse.ArgumentParser()
    p.add_argument("--url")
    p.add_argument("--esperar-minutos", type=float, default=0, help="minutos sin tocar el servidor antes de medir")
    args = p.parse_args()
    if args.url:
        time.sleep(args.esperar_minutos * 60)
        return remoto(args.url.rstrip("/"), args.esperar_minutos)

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        puerto = s.getsockname()[1]
    url = f"http://127.0.0.1:{puerto}"
    entorno = os.environ | {"QMC_PROVEEDOR": "grabado", "LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": "",
                            "VOYAGE_API_KEY": "", "DATABASE_URL": "sqlite://", "QMC_LIMITE_SUBIDAS_DIA": "50"}
    proceso = subprocess.Popen([sys.executable, "-m", "uvicorn", "backend.main:app", "--port", str(puerto),
                                "--log-level", "warning"], cwd=RAIZ, env=entorno)
    try:
        arranque = esperar(url)
        hijos = psutil.Process(proceso.pid)

        def mb() -> float:
            procesos = [hijos, *hijos.children(recursive=True)]
            return sum(x.memory_info().rss for x in procesos) / 1e6

        pasos = [("al arrancar", mb())]
        cabecera = {"X-Dispositivo": "medicion-0001"}
        for f in httpx.get(url + "/polizas", timeout=60).json():
            httpx.get(f"{url}/polizas/{f['poliza_id']}", timeout=120)
        pasos.append(("con los condicionados precargados en memoria", mb()))
        httpx.get(url + "/mapa/departamentos", timeout=120)
        pasos.append(("con el registro de RENIPRESS cargado", mb()))
        pdf = (RAIZ / "data" / "polizas" / "chubb_viajes_jetsmart.pdf").read_bytes()
        t0 = time.perf_counter()
        r = httpx.post(url + "/polizas", files=[("archivos", ("chubb.pdf", pdf, "application/pdf"))], headers=cabecera, timeout=300)
        subida = time.perf_counter() - t0
        pasos.append((f"después de subir una póliza de {r.json()['paginas']} páginas", mb()))
    finally:
        proceso.terminate()

    lineas = [
        "# Arranque y memoria de la API",
        "",
        f"Generado por `pruebas/medir_arranque.py` en {platform.system()} {platform.release()}, Python "
        f"{platform.python_version()}, sin embeddings y sin llamar al modelo. Es esta máquina, no Render: el arranque "
        "en frío del servidor desplegado se mide con `--url` cuando esté desplegado.",
        "",
        f"- Arranque hasta que `/salud` responde: {arranque:.1f} s.",
        f"- Subir e indexar una póliza de 62 páginas (extracción, troceado e índice, sin embeddings): {subida:.1f} s.",
        "",
        "| Momento | Memoria residente |",
        "|---|---:|",
    ] + [f"| {nombre} | {valor:.0f} MB |" for nombre, valor in pasos] + [
        "",
        f"El plan gratuito de Render da 512 MB: lo más alto medido al terminar cada paso es {max(v for _, v in pasos):.0f} MB.",
    ]
    (PRUEBAS / "arranque.md").write_text("\n".join(lineas) + "\n", encoding="utf-8", newline="\n")
    print("\n".join(lineas[4:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

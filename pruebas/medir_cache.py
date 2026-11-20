"""Cuánto baja el costo con la caché de respuestas. Sin red y sin gasto.

Las 10 preguntas de pruebas/preguntas.json se hacen dos veces por la API, con la segunda
escrita distinto (minúsculas, sin tildes ni signos). El modelo se reemplaza por las respuestas
ya grabadas con sus tokens reales, así que el costo de cada pregunta es el que se midió con
Claude Haiku; el triage, el promedio medido de pruebas/fase2.md (en un acierto tampoco se paga).

    python pruebas/medir_cache.py      # escribe pruebas/cache.md
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import time

from comun import PRUEBAS, utf8

os.environ.update({"QMC_PROVEEDOR": "grabado", "DATABASE_URL": f"sqlite:///{tempfile.mkdtemp().replace(os.sep, '/')}/cache.db",
                   "VOYAGE_API_KEY": "", "LANGFUSE_PUBLIC_KEY": "", "LANGFUSE_SECRET_KEY": "", "QMC_LIMITE_DISPOSITIVO_DIA": "100",
                   "QMC_LIMITE_DISPOSITIVO_MES": "100", "QMC_LIMITE_IP_DIA": "500"})

from fastapi.testclient import TestClient  # noqa: E402

from ai.cache_normalizacion import texto_clave  # noqa: E402
from ai.llm import Proveedor, ProveedorNoDisponible  # noqa: E402
from backend import main  # noqa: E402
from backend.cache_respuestas import normalizar  # noqa: E402


class Grabado(Proveedor):
    nombre, reutiliza_datos, aviso = "grabado", False, ""
    precios = (0.10, 0.50)
    modelos = {"normalizacion": "claude-haiku-5-5", "respuesta": "claude-haiku-5-5"}

    def __init__(self) -> None:  # noqa: D107
        self.grabadas = {}
        for ruta in sorted((PRUEBAS / "salidas").glob("P*.json")):
            r = json.loads(ruta.read_text(encoding="utf-8"))
            d = r["uso"]["detalle"][-1]
            self.grabadas[texto_clave(r["pregunta"])] = (r["modelo_crudo"], d["tokens_entrada"], d["tokens_salida"])

    def _llamar(self, tarea, modelo, sistema, usuario, esquema):
        if tarea == "respuesta":
            pregunta = usuario.rsplit("<pregunta>", 1)[1].split("</pregunta>")[0].strip()
            crudo, t_in, t_out = self.grabadas[texto_clave(pregunta)]
            return json.dumps(crudo), t_in, t_out, 0
        raise ProveedorNoDisponible("sin triage grabado")


def main_() -> None:
    utf8()
    preguntas = json.loads((PRUEBAS / "preguntas.json").read_text(encoding="utf-8"))
    triage = float(re.search(r"Costo del paso: USD ([\d.]+)", (PRUEBAS / "fase2.md").read_text(encoding="utf-8")).group(1))
    grabado = Grabado()
    main.proveedor = lambda: grabado
    filas, totales = [], {1: [0.0, 0.0], 2: [0.0, 0.0]}
    with TestClient(main.app) as api:
        lim = main.limites()
        for q in preguntas:
            datos = []
            for vuelta, texto in ((1, q["pregunta"]), (2, normalizar(q["pregunta"]).upper())):
                gasto = lim.gasto_del_mes()["usd"]
                t0 = time.perf_counter()
                r = api.post("/v1/preguntar", json={"poliza_id": q["poliza"], "pregunta": texto}, headers={"X-Dispositivo": "medir-cache-01"})
                segundos = time.perf_counter() - t0
                costo = lim.gasto_del_mes()["usd"] - gasto
                costo += triage if costo > 0 else 0.0
                totales[vuelta][0] += costo
                totales[vuelta][1] += segundos
                datos.append((costo, segundos, r.json().get("modo")))
            filas.append(f"| {q['id']} | {datos[0][2]} | USD {datos[0][0]:.5f} · {datos[0][1]:.2f} s | USD {datos[1][0]:.5f} · {datos[1][1]:.2f} s |")
    ahorro = 1 - totales[2][0] / totales[1][0]
    texto = ["# Caché de respuestas", "",
             "Generado por `pruebas/medir_cache.py`: las 10 preguntas dos veces, la segunda escrita distinto",
             "(mayúsculas, sin tildes ni signos). Costo de la respuesta con los tokens que se midieron con Claude",
             f"Haiku, más el triage medido (USD {triage:.5f}). Tiempo: el de la API en local, con la respuesta grabada.", "",
             "| # | Modo | Primera vez | Repetida |", "|---|---|---:|---:|", *filas, "",
             f"- **Primera vez:** USD {totales[1][0]:.4f} en total, {totales[1][1]:.1f} s.",
             f"- **Repetida:** USD {totales[2][0]:.4f} en total, {totales[2][1]:.1f} s.",
             f"- **Una pregunta repetida cuesta {ahorro:.0%} menos.** Cuánto baja el gasto del mes depende de cuántas",
             "  preguntas se repitan, y eso todavía no se ha medido con usuarios.", ""]
    (PRUEBAS / "cache.md").write_text("\n".join(texto), encoding="utf-8")
    print("\n".join(texto))


if __name__ == "__main__":
    main_()

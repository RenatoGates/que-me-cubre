"""Cuánto cuesta cada plan con los límites vigentes, a partir de costos medidos. Sin red y sin gasto.

Costos medidos (Claude Haiku, ya registrados en el repositorio):
- una consulta: el promedio de las 10 preguntas de pruebas/salidas/*.json;
- el triage previo a cada consulta: el promedio de pruebas/fase2.md;
- una radiografía: el promedio de las 5 de data/cache/radiografias/ (se paga una vez por póliza);
- una comparación de ¿Pagas doble?: pruebas/fase2.json.
Límites: los de backend/limites.py y backend/pagos.py con su configuración por defecto.

Ingreso del pago único: S/ 3,99 menos la comisión de Google Play (15 %). El tipo de cambio no
se mide: es un supuesto que se pasa con --tipo-cambio y queda escrito en el informe.

    python pruebas/medir_planes.py [--tipo-cambio 3.75]     # escribe pruebas/planes.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import tempfile

from comun import PRUEBAS, RAIZ, utf8

os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp().replace(os.sep, '/')}/planes.db")
for variable in ("QMC_LIMITE_DISPOSITIVO_DIA", "QMC_LIMITE_GRATIS_DIA", "QMC_LIMITE_PAGADO_DIA", "QMC_POLIZAS_GRATIS",
                 "QMC_POLIZAS_PAGADO", "QMC_DIAS_POLIZA_GRATIS", "QMC_TOPE_GLOBAL_USD"):
    os.environ.pop(variable, None)  # los valores por defecto del código, no los de un .env local

from backend import pagos  # noqa: E402
from backend.limites import Limites  # noqa: E402

PRECIO_SOLES = 3.99
COMISION_PLAY = 0.15
DIAS = 30


def costos() -> dict:
    consultas = [json.loads(p.read_text(encoding="utf-8"))["uso"]["costo_usd"] for p in sorted((PRUEBAS / "salidas").glob("P*.json"))]
    triage = float(re.search(r"Costo del paso: USD ([\d.]+)", (PRUEBAS / "fase2.md").read_text(encoding="utf-8")).group(1))
    radiografias = [json.loads(p.read_text(encoding="utf-8"))["uso"]["costo_usd"]
                    for p in sorted((RAIZ / "data" / "cache" / "radiografias").glob("*.json"))]
    comparar = json.loads((PRUEBAS / "fase2.json").read_text(encoding="utf-8"))["superposiciones"]["uso"]["costo_usd"]
    return {"consulta": statistics.mean(consultas), "consulta_max": max(consultas), "n_consultas": len(consultas),
            "triage": triage, "radiografia": statistics.mean(radiografias), "n_radiografias": len(radiografias), "comparar": comparar}


def main() -> None:
    utf8()
    a = argparse.ArgumentParser()
    a.add_argument("--tipo-cambio", type=float, default=3.75, help="soles por dólar (supuesto, no medido)")
    tc = a.parse_args().tipo_cambio
    c = costos()
    lim = Limites()
    por_consulta = c["consulta"] + c["triage"]
    neto_usd = PRECIO_SOLES * (1 - COMISION_PLAY) / tc
    tope = lim.tope_global_usd

    pagado_real = 4 * 2 * por_consulta  # 4 pólizas, 2 preguntas por póliza al mes
    pagado_unica = pagos.polizas_permitidas("pagado") * c["radiografia"]  # una radiografía por póliza, una sola vez
    pagado_max = lim.limite_pagado_dia * DIAS * por_consulta
    gratis_max = lim.limite_gratis_dia * DIAS * por_consulta
    sin_cuenta_max = lim.limite_dispositivo * DIAS * por_consulta
    testers = 12

    filas = [
        ("Costo medido de una consulta (respuesta + triage)", f"USD {por_consulta:.5f}"),
        ("Radiografía (una vez por póliza)", f"USD {c['radiografia']:.4f}"),
        ("¿Pagas doble? (una comparación)", f"USD {c['comparar']:.4f}"),
        ("Ingreso neto del pago único (S/ 3,99 − 15 % de Google Play)", f"S/ {PRECIO_SOLES * (1 - COMISION_PLAY):.2f} ≈ USD {neto_usd:.2f}"),
        ("Pagado, uso realista: 4 pólizas × 2 preguntas al mes", f"USD {pagado_real:.4f} al mes; USD {pagado_real * 12:.3f} al año"),
        ("Pagado, una vez: radiografía de sus 4 pólizas", f"USD {pagado_unica:.4f}"),
        ("Pagado, uso realista: años que cubre el pago", f"{(neto_usd - pagado_unica) / (pagado_real * 12):.0f}"),
        (f"Pagado, peor caso: {lim.limite_pagado_dia} consultas todos los días", f"USD {pagado_max:.2f} al mes"),
        ("Pagado, peor caso: meses que cubre el pago", f"{neto_usd / pagado_max:.1f}"),
        (f"Gratis, peor caso: {lim.limite_gratis_dia} consultas todos los días", f"USD {gratis_max:.3f} al mes"),
        (f"Sin cuenta, peor caso: {lim.limite_dispositivo} consultas todos los días", f"USD {sin_cuenta_max:.3f} al mes por dispositivo"),
        (f"{testers} testers gratis en el peor caso", f"USD {testers * gratis_max:.2f} al mes (tope global: USD {tope:.2f})"),
        ("Usuarios gratis en el peor caso que agotan el tope global", f"{tope / gratis_max:.1f}"),
        ("Usuarios pagados en el peor caso que agotan el tope global", f"{tope / pagado_max:.1f}"),
    ]
    texto = ["# Costo de cada plan", "",
             f"Generado por `pruebas/medir_planes.py`. Consulta: promedio de {c['n_consultas']} preguntas medidas "
             f"(máximo USD {c['consulta_max']:.4f}) más el triage. Radiografía: promedio de {c['n_radiografias']}. "
             f"Mes de {DIAS} días. Tipo de cambio supuesto (no medido): S/ {tc:.2f} por dólar.", "",
             "| Concepto | Valor |", "|---|---|", *[f"| {k} | {v} |" for k, v in filas], ""]
    (PRUEBAS / "planes.md").write_text("\n".join(texto), encoding="utf-8")
    print("\n".join(texto))


if __name__ == "__main__":
    main()

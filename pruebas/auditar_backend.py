"""Vulnerabilidades conocidas en las dependencias del backend y de la web, con pip-audit.

    python pruebas/auditar_backend.py      # escribe pruebas/auditoria_backend.md; código 1 si hay alguna
"""

from __future__ import annotations

import json
import subprocess

from comun import PRUEBAS, RAIZ, utf8


def main() -> int:
    utf8()
    salida = subprocess.run(["uvx", "pip-audit", "-r", "requirements.txt", "--progress-spinner", "off", "-f", "json"],
                            cwd=RAIZ, capture_output=True, text=True, check=False)
    datos = json.loads(salida.stdout)["dependencies"]
    hallados = [(d["name"], d["version"], [v["id"] for v in d.get("vulns", [])]) for d in datos if d.get("vulns")]
    texto = ["# Auditoría de dependencias del backend", "",
             f"Generado por `pruebas/auditar_backend.py` (pip-audit sobre `requirements.txt`, con sus dependencias): "
             f"{len(datos)} paquetes.", ""]
    texto += ([f"- **{n} {v}:** {', '.join(ids)}" for n, v, ids in hallados] if hallados else ["- Ninguna vulnerabilidad conocida."])
    (PRUEBAS / "auditoria_backend.md").write_text("\n".join(texto) + "\n", encoding="utf-8")
    print("\n".join(texto))
    return 1 if hallados else 0


if __name__ == "__main__":
    raise SystemExit(main())

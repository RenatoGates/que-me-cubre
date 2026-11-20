"""Vulnerabilidades conocidas en las dependencias de la app de Android (el pip-audit de Flutter).

Lee movil/pubspec.lock y pregunta a OSV.dev (la base pública de vulnerabilidades de Google,
que cubre el ecosistema Pub) por cada paquete y versión. Solo se envían nombres y versiones.

    python pruebas/auditar_flutter.py      # escribe pruebas/auditoria_flutter.md; código 1 si hay alguna
"""

from __future__ import annotations

import re

import httpx

from comun import PRUEBAS, RAIZ, utf8


def paquetes() -> list[tuple[str, str]]:
    lock = (RAIZ / "movil" / "pubspec.lock").read_text(encoding="utf-8")
    return re.findall(r"^  ([\w-]+):\n(?:    .*\n)*?    version: \"([^\"]+)\"", lock, flags=re.M)


def main() -> int:
    utf8()
    lista = paquetes()
    consultas = [{"package": {"name": n, "ecosystem": "Pub"}, "version": v} for n, v in lista]
    r = httpx.post("https://api.osv.dev/v1/querybatch", json={"queries": consultas}, timeout=60)
    r.raise_for_status()
    hallados = [(n, v, [x["id"] for x in res.get("vulns", [])]) for (n, v), res in zip(lista, r.json()["results"]) if res.get("vulns")]
    texto = ["# Auditoría de dependencias de la app de Android", "",
             f"Generado por `pruebas/auditar_flutter.py`: {len(lista)} paquetes de `movil/pubspec.lock` consultados en OSV.dev.", ""]
    texto += ([f"- **{n} {v}:** {', '.join(ids)}" for n, v, ids in hallados] if hallados else ["- Ninguna vulnerabilidad conocida."])
    (PRUEBAS / "auditoria_flutter.md").write_text("\n".join(texto) + "\n", encoding="utf-8")
    print("\n".join(texto))
    return 1 if hallados else 0


if __name__ == "__main__":
    raise SystemExit(main())

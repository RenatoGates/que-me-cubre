"""Calibra y mide el portero de documento (ai/portero.py). Sin modelo y sin red.

Positivos: los 5 condicionados públicos de data/polizas/ y, si está en data/privado/, una
póliza dental real (de ella solo se anotan números, nunca texto). Negativos: los PDF de
data/privado/negativos/ (documentos que no son condicionados; su procedencia está en
data/privado/negativos/fuentes.json, que se copia al informe) y el boletín de data/privado/.

    python pruebas/medir_portero.py
"""

from __future__ import annotations

import json

from comun import PRUEBAS, RAIZ, utf8

from ai import portero
from ai.extraccion import extraer
from ai.subida import reparar
from ai.troceado import trocear

PRIVADO = RAIZ / "data" / "privado"


def texto_de(ruta) -> str:
    doc = extraer(reparar(ruta.read_bytes()))
    return " ".join(t.texto for t in trocear(doc.bloques, "x", "x"))


def main() -> int:
    utf8()
    fuentes = json.loads((RAIZ / "data" / "polizas" / "fuentes.json").read_text(encoding="utf-8"))
    casos = [(f"{f['aseguradora']} · {f['producto']}", RAIZ / "data" / "polizas" / f["archivo"], True) for f in fuentes]
    if (PRIVADO / "seguro_dental_personal.pdf").exists():
        casos.append(("Póliza dental real (privada, sin versionar)", PRIVADO / "seguro_dental_personal.pdf", True))
    negativos = {}
    ruta_fuentes = PRIVADO / "negativos" / "fuentes.json"
    if ruta_fuentes.exists():
        negativos = json.loads(ruta_fuentes.read_text(encoding="utf-8"))
    if (PRIVADO / "boletin_eps_susalud.pdf").exists():
        casos.append(("Boletín informativo de SUSALUD sobre las EPS (no es un condicionado)", PRIVADO / "boletin_eps_susalud.pdf", False))
    casos += [(datos["descripcion"], PRIVADO / "negativos" / archivo, False) for archivo, datos in negativos.items()]

    filas = []
    for nombre, ruta, es_poliza in casos:
        m = portero.medir(texto_de(ruta))
        r = portero.revisar(texto_de(ruta))
        filas.append((nombre, es_poliza, m, r["parece_poliza"]))
        print(f"{'✓' if r['parece_poliza'] == es_poliza else '✗'} {nombre[:60]:<60} densidad {m['densidad']:>5} · distintos {m['distintos']:>2} de {len(portero.MARCADORES)} "
              f"· {m['palabras']} palabras → {'parece póliza' if r['parece_poliza'] else 'aviso'}")

    vp = sum(1 for _, es, _, dice in filas if es and dice)
    fn = sum(1 for _, es, _, dice in filas if es and not dice)
    vn = sum(1 for _, es, _, dice in filas if not es and not dice)
    fp = sum(1 for _, es, _, dice in filas if not es and dice)
    L = [
        "# Portero de documento: ¿parece un condicionado de seguro?",
        "",
        "Generado por `pruebas/medir_portero.py`. Sin modelo: `ai/portero.py` cuenta en el texto extraído "
        f"{len(portero.MARCADORES)} marcadores de vocabulario de póliza. Un documento *parece póliza* si tiene al menos "
        f"{portero.UMBRAL_DENSIDAD:g} apariciones por cada mil palabras **y** al menos {portero.UMBRAL_DISTINTOS} marcadores distintos. "
        "Bajo el umbral no se bloquea: se avisa y se deja continuar.",
        "",
        "| | Dice «parece póliza» | Dice «no parece» (aviso) |",
        "|---|---:|---:|",
        f"| Es un condicionado ({vp + fn}) | {vp} | {fn} |",
        f"| No lo es ({vn + fp}) | {fp} | {vn} |",
        "",
        f"Clasificó bien {vp} de {vp + fn} condicionados y {vn} de {vn + fp} documentos que no lo son.",
        "",
        "| Documento | ¿Es condicionado? | Marcadores por mil palabras | Marcadores distintos | Palabras | Resultado |",
        "|---|---|---:|---:|---:|---|",
    ] + [f"| {n} | {'sí' if es else 'no'} | {m['densidad']} | {m['distintos']} | {m['palabras']} | "
         f"{'parece póliza' if dice else 'aviso'}{'' if dice == es else ' (**mal**)'} |" for n, es, m, dice in filas]
    if negativos:
        L += ["", "Negativos descargados (no se versionan; están en `data/privado/negativos/`):", ""]
        L += [f"- {d['descripcion']}: <{d['url']}>, sha256 `{d['sha256'][:16]}…`" for d in negativos.values()]
    L += ["",
          f"Límite: son {len(filas)} documentos y el umbral se fijó mirándolos, así que estos aciertos no predicen cómo le irá con "
          "otros. Un documento que habla de seguros sin ser una póliza (un boletín, un folleto comercial) es el caso difícil. "
          "De la póliza dental privada aquí solo hay números: su texto no está en el repositorio."]
    (PRUEBAS / "portero.md").write_text("\n".join(L) + "\n", encoding="utf-8", newline="\n")
    print(f"\nPositivos bien: {vp} de {vp + fn} · negativos bien: {vn} de {vn + fp}. Resumen en pruebas/portero.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

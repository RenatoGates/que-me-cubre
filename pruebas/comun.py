"""Utilidades compartidas por los scripts de pruebas/."""

from __future__ import annotations

import json
import sys
from functools import lru_cache
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from ai.indice import Indice  # noqa: E402
from ai.respuesta import Poliza  # noqa: E402
from ai.troceado import Trozo  # noqa: E402

PRUEBAS = RAIZ / "pruebas"
SALIDAS = PRUEBAS / "salidas"
PREGUNTAS = PRUEBAS / "preguntas.json"


def preguntas() -> list[dict]:
    return json.loads(PREGUNTAS.read_text(encoding="utf-8"))


@lru_cache(maxsize=None)
def fuentes() -> dict[str, dict]:
    datos = json.loads((RAIZ / "data" / "polizas" / "fuentes.json").read_text(encoding="utf-8"))
    return {f["id"]: f for f in datos}


@lru_cache(maxsize=None)
def poliza(doc_id: str) -> Poliza:
    indice = Indice.cargar(RAIZ / "data" / "indices", doc_id)
    pdf = (RAIZ / "data" / "polizas" / fuentes()[doc_id]["archivo"]).read_bytes()
    return Poliza(doc_id, indice.meta["documento"], indice, pdf)


def coincide(t: Trozo, esperado: dict) -> bool:
    """¿El trozo es el artículo esperado? Sección y artículo por subcadena; `contiene`
    exige además ese texto (para artículos partidos, la parte que responde)."""
    return (
        esperado["seccion"].lower() in t.seccion.lower()
        and esperado["articulo"].lower() in t.articulo.lower()
        and esperado.get("contiene", "") in t.texto
    )


def acierta(trozos: list[Trozo], esperados: list[dict], modo: str) -> bool | None:
    """None si la pregunta no tiene artículo esperado (control de 'no encontrado')."""
    if modo == "ninguno" or not esperados:
        return None
    halla = [any(coincide(t, e) for t in trozos) for e in esperados]
    return all(halla) if modo == "todos" else any(halla)


def aceptable(q: dict, r: dict) -> bool:
    """Criterio de pruebas/preguntas.json: veredicto aceptable y, si la pregunta lo exige,
    la referencia ausente mencionada, venga del bloque determinista (mencionadas_ausentes) o
    de lo que el modelo puso en no_incluido_en_documento."""
    if r.get("modo", "completo") != "completo":
        return False
    exige = q.get("debe_mencionar_no_incluido")
    return r["cubre"] in q["veredictos_aceptables"] and (not exige or any(exige in n for n in nombres_ausentes(r)))


def nombres_ausentes(r: dict) -> list[str]:
    return [m["nombre"] for m in r.get("mencionadas_ausentes", [])] + [m["nombre"] for m in r["no_incluido_en_documento"]]


def bloque_txt(r: dict) -> str:
    """El bloque determinista en una celda: las cláusulas ausentes por nombre, las remisiones contadas."""
    bloque = r.get("mencionadas_ausentes", [])
    remision = [m.get("nivel", "remision" if m["tipo"] == "documento" else "clausula_ausente") == "remision" for m in bloque]
    nombres = [m["nombre"] for m, es in zip(bloque, remision) if not es]
    remisiones = sum(remision)
    return "; ".join(nombres + ([f"+{remisiones} remisiones"] if remisiones else [])) or "—"


def guardar_json(ruta: Path, datos) -> None:
    ruta.parent.mkdir(parents=True, exist_ok=True)
    ruta.write_text(json.dumps(datos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")


class ProveedorPaciente:
    """Envuelve un proveedor para las pruebas: si Groq pide esperar (límite por minuto o por
    día), espera lo que dice retry-after y reintenta. La app nunca espera: muestra las
    cláusulas. El límite diario se repone continuo (~8300 tokens por hora), así que una
    corrida larga puede pausar varias veces."""

    def __init__(self, proveedor, espera_maxima: float = 4 * 3600):
        self._proveedor = proveedor
        self.espera_maxima = espera_maxima

    def __getattr__(self, nombre):
        return getattr(self._proveedor, nombre)

    def json(self, *args, **kwargs):
        import datetime as dt
        import time

        from ai.llm import LimiteAlcanzado

        while True:
            try:
                return self._proveedor.json(*args, **kwargs)
            except LimiteAlcanzado as e:
                espera = e.espera_segundos if e.espera_segundos is not None else 60
                if espera > self.espera_maxima:
                    raise
                sigue = (dt.datetime.now() + dt.timedelta(seconds=espera + 2)).strftime("%H:%M:%S")
                print(f"  límite del plan gratuito: espero {espera:.0f} s (sigo a las {sigue})", flush=True)
                time.sleep(espera + 2)

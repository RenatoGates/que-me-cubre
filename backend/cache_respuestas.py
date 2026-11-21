"""Caché de respuestas: la misma pregunta sobre el mismo documento no se paga dos veces.

Clave: hash de (pregunta normalizada + aclaraciones + documento + día de Lima). El documento es
el id del condicionado de ejemplo o la huella (sha256) del PDF subido: la misma póliza subida
dos veces es el mismo documento. El día entra en la clave porque la respuesta trae la fecha del
hecho calculada desde hoy ("ayer").

Vive solo en la memoria del servidor: nada de esto se escribe en la base (sin cuenta, la
pregunta y la respuesta no se guardan). Una respuesta sobre una póliza subida dura lo mismo que
la póliza en memoria y se borra con ella; una sobre un condicionado de ejemplo, un día.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
import threading
import time
import unicodedata
from collections import OrderedDict

MAXIMO = 500


def normalizar(texto: str) -> str:
    """Minúsculas, sin tildes, sin signos y con un solo espacio: "¿Me cubre?" = "me cubre"."""
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " ".join(re.sub(r"[^\w\s]", " ", t).split())


def clave(pregunta: str, aclaraciones: list[dict], documento: str, dia: str, turnos: list[dict] | None = None) -> str:
    partes = {"p": normalizar(pregunta), "a": [[normalizar(a.get("pregunta", "")), normalizar(a.get("respuesta", ""))]
                                              for a in aclaraciones], "d": documento, "dia": dia,
              "t": [normalizar(t.get("pregunta", "")) for t in turnos or []]}
    return hashlib.sha256(json.dumps(partes, sort_keys=True).encode()).hexdigest()


class Cache:
    def __init__(self, maximo: int = MAXIMO) -> None:
        self._datos: OrderedDict[str, tuple[dict, str, float]] = OrderedDict()
        self._candado = threading.Lock()
        self.maximo = maximo
        self.aciertos = 0
        self.fallos = 0

    def obtener(self, k: str) -> dict | None:
        with self._candado:
            entrada = self._datos.get(k)
            if entrada is None or entrada[2] < time.monotonic():
                self._datos.pop(k, None)
                self.fallos += 1
                return None
            self._datos.move_to_end(k)
            self.aciertos += 1
            return copy.deepcopy(entrada[0])

    def guardar(self, k: str, respuesta: dict, documento: str, segundos: float) -> None:
        with self._candado:
            self._datos[k] = (copy.deepcopy(respuesta), documento, time.monotonic() + segundos)
            self._datos.move_to_end(k)
            while len(self._datos) > self.maximo:
                self._datos.popitem(last=False)

    def olvidar_documento(self, documento: str) -> int:
        """Al borrar una póliza: sus respuestas salen de la memoria con ella."""
        with self._candado:
            fuera = [k for k, (_, d, _) in self._datos.items() if d == documento]
            for k in fuera:
                del self._datos[k]
            return len(fuera)

    def __len__(self) -> int:
        return len(self._datos)

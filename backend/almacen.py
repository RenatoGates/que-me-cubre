"""Las pólizas con las que trabaja la API.

Precargadas: los condicionados públicos de data/polizas/ con su índice de data/indices/.
Subidas: viven solo en la memoria del proceso, con un identificador al azar que solo conoce
quien la subió, y se borran al vencer (QMC_TTL_POLIZA_MIN), al pedirlo o al reiniciar el
servidor. Nada se escribe en disco.
"""

from __future__ import annotations

import json
import secrets
import threading
import time
from functools import lru_cache
from pathlib import Path

from ai.indice import Indice
from ai.llm import config
from ai.respuesta import Poliza

RAIZ = Path(__file__).resolve().parent.parent
POLIZAS = RAIZ / "data" / "polizas"
INDICES = RAIZ / "data" / "indices"
ENSAYO = RAIZ / "data" / "demo" / "preguntas_ensayo.json"


@lru_cache(maxsize=1)
def fuentes() -> dict[str, dict]:
    return {f["id"]: f for f in json.loads((POLIZAS / "fuentes.json").read_text(encoding="utf-8"))}


@lru_cache(maxsize=None)
def precargada(doc_id: str) -> Poliza:
    indice = Indice.cargar(INDICES, doc_id)
    return Poliza(doc_id, indice.meta["documento"], indice, (POLIZAS / fuentes()[doc_id]["archivo"]).read_bytes())


@lru_cache(maxsize=1)
def ejemplos() -> dict[str, list[str]]:
    salida: dict[str, list[str]] = {}
    for q in json.loads(ENSAYO.read_text(encoding="utf-8")):
        salida.setdefault(q["documento"], []).append(q["pregunta"])
    return salida


class Subidas:
    def __init__(self) -> None:
        self._polizas: dict[str, tuple[Poliza, float]] = {}
        self._candado = threading.Lock()

    @property
    def ttl(self) -> float:
        return 60.0 * float(config("QMC_TTL_POLIZA_MIN", "60") or 60)

    @property
    def maximo(self) -> int:
        return int(config("QMC_MAX_POLIZAS_EN_MEMORIA", "20") or 20)

    def _limpiar(self) -> None:
        ahora = time.monotonic()
        for clave in [k for k, (_, vence) in self._polizas.items() if vence < ahora]:
            del self._polizas[clave]

    def guardar(self, poliza: Poliza) -> str:
        with self._candado:
            self._limpiar()
            while len(self._polizas) >= self.maximo:  # sale la que vence primero
                del self._polizas[min(self._polizas, key=lambda k: self._polizas[k][1])]
            clave = "s_" + secrets.token_urlsafe(24)
            self._polizas[clave] = (poliza, time.monotonic() + self.ttl)
            return clave

    def obtener(self, clave: str) -> Poliza | None:
        with self._candado:
            self._limpiar()
            entrada = self._polizas.get(clave)
            if entrada is None:
                return None
            self._polizas[clave] = (entrada[0], time.monotonic() + self.ttl)  # se usa: se renueva
            return entrada[0]

    def borrar(self, clave: str) -> bool:
        with self._candado:
            return self._polizas.pop(clave, None) is not None

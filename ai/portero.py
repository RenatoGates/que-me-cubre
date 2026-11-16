"""Portero de documento, versión mínima: ¿esto parece un condicionado de seguro?

Sin modelo: cuenta en el texto extraído las palabras propias de una póliza (cláusula,
asegurado, exclusiones, suma asegurada, deducible, prima, siniestro…) y mira dos cosas:
cuántas de ellas aparecen por cada mil palabras y cuántas distintas aparecen. Bajo el umbral
no se bloquea nada: la app avisa que el documento no parece un condicionado y deja seguir.

El umbral está calibrado con pocos documentos (pruebas/portero.md): sirve para atajar el
error más común, subir otro PDF por equivocación, no para garantizar que algo es una póliza.
"""

from __future__ import annotations

import re

from ai.indice import sin_tildes

# Raíces sin tilde: "clausula" cuenta "cláusula" y "cláusulas"; "exclusion" cuenta "exclusiones".
MARCADORES = {
    "cláusula": r"\bclausulas?\b",
    "asegurado": r"\basegurad[oa]s?\b",
    "exclusiones": r"\bexclusion(?:es)?\b",
    "suma asegurada": r"\bsumas? aseguradas?\b",
    "deducible": r"\bdeducibles?\b",
    "condicionado": r"\bcondicionado\b|\bcondiciones (?:generales|particulares|especiales)\b",
    "prima": r"\bprimas?\b",
    "siniestro": r"\bsiniestros?\b",
    "carencia": r"\bcarencia\b",
    "endoso": r"\bendosos?\b",
    "beneficiario": r"\bbeneficiari[oa]s?\b",
    "vigencia": r"\bvigencia\b",
    "contratante": r"\bcontratantes?\b",
    "póliza": r"\bpolizas?\b",
    "indemnización": r"\bindemnizacion(?:es)?\b|\bindemnizar\b",
    "cobertura": r"\bcoberturas?\b",
}
_PATRONES = {nombre: re.compile(p) for nombre, p in MARCADORES.items()}
_PALABRA = re.compile(r"[a-zñ0-9]+")

# Calibrados en pruebas/portero.md con 6 condicionados (24,1 a 51,0 marcadores por mil palabras)
# y 3 documentos que no lo son (0,9 a 9,2): el umbral va a mitad del hueco. Los marcadores
# distintos no separan (9 el condicionado más bajo, 8 el boletín): solo atajan un texto que
# repite una sola palabra.
UMBRAL_DENSIDAD = 16.0  # apariciones de marcadores por cada mil palabras
UMBRAL_DISTINTOS = 5  # marcadores distintos presentes, de los 16
AVISO = "Esto no parece un condicionado de seguro. Puedo intentarlo igual, pero las respuestas pueden no tener sentido."


def medir(texto: str) -> dict:
    plano = sin_tildes(texto.lower())
    palabras = len(_PALABRA.findall(plano))
    cuentas = {nombre: len(p.findall(plano)) for nombre, p in _PATRONES.items()}
    total = sum(cuentas.values())
    return {"palabras": palabras, "marcadores": total, "distintos": sum(1 for c in cuentas.values() if c),
            "densidad": round(1000 * total / palabras, 1) if palabras else 0.0, "cuentas": cuentas}


def revisar(texto: str) -> dict:
    """La medición y el veredicto: parece_poliza y, si no, el aviso para la persona."""
    m = medir(texto)
    parece = m["densidad"] >= UMBRAL_DENSIDAD and m["distintos"] >= UMBRAL_DISTINTOS
    return {"parece_poliza": parece, "aviso": None if parece else AVISO, "densidad": m["densidad"], "distintos": m["distintos"],
            "palabras": m["palabras"]}


def revisar_trozos(trozos) -> dict:
    return revisar(" ".join(t.texto for t in trozos))

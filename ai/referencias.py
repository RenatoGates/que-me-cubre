"""Referencias que la póliza menciona pero cuyo texto no trae ("mencionadas pero ausentes").

Una póliza remite a otros textos: una cobertura con código ("B4 - Continuación de
Tratamiento en País de Residencia"), un anexo ("Anexo A - Tabla de Indemnizaciones por
Invalidez Permanente"), las Condiciones Particulares o el Certificado de Seguro, donde están
los montos. Si ese texto no está en el PDF, nadie puede decir con este documento qué cubre:
lo honesto es avisar que falta y que hay que pedirlo.

Eso lo decide el código, no el modelo. El documento se barre una vez (Indice.ausentes), cada
referencia se compara con los títulos que sí existen en el PDF, y al responder se muestran,
siempre y en su propio bloque, las ausentes que aparecen en los pasajes recuperados, con la
mención literal y su página.

Qué se busca y cuándo cuenta como presente:
- cobertura con código ("B4 - Nombre"): presente si las palabras del nombre están en un
  título de cláusula o de artículo, o si un título de 3 o más palabras está entero dentro
  del nombre ("G2 - Reembolso de Gastos por demora de Equipaje en caso se encuentre…");
- anexo con letra o número ("Anexo A - Nombre"): lo mismo, o si alguna línea del documento
  empieza con "Anexo A" (es su encabezado: la tabla de Rimac va bajo "ANEXO A:" sin título
  de sección propio);
- documentos a los que una póliza remite (DOCUMENTOS_REMITIDOS): presentes si sus palabras
  están en un título de cláusula ("Condiciones Generales", "Condicionado General").

No se detecta: una cobertura nombrada sin código ni la palabra "Anexo", "endosos" o
"anexos" sin nombre (la póliza los menciona "de ser el caso", sin decir cuáles hay), la
Solicitud de Seguro (son las declaraciones del asegurado, no un texto de cobertura), ni una
mención partida entre dos trozos.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from ai.indice import sin_tildes, tokens
from ai.troceado import Trozo

DOCUMENTOS_REMITIDOS = (
    "Condiciones Particulares",
    "Certificado de Seguro",
    "Condiciones Especiales",
    "Condiciones Generales",
    "Tabla de Beneficios",
    "Plan de Beneficios",
)
MENSAJE = "Tu póliza menciona «{}» pero no incluye su texto en este documento. Pídeselo a tu aseguradora."

_GENERICAS = set(tokens("cobertura coberturas cláusula cláusulas adicional adicionales seguro póliza"))
# "B4 - Nombre": código de una letra mayúscula y 1-2 cifras; el nombre llega hasta el fin de
# la línea o el primer . ; : (
_COBERTURA = re.compile(r"(?<![\w])([A-Z]\d{1,2})\s*[-–—]\s*([^\n.;:(]+)")
# "Anexo A - Nombre", "ANEXO 1:", "Anexo B"
_ANEXO = re.compile(r"(?<![\w])((?i:anexo)\s+(?:[A-Z]|\d{1,2}))\b(?:[ \t]*[-–—:][ \t]*([^\n.;:(]+))?")


@dataclass(frozen=True)
class Mencion:
    clave: str  # "B4", "anexo a", "condiciones particulares": una por referencia
    tipo: str  # "cobertura" | "anexo" | "documento"
    nombre: str  # como se muestra: "B4 - Continuación de Tratamiento en País de Residencia"
    trozo_id: str
    inicio: int  # posición de la mención en el texto del trozo
    fin: int


def _plano_alineado(texto: str) -> str:
    """Minúsculas y sin tildes, con la misma longitud que el original (las posiciones sirven)."""
    salida = []
    for c in texto:
        n = sin_tildes(c).lower()
        salida.append(n if len(n) == 1 else (n[:1] or " "))
    return "".join(salida)


def _en_titulo(nombre: str, titulos: list[str], genericas: bool = True) -> bool:
    """¿El nombre es uno de estos títulos? Sus palabras están en un título, o un título de
    3+ palabras está entero en el nombre (el nombre trae una cola: "… en caso se encuentre")."""
    clave = set(tokens(nombre)) - (_GENERICAS if genericas else set())
    if not clave:
        return False
    for t in titulos:
        tt = set(tokens(t)) - (_GENERICAS if genericas else set())
        if clave <= tt or (len(tt) >= 3 and tt <= clave):
            return True
    return False


def _sin_cola(nombre: str) -> str:
    return re.sub(r"\s+", " ", nombre).strip(" ,–—-")


def buscar_menciones(trozos: list[Trozo]) -> list[Mencion]:
    """Todas las menciones de coberturas con código, anexos y documentos remitidos."""
    menciones = []
    for t in trozos:
        for m in _COBERTURA.finditer(t.texto):
            nombre = _sin_cola(m.group(2))
            if len(tokens(nombre)) >= 2:
                menciones.append(Mencion(m.group(1), "cobertura", f"{m.group(1)} - {nombre}", t.id, m.start(1), m.start(2) + len(m.group(2).rstrip(" ,–—-"))))
        for m in _ANEXO.finditer(t.texto):
            etiqueta = "Anexo " + m.group(1).split()[-1]  # "ANEXO A" -> "Anexo A"
            nombre = _sin_cola(m.group(2) or "")
            fin = m.start(2) + len(m.group(2).rstrip(" ,–—-")) if nombre else m.end(1)
            menciones.append(Mencion(etiqueta.lower(), "anexo", f"{etiqueta} - {nombre}" if nombre else etiqueta, t.id, m.start(1), fin))
        plano = _plano_alineado(t.texto)
        for doc in DOCUMENTOS_REMITIDOS:
            patron = r"\b" + r"\s+".join(map(re.escape, _plano_alineado(doc).split())) + r"\b"
            for m in re.finditer(patron, plano):
                menciones.append(Mencion(_plano_alineado(doc), "documento", doc, t.id, m.start(), m.end()))
    return menciones


def ausentes(trozos: list[Trozo], clausulas: list[str], articulos: list[str]) -> dict[str, list[Mencion]]:
    """{trozo_id: [menciones de referencias ausentes del documento]}, en orden de aparición."""
    menciones = buscar_menciones(trozos)
    titulos = clausulas + articulos
    encabezados_anexo = {
        re.sub(r"\s+", " ", m.group(1)).lower()
        for t in trozos
        for m in re.finditer(r"(?im)^[\W_]*(anexo\s+(?:[a-z]|\d{1,2}))\b", t.texto)
    }
    presentes: dict[str, bool] = {}
    for m in menciones:
        if presentes.get(m.clave):
            continue
        if m.tipo == "documento":
            presente = _en_titulo(m.nombre, clausulas, genericas=False)
        else:
            nombre = m.nombre.split(" - ", 1)[1] if " - " in m.nombre else ""
            presente = bool(nombre) and _en_titulo(nombre, titulos)
            if m.tipo == "anexo":
                presente = presente or m.clave in encabezados_anexo
        presentes[m.clave] = presente
    por_trozo: dict[str, list[Mencion]] = {}
    for m in menciones:
        if not presentes[m.clave]:
            por_trozo.setdefault(m.trozo_id, []).append(m)
    for lista in por_trozo.values():
        lista.sort(key=lambda m: m.inicio)
    return por_trozo

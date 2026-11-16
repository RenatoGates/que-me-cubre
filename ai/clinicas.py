"""Clínicas que el condicionado nombra literalmente, con la cita de donde sale cada nombre.

Sin modelo. Busca en el texto un tipo de establecimiento (clínica, hospital, centro médico…)
seguido de un nombre propio, y devuelve cada nombre con la oración donde aparece, su página
y la verificación de esa oración contra el PDF, igual que cualquier cita. Es conservador a
propósito: prefiere no encontrar una clínica antes que inventar una. "La clínica u hospital
de LA COMPAÑÍA" no es un nombre; "Clínica San Pablo" sí.

Que la póliza nombre una clínica no dice para qué coberturas está en convenio: se muestra la
cita tal cual, sin generalizar.
"""

from __future__ import annotations

import re

from ai.indice import sin_tildes
from ai.respuesta import Poliza
from ai.verificacion import verificar_en_pdf

# El tipo puede ir en minúsculas o mayúsculas; el nombre propio tiene que empezar con mayúscula de verdad
_TIPO = r"(?i:cl[íi]nicas?|hospital(?:es)?|policl[íi]nicos?|centros?\s+(?:m[ée]dicos?|odontol[óo]gicos?|dentales?)|sanatorios?)"
_NOMBRE = r"[A-ZÁÉÍÓÚÑ][A-Za-zÁÉÍÓÚÑáéíóúñ.&-]+"
_ENLACE = r"(?:de|del|la|las|los|el|y|e)"
_PATRON = re.compile(rf"\b({_TIPO})((?:\s+{_ENLACE})*\s+{_NOMBRE}(?:(?:\s+{_ENLACE})*\s+{_NOMBRE}){{0,4}})")
_ORACION = re.compile(r"[^.\n]*")
# Palabras en mayúscula que en un condicionado no son nombres propios de una clínica
_GENERICAS = set("""la el los las un una su sus al del de y e o u no si en que donde cuando para por con sin se lo es son más como
compañía compania asegurado asegurada asegurados aseguradora contratante beneficiario beneficiarios póliza poliza red central
afiliada afiliado afiliadas afiliados proveedor proveedores titular médico medico médicos medicos odontólogo odontologo
tratante privada privado pública publico público particular general generales autorizada autorizado perú peru país pais
este esta estos estas dicho dicha ese esa cualquier cualquiera otro otra otros otras convenio convenios disponible disponibles
ios ias ia ei dei ai seguro seguros certificado condiciones cláusula clausula artículo articulo anexo plan""".split())
_GENERICAS = {sin_tildes(x) for x in _GENERICAS}


def _nombre_propio(resto: str) -> str | None:
    """El nombre propio que sigue al tipo, o None si lo que sigue son palabras genéricas."""
    palabras = resto.split()
    while palabras and sin_tildes(palabras[0].lower().strip(".,;:")) in _GENERICAS:
        palabras.pop(0)
    while palabras and sin_tildes(palabras[-1].lower().strip(".,;:")) in _GENERICAS:
        palabras.pop()
    propias = [p for p in palabras if p[0].isupper() and len(p.strip(".,;:")) >= 3 and sin_tildes(p.lower().strip(".,;:")) not in _GENERICAS]
    if not propias or not palabras[0][0].isupper():
        return None
    return " ".join(palabras).strip(".,;: ")


def nombradas(poliza: Poliza) -> list[dict]:
    """[{nombre, cita, seccion, articulo, pagina, paginas, verificacion}], sin repetir nombres."""
    salida, vistas = [], set()
    for t in poliza.indice.trozos:
        for m in _PATRON.finditer(t.texto):
            resto = m.group(2).split()
            if m.group(1).lower().endswith("s") and resto[0].lower() in ("de", "del", "la", "las", "los", "el", "y", "e"):
                continue  # "clínicas y hospitales del Perú": un plural seguido de un enlace no es un nombre
            propio = _nombre_propio(m.group(2))
            if propio is None:
                continue
            nombre = f"{m.group(1)} {propio}"
            clave = sin_tildes(nombre.lower())
            if clave in vistas:
                continue
            ini = t.texto.rfind(".", 0, m.start()) + 1
            fin = t.texto.find(".", m.end())
            fin = len(t.texto) if fin == -1 else fin + 1
            cita = t.texto[ini:fin].strip()
            ini = t.texto.index(cita, ini)
            paginas = t.paginas_de(m.start(), m.end()) or t.paginas
            verificacion = verificar_en_pdf(poliza.pdf_bytes, [(paginas[0], t.texto[m.start():m.end()])], poliza.paginas_leidas)
            if not any(verificacion.values()):
                continue  # el nombre no está en esa página del PDF: no se muestra
            vistas.add(clave)
            salida.append({"nombre": nombre, "cita": cita, "seccion": t.seccion,
                           "articulo": t.articulo + (f" (parte {t.parte} de {t.partes})" if t.partes > 1 else ""),
                           "pagina": paginas[0], "paginas": paginas, "verificacion": verificacion})
    return salida

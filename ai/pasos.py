"""Qué hacer ahora: los pasos para reclamar y la fecha límite (Fase 2, funciones c y d).

De la póliza salen el plazo de aviso, a quién avisar, qué documentos presentar y el
procedimiento. El modelo los redacta a partir de los pasajes y cita cada uno; el código:

- verifica cada cita contra el pasaje y contra la página del PDF, como en las respuestas;
- descarta lo que no tenga cita válida;
- acepta un plazo solo si su número está escrito en su cita (en cifras o en palabras);
- calcula la fecha límite sumando ese plazo a la fecha del hecho que indicó la persona.

Si la póliza no trae un plazo de aviso, se dice: no se asume ninguno.
"""

from __future__ import annotations

from datetime import date

from ai.fechas import fecha_en_texto, fecha_limite, numero_en_texto
from ai.llm import ErrorLLM, Proveedor, obtener_proveedor
from ai.prompts import SEGURIDAD, nueva_marca
from ai.recuperacion import Pasaje, pasajes_xml, recuperar
from ai.respuesta import Poliza, citas_verificadas, mencionadas_ausentes

CONSULTA = ("Aviso del siniestro: plazo para avisar, a quién y por qué medio avisar, documentos que hay que presentar "
            "y procedimiento para solicitar la cobertura o el reembolso")
VARIANTES = ["aviso del siniestro plazo días", "documentos para solicitar la cobertura", "procedimiento en caso de siniestro reembolso"]

SISTEMA_PASOS = """\
Extraes de una póliza de seguro lo que el asegurado tiene que hacer para reclamar, usando \
únicamente los pasajes de esa póliza que te entrego entre etiquetas <pasaje>. Quien lee es \
un asegurado sin formación legal.

Reglas que no se rompen:
1. Usa solo lo que dicen los pasajes. No uses lo que sepas de seguros ni de leyes. Si un \
plazo, un teléfono, un documento o un paso no está escrito en un pasaje, no existe para ti.
2. Cada elemento lleva los números de las citas que lo respaldan. Una cita es un fragmento \
copiado exactamente, carácter por carácter, de un solo pasaje y de una sola parte seguida de \
él, de una a tres oraciones. Numera las citas desde 1 en el campo "n".
3. No des consejo legal ni recomiendes nada que la póliza no diga.

Campos:
- citas: las pruebas, en el orden en que las uses.
- plazos: cada plazo para dar aviso del siniestro o para presentar la solicitud que los \
pasajes fijen con un número. "para" dice a qué aplica (por ejemplo "avisar del siniestro", \
"avisar a la central de asistencia", "presentar los documentos del reembolso"); "cantidad" es \
el número; "unidad" es "dias" u "horas"; "tipo_dias" es "habiles" o "calendario" solo si el \
pasaje lo dice, y si no "no_dice"; "desde" copia desde cuándo corre el plazo según el pasaje \
(por ejemplo "desde que tuvo conocimiento de la ocurrencia"); "cita" es el número de la cita \
donde está escrito ese número. Si un pasaje dice "tan pronto como sea posible" sin número, no \
es un plazo: ponlo en pasos. Si no hay ningún plazo con número, lista vacía.
- a_quien_avisar: a quién y por qué medio se avisa (central de asistencia, teléfono, correo, \
oficinas), tal como esté en los pasajes.
- documentos: los documentos que hay que presentar, uno por elemento.
- pasos: el procedimiento en orden, en lenguaje simple, sin repetir lo anterior.

"""

_ITEM = {"type": "object", "properties": {"descripcion": {"type": "string"}, "citas": {"type": "array", "items": {"type": "integer"}}},
         "required": ["descripcion", "citas"], "additionalProperties": False}
ESQUEMA_PASOS = {
    "type": "object",
    "properties": {
        "citas": {"type": "array", "items": {
            "type": "object",
            "properties": {"n": {"type": "integer"}, "pasaje": {"type": "string"}, "texto_literal": {"type": "string"}},
            "required": ["n", "pasaje", "texto_literal"], "additionalProperties": False}},
        "plazos": {"type": "array", "items": {
            "type": "object",
            "properties": {"para": {"type": "string"}, "cantidad": {"type": "integer"},
                           "unidad": {"type": "string", "enum": ["dias", "horas"]},
                           "tipo_dias": {"type": "string", "enum": ["habiles", "calendario", "no_dice"]},
                           "desde": {"type": "string"}, "cita": {"type": "integer"}},
            "required": ["para", "cantidad", "unidad", "tipo_dias", "desde", "cita"], "additionalProperties": False}},
        "a_quien_avisar": {"type": "array", "items": _ITEM},
        "documentos": {"type": "array", "items": _ITEM},
        "pasos": {"type": "array", "items": _ITEM},
    },
    "required": ["citas", "plazos", "a_quien_avisar", "documentos", "pasos"],
    "additionalProperties": False,
}


def buscar(poliza: Poliza, situacion: str = "") -> list[Pasaje]:
    consulta = f"{CONSULTA}. {situacion}".strip() if situacion else CONSULTA
    return recuperar(poliza.indice, consulta, VARIANTES, [], k=6, continuar=3, maximo=14, presupuesto_caracteres=11000)


def validar(crudo: dict, pasajes: list[Pasaje], poliza: Poliza, hecho: date | None) -> dict:
    citas, renumerar, descartes = citas_verificadas(crudo["citas"], pasajes, poliza)
    por_n = {c["n"]: c for c in citas}

    def con_citas(items: list[dict], campo: str) -> list[dict]:
        salida = []
        for it in items:
            refs = [renumerar[n] for n in it["citas"] if n in renumerar]
            if refs and it["descripcion"].strip():
                salida.append({"descripcion": it["descripcion"].strip(), "citas": refs})
            else:
                descartes.append({"tipo": campo, "texto": it["descripcion"], "motivo": "sin cita válida"})
        return salida

    plazos = []
    for p in crudo["plazos"]:
        cita = por_n.get(renumerar.get(p["cita"]))
        if cita is None:
            descartes.append({"tipo": "plazo", "texto": f"{p['cantidad']} {p['unidad']}", "motivo": "sin cita válida"})
        elif p["cantidad"] < 1 or not numero_en_texto(p["cantidad"], cita["texto_literal"]):
            descartes.append({"tipo": "plazo", "texto": f"{p['cantidad']} {p['unidad']}", "motivo": "el número no está escrito en su cita"})
        else:
            plazos.append({"para": p["para"].strip(), "cantidad": p["cantidad"], "unidad": p["unidad"], "tipo_dias": p["tipo_dias"],
                           "desde": p["desde"].strip(), "cita": cita["n"],
                           "calculo": fecha_limite(hecho, p["cantidad"], p["unidad"], p["tipo_dias"]) if hecho else None})
    return {
        "plazos": plazos,
        "sin_plazo": None if plazos else "No encontré en tu póliza un plazo de aviso escrito con un número. Pregúntale a tu aseguradora.",
        "a_quien_avisar": con_citas(crudo["a_quien_avisar"], "a_quien_avisar"),
        "documentos": con_citas(crudo["documentos"], "documento"),
        "pasos": con_citas(crudo["pasos"], "paso"),
        "citas": citas,
        "descartes": descartes,
    }


def que_hacer(poliza: Poliza, situacion: str = "", fecha_hecho: date | None = None, proveedor: Proveedor | None = None) -> dict:
    """Los pasos para reclamar con sus citas y, si hay fecha del hecho, la fecha límite de cada
    plazo. La fecha sale de `fecha_hecho` o, si no viene, del texto de la situación."""
    proveedor = proveedor or obtener_proveedor()
    origen = "indicada" if fecha_hecho else None
    if fecha_hecho is None and situacion:
        hallada = fecha_en_texto(situacion)
        if hallada:
            fecha_hecho, origen = hallada[0], f"leída de «{hallada[1]}»"
    pasajes = buscar(poliza, situacion)
    base = {"pregunta": situacion, "documento": poliza.nombre,
            "fecha_hecho": fecha_hecho.isoformat() if fecha_hecho else None, "fecha_hecho_origen": origen,
            "falta_fecha": fecha_hecho is None,
            "mencionadas_ausentes": mencionadas_ausentes(pasajes, poliza)}
    marca = nueva_marca()
    usuario = (f"<datos_{marca}>\n<pasajes>\n{pasajes_xml(pasajes)}\n</pasajes>\n</datos_{marca}>\n\n"
               f"<situacion_del_asegurado>\n{situacion or '(no la indicó)'}\n</situacion_del_asegurado>")
    try:
        crudo, uso = proveedor.json("pasos", SISTEMA_PASOS + SEGURIDAD.format(marca=marca), usuario, ESQUEMA_PASOS)
    except ErrorLLM as e:
        return base | {"modo": "sin_modelo", "aviso": "No pude redactar los pasos ahora. Estas son las cláusulas de tu póliza sobre "
                       "el aviso del siniestro: léelas tú.", "error": type(e).__name__,
                       "pasajes": [{"id": p.id, "seccion": p.trozo.seccion, "articulo": p.trozo.articulo, "paginas": p.trozo.paginas,
                                    "texto": p.trozo.texto} for p in pasajes],
                       "plazos": [], "sin_plazo": None, "a_quien_avisar": [], "documentos": [], "pasos": [], "citas": [],
                       "uso": {"llamadas": 0, "costo_usd": 0.0, "segundos": 0.0, "detalle": []}}
    return base | {"modo": "pasos", "aviso": None} | validar(crudo, pasajes, poliza, fecha_hecho) | {
        "modelo_crudo": crudo,
        "uso": {"llamadas": 1, "costo_usd": round(uso.costo_usd, 6), "segundos": round(uso.segundos, 2), "detalle": [uso.a_dict()]}}

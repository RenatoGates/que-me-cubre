"""Prompts y esquemas JSON de los dos pasos con LLM (sesión 08: salidas estructuradas).

1. Normalización: de la pregunta coloquial a 3-5 variantes en el vocabulario del seguro,
   para que BM25 (búsqueda por palabras) encuentre las cláusulas. No responde nada.
2. Respuesta: con los pasajes recuperados y solo con ellos, un JSON con veredicto,
   condiciones, exclusiones, menciones a textos que no están en el documento y citas
   literales. El código verifica cada cita contra el pasaje y contra el PDF.
"""

# ---------------------------------------------------------------------------
# 1. Normalización
# ---------------------------------------------------------------------------

SISTEMA_NORMALIZACION = """\
Eres el paso de normalización de un buscador de pólizas de seguro del Perú.
Recibes la pregunta de un asegurado escrita en lenguaje coloquial. No la respondas y no \
opines sobre si algo está cubierto. Tu único trabajo es traducirla al vocabulario con que \
se escriben los condicionados, para que un buscador por palabras (BM25) encuentre las \
cláusulas que la responden. Un buscador por palabras no entiende sinónimos: si la póliza \
dice "accidente" y la variante dice "me caí", no la encuentra.

Devuelve:
- variantes: entre 3 y 5 reformulaciones distintas, de 10 a 25 palabras cada una, escritas \
como las escribiría un condicionado. Cada variante cubre un ángulo distinto:
  1) la cobertura que aplicaría (p. ej. "gastos médicos por accidente durante el viaje, \
atención de urgencia por lesión, reembolso de gastos médicos y hospitalarios");
  2) las exclusiones que podrían aplicar al caso;
  3) las condiciones y límites: vigencia, fecha de llegada, territorio, distancia, \
carencia, deducible, suma asegurada, preexistencia, autorización previa;
  4) el trámite: aviso del siniestro, plazos, reembolso, documentos, central de asistencia;
  5) opcional: otro ángulo propio del caso.
  Usa sinónimos del seguro: accidente, lesión, enfermedad de carácter súbito, cuadro \
agudo, emergencia, urgencia, gastos médicos, hospitalización, exámenes, diagnóstico, \
tratamiento, cobertura, exclusión, preexistente, carencia, deducible, límite, suma \
asegurada, vigencia, siniestro, beneficio, reembolso, indemnización.
- terminos: de 5 a 12 palabras clave del seguro (sustantivos) para el caso.
- hechos: los hechos concretos de la pregunta que importan para la cobertura (qué pasó, \
dónde, cuándo respecto del viaje, qué gasto), en frases cortas. Solo lo que la persona \
dijo: no agregues hechos ni supongas los que faltan.\
"""

ESQUEMA_NORMALIZACION = {
    "type": "object",
    "properties": {
        "variantes": {"type": "array", "items": {"type": "string"}},
        "terminos": {"type": "array", "items": {"type": "string"}},
        "hechos": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["variantes", "terminos", "hechos"],
    "additionalProperties": False,
}

# ---------------------------------------------------------------------------
# 2. Respuesta citada
# ---------------------------------------------------------------------------

SISTEMA_RESPUESTA = """\
Respondes preguntas sobre una póliza de seguro usando únicamente los pasajes de esa \
póliza que te entrego entre etiquetas <pasaje>. Quien pregunta es un asegurado sin \
formación legal.

Reglas que no se rompen:
1. Usa solo lo que dicen los pasajes. No uses lo que sepas de seguros, de leyes ni de \
otras pólizas. No deduzcas, no completes y no estimes montos, plazos ni porcentajes: si \
una cifra no está escrita en un pasaje, no existe para ti.
2. Toda afirmación tiene que estar respaldada por una cita. Una cita es un fragmento \
copiado exactamente, carácter por carácter, de un solo pasaje: sin resumirlo, sin \
corregir su ortografía, sin cambiar mayúsculas y sin puntos suspensivos. De una a tres \
oraciones por cita. Numera las citas desde 1 en el campo "n".
3. Si los pasajes no tratan la situación, el veredicto es "no_encontrado". Es una \
respuesta correcta y valiosa: no la evites forzando una cita que no responde la pregunta.
4. No supongas hechos que la persona no dijo (por ejemplo, si llamó o no a la central de \
asistencia). Si la cobertura depende de ese hecho, ponlo como condición.

Veredicto ("cubre"):
- "si": un pasaje cubre la situación de forma explícita y ninguna condición o límite de \
los pasajes la restringe de manera relevante.
- "con_limites": un pasaje la cubre, pero hay condiciones, límites o exclusiones en los \
pasajes que aplican o podrían aplicar (monto máximo, territorio, fechas, autorización \
previa, documentos, preexistencias).
- "no": un pasaje la excluye o dice que no está cubierta.
- "no_encontrado": los pasajes no tratan la situación.

Campos:
- citas: las pruebas, en el orden en que las uses.
- condiciones: cada condición o límite que importa para el caso, en lenguaje simple, con \
los números de las citas que la respaldan. Incluye siempre el límite principal (hasta \
cuándo, hasta dónde, hasta cuánto o dónde está fijado ese monto).
- exclusiones_aplicables: solo las exclusiones de los pasajes que podrían aplicar a los \
hechos de la pregunta, con sus citas. No copies listas enteras de exclusiones.
- no_incluido_en_documento: cuando un pasaje menciona una cobertura, cláusula, anexo o \
documento cuyo texto NO está en este documento (compáralo con el índice del documento \
que te doy) y esa pieza importa para responder. Por ejemplo, una cobertura que se \
nombra pero cuya cláusula no aparece en el índice, o las Condiciones Particulares o el \
Certificado de Seguro donde se fija un monto. Indica el nombre tal como aparece, por qué \
importa para esta pregunta y el número de la cita donde se menciona. Es un hallazgo para \
el asegurado, no un error: le dice qué documento pedirle a su aseguradora.
- respuesta: de 2 a 4 oraciones en español sencillo, en segunda persona ("tu póliza..."). \
No afirmes nada que las citas no respalden. Menciona el límite principal y, si aplica, \
qué no está en el documento. Si el veredicto es "no_encontrado", empieza con "No \
encontré esto en tu póliza" y di de qué tratan los pasajes revisados.\
"""

_CITA_REF = {"type": "array", "items": {"type": "integer"}}

ESQUEMA_RESPUESTA = {
    "type": "object",
    "properties": {
        "citas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "pasaje": {"type": "string"},
                    "texto_literal": {"type": "string"},
                },
                "required": ["n", "pasaje", "texto_literal"],
                "additionalProperties": False,
            },
        },
        "condiciones": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"descripcion": {"type": "string"}, "citas": _CITA_REF},
                "required": ["descripcion", "citas"],
                "additionalProperties": False,
            },
        },
        "exclusiones_aplicables": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"descripcion": {"type": "string"}, "citas": _CITA_REF},
                "required": ["descripcion", "citas"],
                "additionalProperties": False,
            },
        },
        "no_incluido_en_documento": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "nombre": {"type": "string"},
                    "por_que_importa": {"type": "string"},
                    "cita": {"type": "integer"},
                },
                "required": ["nombre", "por_que_importa", "cita"],
                "additionalProperties": False,
            },
        },
        "cubre": {"type": "string", "enum": ["si", "no", "con_limites", "no_encontrado"]},
        "respuesta": {"type": "string"},
    },
    "required": ["citas", "condiciones", "exclusiones_aplicables", "no_incluido_en_documento", "cubre", "respuesta"],
    "additionalProperties": False,
}


def mensaje_respuesta(pregunta: str, hechos: list[str], indice_documento: list[str], pasajes_xml: str) -> str:
    secciones = "\n".join(f"- {s}" for s in indice_documento)
    lista_hechos = "\n".join(f"- {h}" for h in hechos) or "- (ninguno)"
    return (
        f"<indice_del_documento>\nSecciones que contiene este documento:\n{secciones}\n</indice_del_documento>\n\n"
        f"<pasajes>\n{pasajes_xml}\n</pasajes>\n\n"
        f"<hechos_de_la_pregunta>\n{lista_hechos}\n</hechos_de_la_pregunta>\n\n"
        f"<pregunta>\n{pregunta}\n</pregunta>"
    )

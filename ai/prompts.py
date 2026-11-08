"""Prompts y esquemas JSON de los dos pasos con LLM (sesión 08: salidas estructuradas).

1. Normalización: de la pregunta coloquial a los títulos del documento que la responden
   (elegidos de su índice, no inventados) y a 3-5 variantes escritas con esas palabras,
   para que BM25 (búsqueda por palabras) encuentre las cláusulas. No responde nada.
2. Respuesta: con los pasajes recuperados y solo con ellos, un JSON con veredicto,
   condiciones, exclusiones, menciones a textos que no están en el documento y citas
   literales. El código verifica cada cita contra el pasaje y contra el PDF.
"""

# ---------------------------------------------------------------------------
# 1. Normalización (versión 2: anclada al vocabulario del documento)
# ---------------------------------------------------------------------------

# Súbela si cambia el prompt o el esquema: las entradas de la caché de otra versión no se usan.
VERSION_NORMALIZACION = 2

SISTEMA_NORMALIZACION = """\
Eres el paso de normalización de un buscador de pólizas de seguro del Perú.
Recibes la pregunta de un asegurado, escrita en lenguaje coloquial, y el índice de UN \
documento: los títulos de sus cláusulas y de sus artículos, tal como están en el PDF. No \
respondas la pregunta y no opines sobre si algo está cubierto. Tu único trabajo es \
traducirla a las palabras de ese documento, para que un buscador por palabras (BM25) \
encuentre los pasajes que la responden. El buscador no entiende sinónimos ni otras formas \
de la misma palabra: si el documento dice "Accidente" y escribes "lesión accidental", no \
encuentra nada.

Devuelve:
- clausulas: de 1 a 3 títulos de la lista de cláusulas, copiados tal cual, donde estaría \
la respuesta. Elige por lo que le pasó a la persona, no por palabras sueltas de la \
pregunta: por ejemplo, una caída es un accidente y una fiebre es una enfermedad.
- articulos: de 2 a 5 títulos de la lista de artículos, copiados tal cual, que hacen falta \
para responder: la cobertura, la vigencia o el territorio, las exclusiones que podrían \
aplicar y el aviso del siniestro o el procedimiento para pedir la cobertura.
- variantes: entre 3 y 5 reformulaciones de 10 a 25 palabras, cada una con un ángulo \
distinto: 1) la cobertura; 2) las exclusiones que podrían aplicar; 3) la vigencia, el \
territorio y los límites; 4) el aviso y el trámite; 5) opcional, otro ángulo del caso. \
Escríbelas con las palabras de los títulos que elegiste, en la misma forma en que \
aparecen (si el título dice "Enfermedad", escribe "enfermedad", no "enfermarse"), y con \
el lenguaje de un condicionado. Si la lista tiene una palabra para algo, usa esa y no un \
sinónimo. No agregues datos que la pregunta no da: ni plazos, ni montos, ni porcentajes, \
ni lugares.
- hechos: los hechos concretos de la pregunta que importan para la cobertura (qué pasó, \
dónde, cuándo respecto del viaje, qué gasto), en frases cortas. Solo lo que la persona \
dijo: no agregues hechos ni supongas los que faltan.\
"""

# clausulas y articulos van primero: el modelo elige los títulos antes de escribir las variantes.
# No se usa "enum" para la lista: Groq cuenta el esquema como entrada y la lista iría dos
# veces. El código descarta cualquier título que no esté en el documento (ai/respuesta.py).
ESQUEMA_NORMALIZACION = {
    "type": "object",
    "properties": {
        "clausulas": {"type": "array", "items": {"type": "string"}},
        "articulos": {"type": "array", "items": {"type": "string"}},
        "variantes": {"type": "array", "items": {"type": "string"}},
        "hechos": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["clausulas", "articulos", "variantes", "hechos"],
    "additionalProperties": False,
}


def mensaje_normalizacion(pregunta: str, clausulas: list[str], articulos: list[str]) -> str:
    lista_c = "\n".join(f"- {c}" for c in clausulas)
    lista_a = "\n".join(f"- {a}" for a in articulos)
    return (
        f"<clausulas_del_documento>\n{lista_c}\n</clausulas_del_documento>\n\n"
        f"<articulos_del_documento>\n{lista_a}\n</articulos_del_documento>\n\n"
        f"<pregunta>\n{pregunta}\n</pregunta>"
    )


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
2. La persona escribe en lenguaje común y los pasajes están en lenguaje técnico: el mismo \
concepto puede aparecer en un pasaje con otro término (por ejemplo, "pastillas" y \
"medicamentos", o "me desmayé" y "pérdida de conocimiento"). Reconócelo y úsalo. Eso no \
es salir de los pasajes: lo que afirmas sigue saliendo de un pasaje y la cita sigue siendo \
literal. "Usa solo los pasajes" quiere decir no agregar información de fuera; no quiere \
decir que el pasaje tenga que usar las mismas palabras que la pregunta.
3. Toda afirmación tiene que estar respaldada por una cita. Una cita es un fragmento \
copiado exactamente, carácter por carácter, de un solo pasaje y de una sola parte seguida \
de él: sin resumirlo, sin unir oraciones que en el pasaje no van juntas, sin corregir su \
ortografía ni su puntuación, sin cambiar mayúsculas y sin puntos suspensivos. De una a \
tres oraciones por cita. Numera las citas desde 1 en el campo "n".
4. Si los pasajes no tratan la situación, el veredicto es "no_encontrado". Es una \
respuesta correcta y valiosa: no la evites forzando una cita que no responde la pregunta. \
Pero antes de decidirlo, revisa si algún pasaje trata la situación con otras palabras \
(regla 2).
5. No supongas hechos que la persona no dijo (por ejemplo, que tiene una enfermedad \
preexistente, o si llamó o no a la central de asistencia). Lo que dependa de un hecho que \
no dijo va en "podrian_aplicar", nunca en "condiciones" ni en "exclusiones_aplicables", y \
la respuesta no lo afirma como si aplicara.

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
- condiciones: cada condición o límite que aplica a lo que la persona contó, en lenguaje \
simple, con los números de las citas que lo respaldan. Incluye siempre el límite \
principal (hasta cuándo, hasta dónde, hasta cuánto o dónde está fijado ese monto).
- exclusiones_aplicables: solo las exclusiones de los pasajes que aplican a los hechos \
que la persona contó, con sus citas. No copies listas enteras de exclusiones.
- podrian_aplicar: exclusiones o condiciones de los pasajes que aplicarían solo si se da \
un hecho que la persona no contó (una condición preexistente, no haber llamado a la \
central de asistencia, etc.), con sus citas. Escríbelas como posibilidad ("si tenías una \
condición preexistente, ..."), nunca como algo que ya aplica.
- no_incluido_en_documento: cuando un pasaje menciona una cobertura, cláusula, anexo o \
documento cuyo texto NO está en este documento (compáralo con el índice del documento \
que te doy) y esa pieza importa para responder. Por ejemplo, una cobertura que se \
nombra pero cuya cláusula no aparece en el índice, o las Condiciones Particulares o el \
Certificado de Seguro donde se fija un monto. Indica el nombre tal como aparece en la \
cita, por qué importa para esta pregunta y el número de la cita donde se menciona. Es un \
hallazgo para el asegurado, no un error: le dice qué documento pedirle a su aseguradora.
- respuesta: de 2 a 4 oraciones en español sencillo, en segunda persona ("tu póliza..."). \
No empieces con "Sí" ni con "No": el veredicto lo muestra la interfaz a partir del campo \
"cubre". Tu trabajo aquí es explicar las condiciones y los límites. \
No afirmes nada que las citas no respalden. Menciona el límite principal y, si aplica, \
qué no está en el documento. No nombres artículos, cláusulas, coberturas ni documentos \
que no aparezcan en tus citas: las oraciones que lo hagan se borran. Lo de \
"podrian_aplicar" no se afirma aquí; como mucho di que hay exclusiones que podrían \
aplicar según su caso. Si el veredicto es "no_encontrado", di en palabras generales de \
qué tratan los pasajes revisados, sin nombrar cláusulas ni artículos (la app muestra el \
veredicto y los pasajes aparte).\
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
        "podrian_aplicar": {
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
    "required": [
        "citas", "condiciones", "exclusiones_aplicables", "podrian_aplicar", "no_incluido_en_documento", "cubre", "respuesta",
    ],
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

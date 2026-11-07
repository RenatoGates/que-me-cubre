"""Flujo completo: pregunta -> normalización -> recuperación -> respuesta JSON verificada.

La validación es código, no confianza en el modelo:
- cada cita debe estar literal en un pasaje recuperado y en su página del PDF;
- condiciones, exclusiones y menciones sin cita válida se descartan;
- una "mención no incluida" se descarta si su nombre sí es una sección del documento;
- sin ninguna cita válida, el veredicto pasa a "no_encontrado".
Nada se guarda ni se registra: todo vive en memoria durante la llamada.
"""

from __future__ import annotations

from dataclasses import dataclass

from ai.indice import Indice, tokens
from ai.llm import Uso, llamar_json
from ai.prompts import (
    ESQUEMA_NORMALIZACION,
    ESQUEMA_RESPUESTA,
    SISTEMA_NORMALIZACION,
    SISTEMA_RESPUESTA,
    mensaje_respuesta,
)
from ai.recuperacion import Pasaje, pasajes_xml, recuperar
from ai.verificacion import ubicar, verificar_en_pdf

MIN_VARIANTES, MAX_VARIANTES = 3, 5
ESFUERZO_NORMALIZACION = "low"
ESFUERZO_RESPUESTA = "medium"
NO_ENCONTRADO = "No encontré esto en tu póliza."


@dataclass
class Poliza:
    """Lo que el flujo necesita de una póliza: su índice y sus bytes para verificar citas."""

    doc_id: str
    nombre: str
    indice: Indice
    pdf_bytes: bytes

    @property
    def secciones(self) -> list[str]:
        return list(dict.fromkeys(t.seccion for t in self.indice.trozos))


# ---------------------------------------------------------------------------
# 1. Normalización
# ---------------------------------------------------------------------------


def normalizar(pregunta: str) -> tuple[dict, Uso]:
    datos, uso = llamar_json(SISTEMA_NORMALIZACION, pregunta, ESQUEMA_NORMALIZACION, ESFUERZO_NORMALIZACION, 4000)
    variantes = list(dict.fromkeys(v.strip() for v in datos["variantes"] if v.strip()))[:MAX_VARIANTES]
    terminos = list(dict.fromkeys(t.strip() for t in datos["terminos"] if t.strip()))
    ajuste = None
    if len(variantes) < MIN_VARIANTES:  # el esquema no puede exigir cantidades: se completa aquí
        ajuste = f"el modelo dio {len(variantes)} variantes; se completó con los términos y la pregunta"
        for extra in (" ".join(terminos), pregunta):
            if len(variantes) < MIN_VARIANTES and extra and extra not in variantes:
                variantes.append(extra)
    return {"variantes": variantes, "terminos": terminos, "hechos": datos["hechos"], "ajuste": ajuste}, uso


# ---------------------------------------------------------------------------
# 2. Validación de la respuesta
# ---------------------------------------------------------------------------

_GENERICOS = set(tokens("cobertura coberturas cláusula cláusulas adicional adicionales condiciones generales seguro póliza"))


def _es_seccion_del_documento(nombre: str, secciones: list[str]) -> bool:
    clave = set(tokens(nombre)) - _GENERICOS
    return bool(clave) and any(clave <= set(tokens(s)) for s in secciones)


def _validar(crudo: dict, pasajes: list[Pasaje], poliza: Poliza) -> tuple[dict, list[dict]]:
    por_id = {p.id: p for p in pasajes}
    descartes: list[dict] = []

    # Citas: literal en un pasaje -> página calculada -> presente en esa página del PDF
    citas, renumerar = [], {}
    for c in crudo["citas"]:
        # Primero el pasaje que el modelo indicó; si la cita no está ahí, los de su misma
        # sección (el texto repetido entre cláusulas no debe cambiar de cláusula), y al final el resto.
        indicado = por_id.get(c["pasaje"])
        misma = [p for p in pasajes if indicado and p is not indicado and p.trozo.seccion == indicado.trozo.seccion]
        candidatos = ([indicado] if indicado else []) + misma + [p for p in pasajes if p is not indicado and p not in misma]
        hallado = next(((p, u) for p in candidatos if (u := ubicar(p.trozo.texto, c["texto_literal"]))), None)
        if hallado is None:
            descartes.append({"tipo": "cita", "n": c["n"], "texto": c["texto_literal"], "motivo": "no está literal en ningún pasaje"})
            continue
        p, (a, b) = hallado
        t = p.trozo
        paginas = t.paginas_de(a, b) or t.paginas
        # El tramo citado del pasaje, partido por página (la cita ya coincide con t.texto[a:b])
        tramos = [(pag, t.texto[max(a, ini) : min(b, fin)]) for pag, ini, fin in t.segmentos if ini < b and fin > a]
        tramos_por_pagina: dict[int, str] = {}
        for pag, tramo in tramos:
            tramos_por_pagina[pag] = f"{tramos_por_pagina.get(pag, '')} {tramo}".strip()
        en_pdf = verificar_en_pdf(poliza.pdf_bytes, list(tramos_por_pagina.items()))
        if not any(en_pdf.values()):
            descartes.append({"tipo": "cita", "n": c["n"], "texto": c["texto_literal"], "motivo": f"no está en la página {paginas} del PDF"})
            continue
        nuevo = len(citas) + 1
        renumerar[c["n"]] = nuevo
        citas.append(
            {
                "n": nuevo,
                "documento": poliza.nombre,
                "seccion": t.seccion,
                "articulo": t.articulo + (f" (parte {t.parte} de {t.partes})" if t.partes > 1 else ""),
                "pagina": paginas[0],
                "paginas": paginas,
                "texto_literal": c["texto_literal"],
                "pasaje": p.id,
                "trozo_id": t.id,
                "posicion": [a, b],
                "verificacion": {"en_pasaje": True, **en_pdf},
            }
        )

    def con_citas(items: list[dict], campo: str) -> list[dict]:
        salida = []
        for it in items:
            refs = [renumerar[n] for n in it["citas"] if n in renumerar]
            if refs:
                salida.append({"descripcion": it["descripcion"], "citas": refs})
            else:
                descartes.append({"tipo": campo, "texto": it["descripcion"], "motivo": "sin cita válida"})
        return salida

    condiciones = con_citas(crudo["condiciones"], "condicion")
    exclusiones = con_citas(crudo["exclusiones_aplicables"], "exclusion")

    no_incluido = []
    for m in crudo["no_incluido_en_documento"]:
        if m["cita"] not in renumerar:
            descartes.append({"tipo": "no_incluido", "texto": m["nombre"], "motivo": "sin cita válida"})
        elif _es_seccion_del_documento(m["nombre"], poliza.secciones):
            descartes.append({"tipo": "no_incluido", "texto": m["nombre"], "motivo": "sí es una sección del documento"})
        else:
            no_incluido.append({"nombre": m["nombre"], "por_que_importa": m["por_que_importa"], "cita": renumerar[m["cita"]]})

    cubre, respuesta = crudo["cubre"], crudo["respuesta"].strip()
    degradado = False
    if cubre != "no_encontrado" and not citas:
        cubre, degradado = "no_encontrado", True
        respuesta = f"{NO_ENCONTRADO} No pude respaldar ninguna afirmación con una cita literal del documento."
        condiciones, exclusiones, no_incluido = [], [], []
    elif cubre == "no_encontrado" and not respuesta.startswith("No encontré"):
        respuesta = f"{NO_ENCONTRADO} {respuesta}"

    return (
        {
            "cubre": cubre,
            "respuesta": respuesta,
            "condiciones": condiciones,
            "exclusiones_aplicables": exclusiones,
            "no_incluido_en_documento": no_incluido,
            "citas": citas,
            "veredicto_degradado": degradado,
        },
        descartes,
    )


# ---------------------------------------------------------------------------
# 3. Flujo
# ---------------------------------------------------------------------------


def responder(pregunta: str, poliza: Poliza, k: int = 8) -> dict:
    norm, uso_n = normalizar(pregunta)
    pasajes = recuperar(poliza.indice, pregunta, norm["variantes"], norm["terminos"], k=k)
    usuario = mensaje_respuesta(pregunta, norm["hechos"], poliza.secciones, pasajes_xml(pasajes))
    crudo, uso_r = llamar_json(SISTEMA_RESPUESTA, usuario, ESQUEMA_RESPUESTA, ESFUERZO_RESPUESTA)
    final, descartes = _validar(crudo, pasajes, poliza)

    revisadas = list(dict.fromkeys(f"{p.trozo.seccion} › {p.trozo.articulo}" for p in pasajes))
    return {
        "pregunta": pregunta,
        "documento": poliza.nombre,
        **final,
        "secciones_revisadas": revisadas,
        "pasajes": [
            {
                "id": p.id,
                "rango": p.rango,
                "trozo_id": p.trozo.id,
                "seccion": p.trozo.seccion,
                "articulo": p.trozo.articulo,
                "parte": [p.trozo.parte, p.trozo.partes],
                "paginas": p.trozo.paginas,
                "texto": p.trozo.texto,
            }
            for p in pasajes
        ],
        "normalizacion": norm,
        "modelo_crudo": crudo,
        "descartes": descartes,
        "uso": {
            "normalizacion": uso_n.a_dict(),
            "respuesta": uso_r.a_dict(),
            "costo_usd": round(uso_n.costo_usd + uso_r.costo_usd, 5),
            "segundos": round(uso_n.segundos + uso_r.segundos, 2),
        },
    }

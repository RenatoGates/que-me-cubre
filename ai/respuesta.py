"""Flujo completo: pregunta -> normalización -> recuperación -> respuesta JSON verificada.

La validación es código, no confianza en el modelo:
- cada cita debe estar literal en un pasaje recuperado y en su página del PDF (la única
  tolerancia es el signo de puntuación final: ai/verificacion.py);
- condiciones, exclusiones, "podrían aplicar" y menciones sin cita válida se descartan;
- una "mención no incluida" se descarta si su nombre no está en su cita o si sí es una
  sección del documento;
- el texto libre (respuesta y descripciones) no puede nombrar artículos, numerales,
  códigos de cobertura, documentos ni títulos de cláusula que no estén en las citas
  verificadas: la oración que lo hace se recorta;
- el veredicto es el campo estructurado "cubre" y la interfaz lo muestra arriba como
  etiqueta ("etiqueta_veredicto"); el texto del modelo va debajo, como explicación, y el
  prompt le pide no empezar con "Sí" ni con "No". Si aun así abre contradiciendo el
  veredicto ("Sí, está cubierta…" con "con límites"), no se borra nada: queda marcado en
  "apertura_contradictoria" para la auditoría, y la etiqueta de arriba sigue mandando;
- sin ninguna cita válida, el veredicto pasa a "no_encontrado".

Aparte, sin pasar por el modelo: si un pasaje recuperado menciona una cobertura, un anexo o
un documento cuyo texto no está en el PDF (B4, Condiciones Particulares…), la salida trae
el bloque "mencionadas_ausentes" con la mención literal, su página y el aviso de pedírselo
a la aseguradora (ai/referencias.py). Sale siempre, también en la red de seguridad, con dos
niveles: "clausula_ausente" (cobertura o anexo con nombre propio, como B4: arriba y
resaltado) y "remision" (Condiciones Particulares, Certificado…: debajo y plegado).

Límite que el código no cubre: la verificación garantiza que cada cita existe literal en
su página, no que la conclusión se siga de las citas. Eso puede fallar en las dos
direcciones (un "sí" o un "no" apoyados en citas reales que no lo dicen).

Red de seguridad: si el proveedor llega a su límite, no responde o el modelo no genera un
JSON válido, el resultado sale en modo "solo_clausulas": los pasajes encontrados con las
palabras de búsqueda resaltadas, sin texto generado y con un aviso de por qué. No se cambia
de modelo ni se reintenta (un reintento gasta otra consulta del límite por minuto).

Nada se guarda ni se registra: todo vive en memoria durante la llamada.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field

from ai import cache_normalizacion
from ai.indice import Indice, limpiar_titulo, tokens
from ai.llm import LimiteAlcanzado, Proveedor, ProveedorNoDisponible, SalidaInvalida, Uso, obtener_proveedor
from ai.prompts import (
    ESQUEMA_NORMALIZACION,
    ESQUEMA_RESPUESTA,
    SISTEMA_NORMALIZACION,
    SISTEMA_RESPUESTA,
    mensaje_normalizacion,
    mensaje_respuesta,
)
from ai.recuperacion import Pasaje, pasajes_xml, recuperar, recuperar_normalizada, resaltar
from ai.referencias import MENSAJE
from ai.verificacion import partir_primera_oracion, recortar, ubicar_cita, verificar_en_pdf

MIN_VARIANTES, MAX_VARIANTES = 3, 5
NO_ENCONTRADO = "No encontré esto en tu póliza."
# El veredicto que se muestra sale de aquí, del campo estructurado, nunca del texto del modelo.
ETIQUETA_VEREDICTO = {
    "si": "Cubre",
    "con_limites": "Cubre con límites",
    "no": "No cubre",
    "no_encontrado": "No está en tu póliza",
    None: "Sin veredicto",
}


@dataclass
class Poliza:
    """Lo que el flujo necesita de una póliza: su índice y sus bytes para verificar citas."""

    doc_id: str
    nombre: str
    indice: Indice
    pdf_bytes: bytes
    _sha256: str | None = field(default=None, repr=False)

    @property
    def secciones(self) -> list[str]:
        return list(dict.fromkeys(t.seccion for t in self.indice.trozos))

    @property
    def sha256(self) -> str:
        if self._sha256 is None:
            self._sha256 = hashlib.sha256(self.pdf_bytes).hexdigest()
        return self._sha256


# ---------------------------------------------------------------------------
# 1. Normalización
# ---------------------------------------------------------------------------


def _del_documento(elegidos: list[str], lista: list[str]) -> tuple[list[str], list[str]]:
    """Los títulos elegidos que existen en el documento, con su texto exacto del PDF, y los
    que no. Se comparan por sus palabras (sin mayúsculas, tildes ni numeración)."""
    por_clave = {" ".join(tokens(t)): t for t in lista}
    validos, fuera = [], []
    for e in elegidos:
        limpio = limpiar_titulo(e) or ""
        t = por_clave.get(" ".join(tokens(limpio)))
        if t and t not in validos:
            validos.append(t)
        elif not t and e.strip():
            fuera.append(e.strip())
    return validos, fuera


def normalizar(pregunta: str, proveedor: Proveedor, indice: Indice) -> tuple[dict, Uso]:
    """Variantes de búsqueda y títulos del documento para la pregunta. Los títulos solo
    pueden ser del índice del documento: el modelo elige de la lista y el código descarta
    lo que no esté en ella."""
    clausulas_doc, articulos_doc = indice.vocabulario()
    usuario = mensaje_normalizacion(pregunta, clausulas_doc, articulos_doc)
    datos, uso = proveedor.json("normalizacion", SISTEMA_NORMALIZACION, usuario, ESQUEMA_NORMALIZACION)
    clausulas, fuera_c = _del_documento(datos["clausulas"], clausulas_doc)
    articulos, fuera_a = _del_documento(datos["articulos"], articulos_doc)
    titulos = clausulas + articulos
    variantes = list(dict.fromkeys(v.strip() for v in datos["variantes"] if v.strip()))[:MAX_VARIANTES]
    ajustes = []
    if fuera_c or fuera_a:
        ajustes.append(f"se descartaron títulos que no están en el documento: {fuera_c + fuera_a}")
    if len(variantes) < MIN_VARIANTES:  # el esquema no puede exigir cantidades: se completa aquí
        ajustes.append(f"el modelo dio {len(variantes)} variantes; se completó con los títulos y la pregunta")
        for extra in (" ".join(titulos), pregunta):
            if len(variantes) < MIN_VARIANTES and extra and extra not in variantes:
                variantes.append(extra)
    return {
        "variantes": variantes,
        "titulos": titulos,
        "clausulas": clausulas,
        "articulos": articulos,
        "hechos": datos["hechos"],
        "ajuste": "; ".join(ajustes) or None,
    }, uso


# ---------------------------------------------------------------------------
# 2. Validación de la respuesta
# ---------------------------------------------------------------------------

_GENERICOS = set(tokens("cobertura coberturas cláusula cláusulas adicional adicionales condiciones generales seguro póliza"))


def _es_seccion_del_documento(nombre: str, secciones: list[str]) -> bool:
    clave = set(tokens(nombre)) - _GENERICOS
    return bool(clave) and any(clave <= set(tokens(s)) for s in secciones)


def mencionadas_ausentes(pasajes: list[Pasaje], poliza: Poliza) -> list[dict]:
    """Coberturas, anexos y documentos que los pasajes recuperados mencionan y cuyo texto no
    está en el PDF. Lo calcula el código: la mención es literal del pasaje y la página sale
    de su posición, como en las citas. Primero coberturas y anexos, después documentos."""
    por_trozo = poliza.indice.ausentes()
    salida, vistas = [], set()
    for p in pasajes:
        t = p.trozo
        for m in por_trozo.get(t.id, []):
            if m.clave in vistas:
                continue
            vistas.add(m.clave)
            paginas = t.paginas_de(m.inicio, m.fin) or t.paginas
            salida.append({
                "nombre": m.nombre,
                "tipo": m.tipo,
                "mensaje": MENSAJE.format(m.nombre),
                "mencion": t.texto[m.inicio : m.fin],
                "seccion": t.seccion,
                "articulo": t.articulo + (f" (parte {t.parte} de {t.partes})" if t.partes > 1 else ""),
                "pagina": paginas[0],
                "paginas": paginas,
                "pasaje": p.id,
                "trozo_id": t.id,
                "posicion": [m.inicio, m.fin],
                # Jerarquía para mostrarlo: arriba y resaltada la cobertura o el anexo con nombre
                # propio (B4); debajo y plegadas las remisiones genéricas (Condiciones
                # Particulares, Certificado), que salen en casi todas las respuestas.
                "nivel": "remision" if m.tipo == "documento" else "clausula_ausente",
            })
    return sorted(salida, key=lambda x: x["nivel"] == "remision")  # estable: dentro de cada nivel, orden de aparición


_ABRE_SI = re.compile(r"^\W*(?:sí\b|si(?=\s*[,.;:!]))", re.IGNORECASE)  # "Sí, …"; no "Si la radiografía…"
_ABRE_NO = re.compile(r"^\W*no\b(?!\s+(?:obstante|solo|sólo)\b)", re.IGNORECASE)  # no "No obstante, …"


def apertura_contradictoria(respuesta: str, cubre: str) -> str | None:
    """"Sí" o "No" si el texto abre con esa palabra y el veredicto dice otra cosa."""
    if _ABRE_SI.match(respuesta) and cubre != "si":
        return "Sí"
    if _ABRE_NO.match(respuesta) and cubre not in ("no", "no_encontrado"):
        return "No"
    return None


def _misma_referencia(nombre: str, ausente: dict) -> bool:
    """¿El "no incluido" del modelo es una referencia que ya está en el bloque determinista?"""
    codigo, _, titulo = ausente["nombre"].partition(" - ")
    if ausente["tipo"] != "documento" and re.search(rf"\b{re.escape(codigo)}\b", nombre, re.IGNORECASE):
        return True
    clave = set(tokens(titulo or ausente["nombre"]))
    return bool(clave) and clave <= set(tokens(nombre))


def _validar(crudo: dict, pasajes: list[Pasaje], poliza: Poliza, ausentes: list[dict] | None = None) -> tuple[dict, list[dict]]:
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
        hallado = next(((p, u) for p in candidatos if (u := ubicar_cita(p.trozo.texto, c["texto_literal"]))), None)
        if hallado is None:
            descartes.append({"tipo": "cita", "n": c["n"], "texto": c["texto_literal"], "motivo": "no está literal en ningún pasaje"})
            continue
        p, ((a, b), literal, signo_ignorado) = hallado
        t = p.trozo
        paginas = t.paginas_de(a, b) or t.paginas
        # El tramo citado del pasaje, partido por página (la cita ya coincide con t.texto[a:b])
        tramos_por_pagina: dict[int, str] = {}
        for pag, ini, fin in t.segmentos:
            if ini < b and fin > a:
                tramos_por_pagina[pag] = f"{tramos_por_pagina.get(pag, '')} {t.texto[max(a, ini) : min(b, fin)]}".strip()
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
                "texto_literal": literal,
                "pasaje": p.id,
                "trozo_id": t.id,
                "posicion": [a, b],
                "verificacion": {"en_pasaje": True, "puntuacion_final_ignorada": signo_ignorado, **en_pdf},
            }
        )

    # Texto libre: no puede nombrar artículos, cláusulas ni documentos ausentes de las citas
    clausulas_doc = poliza.indice.vocabulario()[0]

    def sin_referencias_ajenas(texto: str, campo: str) -> str:
        recortado, quitadas = recortar(texto, citas, clausulas_doc)
        for q in quitadas:
            descartes.append({"tipo": "texto", "campo": campo, "texto": q["oracion"],
                              "motivo": f"nombra {', '.join(q['nombra'])}, que no está en las citas verificadas"})
        return recortado

    def con_citas(items: list[dict], campo: str) -> list[dict]:
        salida = []
        for it in items:
            refs = [renumerar[n] for n in it["citas"] if n in renumerar]
            if not refs:
                descartes.append({"tipo": campo, "texto": it["descripcion"], "motivo": "sin cita válida"})
                continue
            descripcion = sin_referencias_ajenas(it["descripcion"], campo)
            if descripcion:
                salida.append({"descripcion": descripcion, "citas": refs})
        return salida

    condiciones = con_citas(crudo["condiciones"], "condicion")
    exclusiones = con_citas(crudo["exclusiones_aplicables"], "exclusion")
    podrian_aplicar = con_citas(crudo.get("podrian_aplicar", []), "podria_aplicar")

    no_incluido = []
    for m in crudo["no_incluido_en_documento"]:
        cita = next((c for c in citas if c["n"] == renumerar.get(m["cita"])), None)
        tn, tc = tokens(m["nombre"]), tokens(cita["texto_literal"]) if cita else []
        if cita is None:
            descartes.append({"tipo": "no_incluido", "texto": m["nombre"], "motivo": "sin cita válida"})
        elif not tn or not any(tc[i : i + len(tn)] == tn for i in range(len(tc) - len(tn) + 1)):
            descartes.append({"tipo": "no_incluido", "texto": m["nombre"], "motivo": "el nombre no está en su cita"})
        elif _es_seccion_del_documento(m["nombre"], poliza.secciones):
            descartes.append({"tipo": "no_incluido", "texto": m["nombre"], "motivo": "sí es una sección del documento"})
        elif any(_misma_referencia(m["nombre"], a) for a in ausentes or []):
            descartes.append({"tipo": "no_incluido", "texto": m["nombre"], "motivo": "ya está en el bloque de mencionadas pero ausentes"})
        else:
            no_incluido.append({"nombre": m["nombre"], "por_que_importa": sin_referencias_ajenas(m["por_que_importa"], "no_incluido"),
                                "cita": cita["n"]})

    cubre, respuesta = crudo["cubre"], crudo["respuesta"].strip()
    degradado, apertura = False, None
    if cubre != "no_encontrado" and not citas:
        cubre, degradado = "no_encontrado", True
        respuesta = f"{NO_ENCONTRADO} No pude respaldar ninguna afirmación con una cita literal del documento."
        condiciones, exclusiones, podrian_aplicar, no_incluido = [], [], [], []
    else:
        respuesta = sin_referencias_ajenas(respuesta, "respuesta")
        palabra = apertura_contradictoria(respuesta, cubre)
        if palabra:  # se marca, no se borra: mutilar la oración es peor que el problema
            apertura = {"palabra": palabra, "veredicto": cubre, "oracion": partir_primera_oracion(respuesta)[0]}
        if cubre == "no_encontrado" and not respuesta.startswith("No encontré"):
            respuesta = f"{NO_ENCONTRADO} {respuesta}".strip()
        elif not respuesta:
            respuesta = "Revisa abajo las condiciones y las citas del documento."

    return (
        {
            "cubre": cubre,
            "etiqueta_veredicto": ETIQUETA_VEREDICTO[cubre],
            "respuesta": respuesta,
            "apertura_contradictoria": apertura,
            "condiciones": condiciones,
            "exclusiones_aplicables": exclusiones,
            "podrian_aplicar": podrian_aplicar,
            "no_incluido_en_documento": no_incluido,
            "citas": citas,
            "veredicto_degradado": degradado,
        },
        descartes,
    )


# ---------------------------------------------------------------------------
# 3. Flujo
# ---------------------------------------------------------------------------


def _pasajes_dict(pasajes: list[Pasaje], consultas: list[str] | None = None) -> list[dict]:
    return [
        {
            "id": p.id,
            "rango": p.rango,
            "trozo_id": p.trozo.id,
            "seccion": p.trozo.seccion,
            "articulo": p.trozo.articulo,
            "parte": [p.trozo.parte, p.trozo.partes],
            "paginas": p.trozo.paginas,
            "texto": p.trozo.texto,
            **({"resaltado": resaltar(p.trozo.texto, consultas)} if consultas else {}),
        }
        for p in pasajes
    ]


def _solo_clausulas(pregunta: str, poliza: Poliza, proveedor: Proveedor | None, norm: dict | None,
                    error: Exception, k: int, usos: list[Uso], desde_cache: bool = False) -> dict:
    """Red de seguridad: sin texto generado, solo las cláusulas encontradas, resaltadas."""
    if norm:
        consultas = [*norm["variantes"], *norm.get("clausulas", []), *norm.get("terminos", []), pregunta]
        pasajes = recuperar_normalizada(poliza.indice, pregunta, norm, k=k)
    else:  # sin normalización: búsqueda por palabras con la pregunta tal cual
        consultas = [pregunta]
        pasajes = recuperar(poliza.indice, pregunta, [], [], k=k, metodo="bm25_pregunta")
    if isinstance(error, LimiteAlcanzado):
        espera = f" Vuelve a intentar en unos {round(error.espera_segundos)} segundos." if error.espera_segundos else ""
        motivo = f"El proveedor del modelo alcanzó el límite de su plan gratuito.{espera}"
    elif isinstance(error, SalidaInvalida):
        motivo = "El modelo no devolvió una respuesta con el formato esperado esta vez; puedes volver a preguntar."
    else:
        motivo = "No pude comunicarme con el proveedor del modelo."
    aviso = (
        f"{motivo} No generé una respuesta: estas son las cláusulas de tu póliza que encontré para tu "
        "pregunta, con las palabras de búsqueda resaltadas. Léelas tú; aquí no hay un veredicto."
    )
    return {
        "modo": "solo_clausulas",
        "pregunta": pregunta,
        "documento": poliza.nombre,
        "aviso": aviso,
        "cubre": None,
        "etiqueta_veredicto": ETIQUETA_VEREDICTO[None],
        "respuesta": None,
        "apertura_contradictoria": None,
        "condiciones": [],
        "exclusiones_aplicables": [],
        "podrian_aplicar": [],
        "no_incluido_en_documento": [],
        "citas": [],
        "mencionadas_ausentes": mencionadas_ausentes(pasajes, poliza),
        "secciones_revisadas": list(dict.fromkeys(f"{p.trozo.seccion} › {p.trozo.articulo}" for p in pasajes)),
        "pasajes": _pasajes_dict(pasajes, consultas),
        "normalizacion": norm,
        "proveedor": _info_proveedor(proveedor),
        "error": type(error).__name__,
        "uso": _uso(usos, desde_cache),
    }


def _info_proveedor(proveedor: Proveedor | None) -> dict | None:
    if proveedor is None:
        return None
    return {
        "nombre": proveedor.nombre,
        "modelo": proveedor.modelos["respuesta"],
        "reutiliza_datos": proveedor.reutiliza_datos,
        "aviso": proveedor.aviso,
    }


def _uso(usos: list[Uso], desde_cache: bool) -> dict:
    return {
        "llamadas": len(usos),
        "normalizacion_desde_cache": desde_cache,
        "detalle": [u.a_dict() for u in usos],
        "tokens": sum(u.tokens_entrada + u.tokens_salida for u in usos),
        "costo_usd": 0.0,
        "segundos": round(sum(u.segundos for u in usos), 2),
    }


def responder(pregunta: str, poliza: Poliza, proveedor: Proveedor | None = None, k: int = 5) -> dict:
    proveedor = proveedor or obtener_proveedor()
    usos: list[Uso] = []

    norm = cache_normalizacion.buscar(pregunta, poliza.sha256)
    desde_cache = norm is not None
    if norm is None:
        try:
            norm, uso_n = normalizar(pregunta, proveedor, poliza.indice)
            usos.append(uso_n)
        except (LimiteAlcanzado, ProveedorNoDisponible, SalidaInvalida) as e:
            return _solo_clausulas(pregunta, poliza, proveedor, None, e, k, usos)

    pasajes = recuperar_normalizada(poliza.indice, pregunta, norm, k=k)
    usuario = mensaje_respuesta(pregunta, norm["hechos"], poliza.secciones, pasajes_xml(pasajes))
    try:
        crudo, uso_r = proveedor.json("respuesta", SISTEMA_RESPUESTA, usuario, ESQUEMA_RESPUESTA)
        usos.append(uso_r)
    except (LimiteAlcanzado, ProveedorNoDisponible, SalidaInvalida) as e:
        return _solo_clausulas(pregunta, poliza, proveedor, norm, e, k, usos, desde_cache)

    ausentes = mencionadas_ausentes(pasajes, poliza)
    final, descartes = _validar(crudo, pasajes, poliza, ausentes)
    return {
        "modo": "completo",
        "pregunta": pregunta,
        "documento": poliza.nombre,
        "aviso": None,
        **final,
        "mencionadas_ausentes": ausentes,
        "secciones_revisadas": list(dict.fromkeys(f"{p.trozo.seccion} › {p.trozo.articulo}" for p in pasajes)),
        "pasajes": _pasajes_dict(pasajes),
        "normalizacion": norm,
        "modelo_crudo": crudo,
        "descartes": descartes,
        "proveedor": _info_proveedor(proveedor),
        "uso": _uso(usos, desde_cache),
    }

"""¿Qué me cubre? Interfaz de Streamlit: cliente de la API (backend/main.py).

La pantalla es la misma del prototipo; lo que cambió es que ya no corre el pipeline aquí:
sube el PDF, pregunta y pide el mapa a la API (QMC_API_URL), la misma que usa la app móvil.
Muestra la respuesta con el contrato del README ("Cómo se muestra una respuesta"):

1. el veredicto arriba, como etiqueta, sacado del campo estructurado (`etiqueta_veredicto`);
2. el texto del modelo debajo, como explicación, con sus condiciones y exclusiones;
3. lo que la póliza menciona pero no trae: cláusulas con nombre propio (B4) resaltadas y
   remisiones genéricas (Condiciones Particulares, Certificado) plegadas;
4. las citas, cada una desplegable, con su texto literal, cláusula, artículo y página;
5. "exclusiones que podrían aplicar según tu caso", aparte y como posibilidad.

Privacidad: el PDF subido viaja a la API, que lo tiene solo en memoria; aquí no se guarda.

    uvicorn backend.main:app          # en otra terminal
    streamlit run app/app.py
"""

from __future__ import annotations

import datetime as dt
import hashlib
import html
import json
import os
import re
import uuid
from pathlib import Path

import httpx
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

POLIZA_TARAPOTO = "chubb_viajes_jetsmart"
COLORES = {  # fondo, texto, borde
    "si": ("#e3f4e8", "#14532d", "#4f9a69"),
    "con_limites": ("#fff3d1", "#6b4500", "#a67c00"),
    "no": ("#fde4e2", "#8a1c13", "#d0645a"),
    "no_encontrado": ("#eceff3", "#2f3640", "#7d8796"),
    "fuera_de_alcance": ("#eceff3", "#2f3640", "#7d8796"),
    None: ("#eceff3", "#2f3640", "#7d8796"),
}

st.set_page_config(page_title="¿Qué me cubre?", page_icon="🛡️", layout="centered")
st.markdown(
    """
    <style>
    .qmc-veredicto {font-size: 1.6rem; font-weight: 700; padding: .55rem 1rem; border-radius: .6rem;
                    border: 2px solid; display: inline-block; margin: .2rem 0 .8rem 0;}
    .qmc-pasaje {font-size: .92rem; line-height: 1.5; white-space: normal;}
    .qmc-pasaje mark {background: #ffe58a; color: #1d1d1d; padding: 0 .1em; border-radius: .15em;}
    .qmc-cita {border-left: 4px solid #4338CA; padding: .35rem 0 .35rem .9rem; margin: .3rem 0 .6rem 0;
               font-size: 1rem; line-height: 1.55;}
    /* Streamlit dibuja st.caption al 60 % de opacidad: sobre el fondo azul claro del tema queda en
       4,2:1, bajo el 4,5:1 de WCAG AA. Ahí van la página y la verificación de cada cita. */
    [data-testid="stCaptionContainer"] {opacity: .75;}

    /* Encabezado fijo de Streamlit con el mismo degradado que la banda, íconos en blanco */
    header[data-testid="stHeader"] {background: linear-gradient(90deg, #4C2FC9, #6366F1);}
    header[data-testid="stHeader"] button, header[data-testid="stHeader"] a,
    header[data-testid="stHeader"] span, header[data-testid="stHeader"] svg {color: #FFFFFF; fill: #FFFFFF;}
    [data-testid="stDecoration"] {display: none;}
    [data-testid="stMain"] {overflow-x: hidden;}
    [data-testid="stMainBlockContainer"] {padding-top: 3.75rem;}

    /* Banda del título a todo el ancho, pegada al encabezado */
    .qmc-banda {position: relative; z-index: 0; padding: 1.4rem 0 1.7rem 0; margin-bottom: .4rem;}
    /* el fondo sube por debajo del encabezado fijo para que banda y encabezado se vean como una sola pieza */
    .qmc-banda::before {content: ""; position: absolute; z-index: -1; top: -6rem; bottom: 0; left: 50%;
                        width: 100vw; transform: translateX(-50%);
                        background: linear-gradient(90deg, #4C2FC9, #6366F1);}
    [data-testid="stMarkdownContainer"] p.qmc-titulo {color: #FFFFFF; font-size: clamp(2rem, 7vw, 2.75rem) !important;
                 font-weight: 700; line-height: 1.15; margin: 0 0 .45rem 0;}
    /* Texto grande para WCAG (19 px en negrita): pide 3:1, y el blanco al 85 % da de 3,7:1 (extremo
       claro del degradado) a 6,4:1. A tamaño normal pediría 4,5:1 y no llegaría en el extremo claro. */
    [data-testid="stMarkdownContainer"] p.qmc-bajada {color: rgba(255, 255, 255, .85); font-size: 19px !important;
                 font-weight: 700; line-height: 1.4; margin: 0;}

    /* Tarjetas blancas: el contenido (y el texto de las cláusulas) siempre sobre blanco */
    div[class*="st-key-tarjeta_"] {background: #FFFFFF; border-radius: 12px; padding: 1.25rem 1.25rem 1rem;
                                   border: 1px solid rgba(22, 26, 46, .05);
                                   box-shadow: 0 1px 2px rgba(22, 26, 46, .05), 0 4px 14px rgba(22, 26, 46, .06);}

    /* Ejemplos: chicos, tipo enlace */
    /* Cuenta: tarjetas de póliza guardada y una zona de borrado que no se confunde con el resto */
    div[class*="st-key-poliza_g_"] {background: #F7F7FD; border: 1px solid #DCDDF3; border-radius: 12px; padding: 1rem 1rem .6rem;}
    div.st-key-zona_borrado {background: #FFF5F4; border: 1.5px solid #D0645A; border-radius: 12px; padding: 1rem 1rem .8rem;
                             margin-top: 1.2rem;}
    div[class*="st-key-borrar_"] button {border: 1.5px solid #B42318; color: #B42318; background: #FFFFFF;}
    div[class*="st-key-borrar_"] button:hover {background: #B42318; color: #FFFFFF; border-color: #B42318;}
    div[class*="st-key-borrar_"] button:hover p {color: #FFFFFF;}
    div.st-key-borrar_cuenta button {background: #B42318; color: #FFFFFF;}
    .qmc-plan {display: inline-block; padding: .15rem .6rem; border-radius: 999px; background: #E0E7FF; color: #3730A3;
               font-weight: 700; font-size: .85rem;}
    .qmc-vence {display: inline-block; padding: .15rem .6rem; border-radius: 999px; background: #FFF3D1; color: #6B4500;
                font-weight: 700; font-size: .85rem;}
    div[class*="st-key-tarapoto_"] button {padding: 0; min-height: 0; justify-content: flex-start;}
    div[class*="st-key-tarapoto_"] button p {font-size: .92rem; color: #4338CA; text-align: left;
                                              text-decoration: underline; text-underline-offset: 2px;}

    /* Cómo funciona: tres pasos debajo del título */
    [data-testid="stMarkdownContainer"] ol.qmc-pasos {list-style: none; display: flex; gap: .6rem;
                                                       margin: .1rem 0 .4rem 0; padding: 0;}
    ol.qmc-pasos li {flex: 1; display: flex; align-items: center; gap: .6rem; margin: 0; padding: .6rem .8rem;
                     background: #FFFFFF; border-radius: 12px; font-size: .95rem; line-height: 1.35;
                     box-shadow: 0 1px 2px rgba(22, 26, 46, .05), 0 4px 14px rgba(22, 26, 46, .06);}
    ol.qmc-pasos li span {flex: none; width: 1.7rem; height: 1.7rem; border-radius: 50%; background: #4338CA;
                          color: #FFFFFF; font-weight: 700; font-size: .9rem; display: inline-flex;
                          align-items: center; justify-content: center;}

    /* Condicionados de ejemplo: en letra chica, debajo de la subida */
    div.st-key-fuente p {font-size: .9rem !important;}

    @media (max-width: 640px) {
        [data-testid="stMarkdownContainer"] ol.qmc-pasos {flex-direction: column; gap: .35rem;}
        ol.qmc-pasos li {padding: .4rem .7rem; font-size: .92rem;}
        ol.qmc-pasos li span {width: 1.45rem; height: 1.45rem; font-size: .8rem;}
        .qmc-banda {padding: 1rem 0 1.25rem 0;}
        div[class*="st-key-tarjeta_"] {padding: 1rem .85rem .75rem;}
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# La API
# ---------------------------------------------------------------------------


def api_url() -> str:
    try:
        if "QMC_API_URL" in st.secrets:
            return str(st.secrets["QMC_API_URL"]).rstrip("/")
    except Exception:  # noqa: BLE001 - sin secrets.toml
        pass
    return os.environ.get("QMC_API_URL", "http://localhost:8000").rstrip("/")


class ErrorAPI(RuntimeError):
    def __init__(self, mensaje: str, codigo: str = "", status: int = 0) -> None:
        super().__init__(mensaje)
        self.codigo, self.status = codigo, status


def dispositivo() -> str:
    """Identificador de esta sesión del navegador: Streamlit no tiene uno que dure más."""
    if "dispositivo" not in st.session_state:
        st.session_state["dispositivo"] = f"web-{uuid.uuid4().hex}"
    return st.session_state["dispositivo"]


def api(metodo: str, ruta: str, **kwargs):
    # El servidor gratuito se duerme sin tráfico y tarda en despertar: de ahí el tiempo de espera largo.
    try:
        cabeceras = {"X-Dispositivo": dispositivo()}
        if st.session_state.get("token"):
            cabeceras["Authorization"] = f"Bearer {st.session_state['token']}"
        r = httpx.request(metodo, api_url() + ruta, headers=cabeceras, timeout=150.0, **kwargs)
    except httpx.HTTPError as e:
        raise ErrorAPI("No pude conectarme con el servidor. Si estaba dormido tarda cerca de un minuto en "
                       "despertar: vuelve a intentar.") from e
    if r.status_code >= 400:
        try:
            detalle = r.json().get("detail")
        except ValueError:
            detalle = None
        if isinstance(detalle, dict) and detalle.get("codigo") == "sesion_vencida":
            st.session_state.pop("token", None)
            st.session_state.pop("cuenta", None)
        if isinstance(detalle, dict):
            raise ErrorAPI(detalle.get("mensaje", "Error del servidor."), detalle.get("codigo", ""), r.status_code)
        raise ErrorAPI(f"El servidor respondió con un error ({r.status_code}).", status=r.status_code)
    return r.json()


@st.cache_data(ttl=600, show_spinner="Conectando con el servidor…")
def fuentes() -> dict[str, dict]:
    return {f["poliza_id"]: f for f in api("GET", "/polizas")}


@st.cache_data(ttl=600, show_spinner=False)
def info() -> dict:
    return api("GET", "/info")


def etiqueta_fuente(doc_id: str) -> str:
    f = fuentes()[doc_id]
    return f"{f['aseguradora']} · {f['producto']}"


def subir(pares: list[tuple[str, bytes]]) -> dict:
    return api("POST", "/polizas", files=[("archivos", (nombre, datos, "application/pdf")) for nombre, datos in pares])


def poliza_subida(archivos) -> dict:
    """Los PDF del usuario, uno o varios, como un solo documento. Se envían a la API, que los
    procesa en memoria; en esta sesión queda solo el identificador que devuelve."""
    pares = [(a.name, a.getvalue()) for a in archivos]
    clave = hashlib.sha256(b"".join(hashlib.sha256(d).digest() for _, d in pares)).hexdigest()
    guardada = st.session_state.get("poliza_subida")
    if guardada is not None and guardada["huella"] == clave:
        return guardada
    if guardada is not None:  # cambió de archivos: la anterior se borra del servidor
        try:
            api("DELETE", f"/polizas/{guardada['poliza_id']}")
        except ErrorAPI:
            pass
    poliza = subir(pares) | {"huella": clave}
    st.session_state["poliza_subida"] = poliza
    return poliza


def con_poliza(metodo: str, ruta: str, poliza: dict, archivos, cuerpo: dict | None = None):
    """Llama a la API con la póliza; si venció en la memoria del servidor (o este se reinició),
    la sube de nuevo y repite."""
    def llamar(poliza_id: str):
        if cuerpo is None:
            return api(metodo, ruta.format(poliza_id=poliza_id))
        return api(metodo, ruta, json=cuerpo | {"poliza_id": poliza_id})

    try:
        return llamar(poliza["poliza_id"])
    except ErrorAPI as e:
        if e.codigo != "poliza_no_encontrada" or not archivos:
            raise
    st.session_state.pop("poliza_subida", None)
    return llamar(poliza_subida(archivos)["poliza_id"])


def preguntar(poliza: dict, pregunta: str, archivos, aclaraciones: list[dict] | None = None) -> dict:
    return con_poliza("POST", "/preguntar", poliza, archivos, {"pregunta": pregunta, "aclaraciones": aclaraciones or []})


def ubicar_pagina(archivos: list[tuple[str, int]], pagina: int) -> tuple[str, int]:
    """Página de corrido → (archivo, página dentro de ese archivo)."""
    desde = 0
    for nombre, n in archivos:
        if pagina <= desde + n:
            return nombre, pagina - desde
        desde += n
    return archivos[-1][0], pagina - (desde - archivos[-1][1])


def paginas_con_archivo(archivos: list[tuple[str, int]], paginas: list[int]) -> str:
    (a1, p1), (a2, p2) = ubicar_pagina(archivos, paginas[0]), ubicar_pagina(archivos, paginas[-1])
    if a1 != a2:
        return f"{a1}, pág. {p1} – {a2}, pág. {p2}"
    return f"{a1}, pág. {p1}" if p1 == p2 else f"{a1}, págs. {p1}–{p2}"


# ---------------------------------------------------------------------------
# Presentación
# ---------------------------------------------------------------------------

_MD_ESPECIALES = re.compile(r"([\\`*_{}\[\]<>()#+|~$!])")


def md(texto: str) -> str:
    """Texto de la póliza o del modelo dentro de markdown, sin que se interprete ("US$ 100"
    no es una fórmula, "*" no es cursiva)."""
    return _MD_ESPECIALES.sub(r"\\\1", texto)


Archivos = list[tuple[str, int]]


def varios(archivos: Archivos | None) -> bool:
    return bool(archivos) and len(archivos) > 1


def paginas(c: dict, archivos: Archivos | None = None) -> str:
    ps = c.get("paginas") or [c.get("pagina")]
    if varios(archivos):  # la póliza vino en varios PDF: de qué archivo sale y su página en él
        return paginas_con_archivo(archivos, ps)
    return f"pág. {ps[0]}" if len(ps) == 1 else f"págs. {ps[0]}–{ps[-1]}"


def refs(numeros: list[int]) -> str:
    return f" (cita {numeros[0]})" if len(numeros) == 1 else f" (citas {', '.join(map(str, numeros))})"


def veredicto(r: dict) -> None:
    cubre = r.get("cubre")
    texto = r.get("etiqueta_veredicto") or "Sin veredicto"
    fondo, color, borde = COLORES.get(cubre, COLORES[None])
    st.markdown(
        f'<div class="qmc-veredicto" style="background:{fondo};color:{color};border-color:{borde}">'
        f"{html.escape(texto)}</div>",
        unsafe_allow_html=True,
    )


def explicacion(r: dict) -> None:
    st.markdown(md(r["respuesta"]))
    if r["condiciones"]:
        st.markdown("**Condiciones y límites**")
        st.markdown("\n".join(f"- {md(c['descripcion'])}{refs(c['citas'])}" for c in r["condiciones"]))
    if r["exclusiones_aplicables"]:
        st.markdown("**Exclusiones que aplican a lo que contaste**")
        st.markdown("\n".join(f"- {md(c['descripcion'])}{refs(c['citas'])}" for c in r["exclusiones_aplicables"]))


def nivel(m: dict) -> str:
    return m.get("nivel") or ("remision" if m["tipo"] == "documento" else "clausula_ausente")


def mencionadas_ausentes(r: dict, archivos: Archivos | None = None) -> None:
    bloque = r.get("mencionadas_ausentes", [])
    clausulas = [m for m in bloque if nivel(m) == "clausula_ausente"]
    remisiones = [m for m in bloque if nivel(m) == "remision"]
    del_modelo = r.get("no_incluido_en_documento", [])
    if not (clausulas or remisiones or del_modelo):
        return
    st.markdown("#### Lo que tu póliza menciona pero no trae")
    for m in clausulas:
        st.warning(
            f"**{md(m['mensaje'])}**\n\n"
            f"Se menciona en {md(m['seccion'])} › {md(m['articulo'])}, {paginas(m, archivos)}: «{md(m['mencion'])}»",
            icon="📄",
        )
    for m in del_modelo:
        st.warning(f"**{md(m['nombre'])}** no está en este documento. {md(m['por_que_importa'])}{refs([m['cita']])}",
                   icon="📄")
    if remisiones:
        with st.expander(f"Remisiones a otros documentos ({len(remisiones)}): ahí suelen estar los montos"):
            for m in remisiones:
                st.markdown(f"- {md(m['mensaje'])} Se menciona en {md(m['seccion'])} › {md(m['articulo'])}, "
                            f"{paginas(m, archivos)}.")


def citas(r: dict, archivos: Archivos | None = None) -> None:
    if not r["citas"]:
        return
    st.markdown("#### Citas de tu póliza")
    for c in r["citas"]:
        donde = paginas(c, archivos)
        with st.expander(f"Cita {c['n']} · {c['articulo']} · {donde}"):
            st.caption(f"{c['seccion']} › {c['articulo']} · {donde}")
            literal = html.escape(c["texto_literal"]).replace("\n", "<br>")
            st.markdown(f'<div class="qmc-cita">{literal}</div>', unsafe_allow_html=True)
            v = c["verificacion"]
            lectores = " y ".join(n for n in ("pdfplumber", "pypdf") if v.get(n))
            nota = (f"Verificada: el texto está literal en {donde} (leído con {lectores})." if varios(archivos)
                    else f"Verificada: el texto está literal en la {donde}, tal como se extrajo de tu PDF al subirlo (con {lectores}).")
            if v.get("puntuacion_final_ignorada"):
                nota += f" Se quitó el signo final «{v['puntuacion_final_ignorada']}» que agregó el modelo."
            st.caption(nota)


def podrian_aplicar(r: dict) -> None:
    if not r.get("podrian_aplicar"):
        return
    st.markdown("#### Exclusiones que podrían aplicar según tu caso")
    st.info(
        "No es lo que pasó: aplicarían solo si se da algo que no contaste.\n\n"
        + "\n".join(f"- {md(p['descripcion'])}{refs(p['citas'])}" for p in r["podrian_aplicar"]),
        icon="ℹ️",
    )


def pasaje_resaltado(p: dict) -> str:
    texto, marcas, partes, desde = p["texto"], p.get("resaltado", []), [], 0
    for a, b in marcas:
        partes += [html.escape(texto[desde:a]), f"<mark>{html.escape(texto[a:b])}</mark>"]
        desde = b
    partes.append(html.escape(texto[desde:]))
    return '<div class="qmc-pasaje">' + "".join(partes).replace("\n", "<br>") + "</div>"


def pasajes(r: dict, abiertos: bool, archivos: Archivos | None = None) -> None:
    for p in r["pasajes"]:
        etiqueta = f"{p['seccion']} › {p['articulo']} · {paginas(p, archivos)}"
        with st.expander(etiqueta, expanded=abiertos):
            st.markdown(pasaje_resaltado(p), unsafe_allow_html=True)


def fecha_larga(iso: str) -> str:
    return dt.date.fromisoformat(iso).strftime("%d/%m/%Y")


def mostrar_pasos(r: dict, archivos: Archivos | None = None) -> None:
    """Qué hacer ahora: primero la fecha límite, después a quién avisar, documentos y pasos."""
    if r["modo"] != "pasos":
        st.warning(r["aviso"], icon="⚠️")
        pasajes(r, abiertos=False, archivos=archivos)
        return
    for p in r["plazos"]:
        plazo = f"{p['cantidad']} {'horas' if p['unidad'] == 'horas' else 'días'}"
        c = p["calculo"]
        if c is None:
            st.warning(f"**Plazo para {md(p['para'])}: {plazo}**, {md(p['desde'])}{refs([p['cita']])}. "
                       "Indica cuándo ocurrió y calculo la fecha límite.", icon="⏳")
            continue
        cuanto = ("ya venció" if c["vencido"] else "vence hoy" if c["dias_restantes"] == 0
                  else f"quedan {c['dias_restantes']} día{'s' if c['dias_restantes'] != 1 else ''}")
        texto = (f"**Fecha límite para {md(p['para'])}: {fecha_larga(c['fecha_limite'])}** ({cuanto}). "
                 f"Son {plazo} {md(p['desde'])}{refs([p['cita']])}, contados desde el {fecha_larga(c['fecha_hecho'])}."
                 + "".join(f"\n\n{md(n)}" for n in c["notas"]))
        (st.error if c["vencido"] or c["dias_restantes"] <= 2 else st.warning)(texto, icon="⏳")
    if r["sin_plazo"]:
        st.info(r["sin_plazo"], icon="ℹ️")
    for titulo, campo, numerar in (("A quién avisar", "a_quien_avisar", False), ("Documentos que tienes que presentar", "documentos", False),
                                   ("Pasos", "pasos", True)):
        if r[campo]:
            st.markdown(f"**{titulo}**")
            st.markdown("\n".join(f"{f'{i}.' if numerar else '-'} {md(x['descripcion'])}{refs(x['citas'])}"
                                  for i, x in enumerate(r[campo], start=1)))
    mencionadas_ausentes(r | {"no_incluido_en_documento": []}, archivos)
    citas(r, archivos)


def mostrar_radiografia(r: dict) -> None:
    if r["modo"] != "radiografia":
        st.warning(r["aviso"], icon="⚠️")
    if r["coberturas"]:
        st.markdown("**Qué cubre y hasta cuánto**")
        st.markdown("\n".join(f"- **{md(c['nombre'])}:** {md(c['que_cubre'])} "
                              f"{'Hasta: ' + md(c['limite']) + '.' if c['limite'] else 'Monto: no está en este documento.'}{refs(c['citas'])}"
                              for c in r["coberturas"]))
    for titulo, campo in (("Exclusiones principales", "exclusiones"), ("Deducibles y copagos", "deducibles"),
                          ("Carencias y períodos de espera", "carencias")):
        st.markdown(f"**{titulo}**")
        if r[campo]:
            st.markdown("\n".join(f"- {md(x['descripcion'])}{refs(x['citas'])}" for x in r[campo]))
        else:
            st.caption(r.get("no_encontrado", {}).get(campo, "Sin datos."))
    mencionadas_ausentes(r | {"no_incluido_en_documento": []})
    citas(r)
    st.caption("Es un resumen de los pasajes más relevantes de tu póliza, no la póliza entera.")


def mostrar(r: dict, archivos: Archivos | None = None) -> None:
    if r.get("modo") == "varias":
        st.info(r["aviso"], icon="🧩")
        for i, sub in enumerate(r["respuestas"], start=1):
            st.markdown(f"##### Pregunta {i}: {md(sub['pregunta'])}")
            mostrar(sub, archivos)
        for q in r.get("sin_responder", []):
            st.warning(f"No respondí «{q}»: llegaste al límite de consultas de hoy.")
        return
    veredicto(r)
    if r.get("cubre") == "fuera_de_alcance":
        st.markdown(md(r["respuesta"]))
        return
    if r["modo"] != "completo":  # red de seguridad: sin texto generado
        st.warning(r["aviso"], icon="⚠️")
        mencionadas_ausentes(r, archivos)
        st.markdown("#### Cláusulas que encontré para tu pregunta")
        st.caption("Resaltadas, las palabras de la búsqueda. Aquí no hay un veredicto: léelas tú.")
        pasajes(r, abiertos=False, archivos=archivos)
        return
    explicacion(r)
    mencionadas_ausentes(r, archivos)
    citas(r, archivos)
    podrian_aplicar(r)
    with st.expander(f"Pasajes que revisé ({len(r['pasajes'])})"):
        st.caption("Lo que se le envió al modelo, en el orden de la búsqueda.")
        pasajes(r, abiertos=False, archivos=archivos)
    quien = r.get("proveedor") or {}
    st.caption(f"Modelo: {quien.get('modelo', '—')} en {quien.get('nombre', '—')} · costo de esta consulta: "
               f"USD {r['uso'].get('costo_usd', 0):.4f}")


# ---------------------------------------------------------------------------
# Tu póliza
# ---------------------------------------------------------------------------


def texto_limites(limites: dict) -> str:
    partes = []
    if limites.get("limite_dia") is not None:
        partes.append(f"{limites['restantes_hoy']} de {limites['limite_dia']} consultas por hoy")
    if limites.get("limite_mes") is not None:
        partes.append(f"{limites['restantes_mes']} de {limites['limite_mes']} este mes")
    extra = " Con una cuenta gratuita tienes más (pestaña «Mi cuenta»)." if limites.get("plan") == "sin_cuenta" else ""
    return "Te quedan " + " y ".join(partes) + "." + extra


def refrescar_cuenta() -> None:
    try:
        st.session_state["cuenta"] = api("GET", "/cuenta")
    except ErrorAPI:
        st.session_state.pop("cuenta", None)


def guardar_en_cuenta(poliza: dict) -> None:
    """Debajo de una póliza recién subida: guardarla en la cuenta, diciendo antes cuándo se borra."""
    cuenta = st.session_state.get("cuenta")
    if not cuenta:
        st.caption("¿Quieres no tener que subirla cada vez? Con una cuenta gratuita se guarda 7 días (pestaña «Mi cuenta»).")
        return
    dias = cuenta.get("dias_de_guardado")
    cuando = ((dt.date.today() + dt.timedelta(days=dias)).strftime("%d/%m/%Y") if dias else None)
    st.caption((f"Si la guardas, se borrará sola el {cuando} y tendrás que volver a subir el PDF." if cuando
                else "Si la guardas, queda en tu cuenta hasta que la borres.") + " Se guarda su texto, no el archivo PDF.")
    if st.button("Guardar esta póliza en mi cuenta", key="guardar_poliza"):
        try:
            hecho = api("POST", f"/polizas/{poliza['poliza_id']}/guardar")
            refrescar_cuenta()
            st.success(hecho["aviso"], icon="✅")
        except ErrorAPI as e:
            st.warning(str(e))


def formulario_de_entrada() -> None:
    avisos = api("GET", "/cuenta/avisos")
    if not avisos["disponible"]:
        st.info("Las cuentas todavía no están activadas en este servidor. Todo lo demás funciona igual sin cuenta.")
        return
    crear, entrar = st.tabs(["Crear cuenta", "Ya tengo cuenta"])
    with crear:
        st.info(avisos["guardado"], icon="🔒")
        correo = st.text_input("Correo", key="registro_correo")
        clave = st.text_input("Contraseña (8 caracteres o más)", type="password", key="registro_clave")
        st.warning(avisos["clave"], icon="🔑")
        acepto = st.checkbox(avisos["consentimiento"], value=False, key="registro_acepto")
        st.caption("Política de privacidad: docs/privacidad.md en el repositorio del proyecto.")
        if st.button("Crear mi cuenta", type="primary", key="registro_crear", disabled=not acepto):
            try:
                r = api("POST", "/cuenta/registro", json={"correo": correo, "clave": clave, "acepto_privacidad": acepto})
                st.session_state["token"], st.session_state["cuenta"] = r["token"], r["cuenta"]
                st.rerun()
            except ErrorAPI as e:
                st.error(str(e))
    with entrar:
        correo = st.text_input("Correo", key="entrar_correo")
        clave = st.text_input("Contraseña", type="password", key="entrar_clave")
        st.caption(avisos["clave"])
        if st.button("Entrar", type="primary", key="entrar_boton"):
            try:
                r = api("POST", "/cuenta/sesion", json={"correo": correo, "clave": clave})
                st.session_state["token"], st.session_state["cuenta"] = r["token"], r["cuenta"]
                st.rerun()
            except ErrorAPI as e:
                st.error(str(e))


def tarjeta_poliza_guardada(g: dict) -> None:
    with st.container(key=f"poliza_{g['poliza_id']}"):
        vence = (f'<span class="qmc-vence">Se borra sola el {g["borrado_automatico"]}</span>' if g.get("borrado_automatico")
                 else '<span class="qmc-plan">No se borra sola</span>')
        st.markdown(f"**{md(g['nombre'])}** · {g['paginas']} páginas &nbsp; {vence}", unsafe_allow_html=True)
        if g.get("borrado_automatico"):
            st.caption("Ese día se borra con su historial y tendrás que volver a subir el PDF.")
        with st.expander("Últimas consultas de esta póliza"):
            try:
                historial = api("GET", f"/polizas/{g['poliza_id']}/consultas")["consultas"]
            except ErrorAPI as e:
                historial = []
                st.caption(str(e))
            if not historial:
                st.caption("Todavía no hay consultas guardadas. Se guardan las últimas 20 que hagas sobre esta póliza.")
            for c in historial:
                izquierda, derecha = st.columns([5, 1])
                with izquierda:
                    st.markdown(f"**{md(c.get('pregunta', ''))}**")
                    for sub in c.get("respuestas", [c]):
                        st.markdown(f"*{sub.get('etiqueta_veredicto') or 'Sin veredicto'}.* {md(sub.get('respuesta') or sub.get('aviso') or '')}")
                        for cita in sub.get("citas", [])[:3]:
                            st.caption(f"Cita verificada · {cita['articulo']} · pág. {cita['pagina']}: «{cita['texto_literal'][:220]}»")
                with derecha:
                    if st.button("Borrar", key=f"borrar_c_{c['consulta_id']}", help="Borra solo esta consulta"):
                        api("DELETE", f"/consultas/{c['consulta_id']}")
                        st.rerun()
        pendiente = st.session_state.get("confirmar_borrado") == g["poliza_id"]
        if not pendiente:
            if st.button("Borrar esta póliza", key=f"borrar_p_{g['poliza_id']}"):
                st.session_state["confirmar_borrado"] = g["poliza_id"]
                st.rerun()
        else:
            st.warning("Se borrará esta póliza y todas sus consultas guardadas. No se puede deshacer.", icon="⚠️")
            si, no = st.columns(2)
            if si.button("Sí, borrarla", key=f"borrar_si_{g['poliza_id']}"):
                api("DELETE", f"/polizas/{g['poliza_id']}")
                st.session_state.pop("confirmar_borrado", None)
                refrescar_cuenta()
                st.rerun()
            if no.button("No, conservarla", key=f"conservar_{g['poliza_id']}"):
                st.session_state.pop("confirmar_borrado", None)
                st.rerun()


def pantalla_cuenta() -> None:
    with st.container(key="tarjeta_cuenta"):
        if st.session_state.pop("cuenta_borrada", False):
            st.success("Tu cuenta y todo lo guardado se borraron.", icon="✅")
        cuenta = st.session_state.get("cuenta")
        if not cuenta:
            st.markdown("#### Tu cuenta")
            st.markdown("Sin cuenta todo funciona igual y nada se guarda. Con una cuenta gratuita tienes más consultas y puedes "
                        "guardar tu póliza 7 días para no subirla cada vez.")
            formulario_de_entrada()
            return
        limites = cuenta["limites"]
        plan = "Plan de pago único" if cuenta["plan"] == "pagado" else "Plan gratuito"
        st.markdown(f"#### {md(cuenta['correo'])} &nbsp; <span class='qmc-plan'>{plan}</span>", unsafe_allow_html=True)
        st.caption(texto_limites(limites) + f" Pólizas guardadas: {len(cuenta['polizas'])} de {cuenta['polizas_permitidas']}.")
        if cuenta["plan"] != "pagado":
            st.info("**Plan de pago único (S/ 3,99):** hasta 4 pólizas guardadas sin borrado automático y 10 consultas al día. "
                    "El pago todavía no está disponible en la app.", icon="⭐")

        st.markdown("##### Tus pólizas guardadas")
        if not cuenta["polizas"]:
            st.caption("No tienes ninguna. Sube tu PDF en «Pregunta a tu póliza» y toca «Guardar esta póliza en mi cuenta».")
        for g in cuenta["polizas"]:
            tarjeta_poliza_guardada(g)

        if st.button("Cerrar sesión", key="cerrar_sesion"):
            try:
                api("DELETE", "/cuenta/sesion")
            except ErrorAPI:
                pass
            for clave in ("token", "cuenta", "guardada"):
                st.session_state.pop(clave, None)
            st.rerun()

        with st.container(key="zona_borrado"):
            st.markdown("##### Borrar mi cuenta y todo")
            st.markdown("Borra tu cuenta, tus pólizas guardadas, todo tu historial y tus contadores. Es inmediato y **no se puede "
                        "deshacer**. Después puedes seguir usando la app sin cuenta.")
            clave = st.text_input("Escribe tu contraseña para confirmar", type="password", key="borrar_clave")
            seguro = st.checkbox("Entiendo que se borra todo y no se puede recuperar", value=False, key="borrar_seguro")
            if st.button("Borrar mi cuenta y todo", key="borrar_cuenta", disabled=not (seguro and clave)):
                try:
                    api("DELETE", "/cuenta", json={"clave": clave})
                    for k in ("token", "cuenta", "guardada"):
                        st.session_state.pop(k, None)
                    st.session_state["cuenta_borrada"] = True
                    st.rerun()
                except ErrorAPI as e:
                    st.error(str(e))


def elegir_tarapoto(pregunta: str) -> None:
    """Ejemplo (solo visible con la póliza de Chubb): pone el texto exacto y pide responder."""
    st.session_state["fuente"] = POLIZA_TARAPOTO
    st.session_state["pregunta"] = pregunta
    st.session_state["consultar"] = True


def pedir_respuesta() -> None:
    st.session_state["consultar"] = True


def pedir(clave: str) -> None:
    st.session_state[clave] = True


def ejemplos_tarapoto() -> list[str]:
    return [q for q in fuentes().get(POLIZA_TARAPOTO, {}).get("ejemplos", []) if "Tarapoto" in q or "al llegar a Lima" in q]


def pantalla_poliza() -> None:
    with st.container(key="tarjeta_consulta"):
        st.markdown("#### Sube el PDF de tu póliza")
        archivos = st.file_uploader("PDF de tu póliza", type=["pdf"], accept_multiple_files=True, key="pdfs",
                                    label_visibility="collapsed")
        st.caption("Si tu póliza viene en varios archivos, súbelos juntos: se leen como un solo documento. "
                   "Necesita texto seleccionable (no escaneado).")
        poliza: dict | None = None
        fuente: str | None = None
        guardadas = {g["poliza_id"]: g for g in (st.session_state.get("cuenta") or {}).get("polizas", [])}
        elegida = None
        if guardadas and not archivos:
            elegida = st.selectbox("O usa una póliza guardada en tu cuenta", [None, *guardadas], key="guardada",
                                   format_func=lambda i: "No usar una guardada" if i is None else
                                   f"{guardadas[i]['nombre']} · {guardadas[i]['paginas']} páginas")
        if elegida:
            g = guardadas[elegida]
            poliza = {"poliza_id": elegida, "huella": elegida, "archivos": g.get("archivos", [])}
            st.caption(f"Guardada en tu cuenta. Se borra sola el {g['borrado_automatico']}: desde ese día tendrás que volver a "
                       "subir el PDF." if g.get("borrado_automatico") else "Guardada en tu cuenta. No se borra sola.")
        elif archivos:
            try:
                n = len(archivos)
                with st.spinner(f"Leyendo tu póliza ({n} archivo{'s' if n > 1 else ''}). Un documento largo "
                                "puede tardar medio minuto…"):
                    poliza = poliza_subida(archivos)
                st.caption(f"Listo: {poliza.get('paginas', '?')} páginas, {poliza['fragmentos']} "
                           "fragmentos. Vive solo en la memoria del servidor mientras la usas. Para probar con un "
                           "ejemplo, quita tus archivos.")
                if poliza.get("aviso_documento"):
                    st.warning(poliza["aviso_documento"], icon="📄")
                guardar_en_cuenta(poliza)
            except ErrorAPI as e:
                st.error(f"No pude leer tu póliza: {e}")
        else:
            # Sin PDF a mano (quien entra solo a probar): los condicionados públicos precargados
            st.caption("¿No tienes una a mano? Prueba con un condicionado de ejemplo:")
            fuente = st.radio("Condicionado de ejemplo", list(fuentes()), key="fuente", horizontal=True,
                              format_func=etiqueta_fuente, label_visibility="collapsed")
            poliza = {"poliza_id": fuente, "huella": fuente, "archivos": []}

        if poliza is not None:
            with st.expander("Radiografía de tu póliza: qué cubre, exclusiones, deducibles y carencias"):
                st.button("Ver la radiografía", key="ver_radiografia", on_click=pedir, args=("pedir_radiografia",))
                if st.session_state.pop("pedir_radiografia", False):
                    try:
                        with st.spinner("Leyendo tu póliza: tarda unos 15 segundos la primera vez…"):
                            st.session_state["radiografia"] = (poliza["huella"], con_poliza(
                                "GET", "/polizas/{poliza_id}/radiografia", poliza, archivos))
                    except ErrorAPI as e:
                        st.error(str(e))
                hecha = st.session_state.get("radiografia")
                if hecha and hecha[0] == poliza["huella"]:
                    mostrar_radiografia(hecha[1])

        st.text_area("Tu pregunta", key="pregunta", height=90,
                     placeholder="Por ejemplo: me robaron la maleta en el aeropuerto, ¿me cubre?")
        st.caption("Puedes hacer hasta 3 preguntas en el mismo texto: cada una cuenta como una consulta.")
        st.button("Preguntar", type="primary", key="preguntar", on_click=pedir_respuesta, disabled=poliza is None)
        # Los ejemplos son de la póliza de Chubb: solo tienen sentido con ella elegida. Con el texto
        # exacto usan la normalización de la caché (una llamada al modelo en vez de dos).
        if fuente == POLIZA_TARAPOTO:
            st.caption("Prueba con un ejemplo:")
            for i, texto in enumerate(ejemplos_tarapoto()):
                st.button(texto, key=f"tarapoto_{i}", on_click=elegir_tarapoto, args=(texto,), type="tertiary")

        if st.session_state.pop("consultar", False):
            pregunta = (st.session_state.get("pregunta") or "").strip()
            if poliza is None:
                st.warning("Primero sube tu PDF o elige un condicionado de ejemplo.")
            elif len(pregunta) < 3:
                st.warning("Escribe una pregunta.")
            else:
                try:
                    with st.spinner("Buscando en tu póliza, redactando y verificando cada cita: suele tardar entre "
                                    "5 y 15 segundos…"):
                        st.session_state["resultado"] = preguntar(poliza, pregunta, archivos)
                    st.session_state["resultado_de"] = poliza["huella"]
                    st.session_state.pop("pasos", None)
                except ErrorAPI as e:
                    st.session_state.pop("resultado", None)
                    (st.warning if e.status == 429 else st.error)(str(e))

        # Respuestas a las repreguntas: se vuelve a preguntar con lo que la persona agregó
        anterior = st.session_state.get("resultado")
        if st.session_state.pop("aclarar", False) and poliza is not None and anterior and anterior["modo"] == "aclaracion":
            aclaraciones = [{"pregunta": q, "respuesta": (st.session_state.get(f"aclara_{i}") or "").strip()}
                            for i, q in enumerate(anterior["repreguntas"])]
            if not any(a["respuesta"] for a in aclaraciones):
                st.warning("Responde al menos una de las preguntas.")
            else:
                try:
                    with st.spinner("Buscando en tu póliza con lo que me contaste…"):
                        st.session_state["resultado"] = preguntar(poliza, anterior["pregunta"], archivos, aclaraciones)
                except ErrorAPI as e:
                    (st.warning if e.status == 429 else st.error)(str(e))

    resultado = st.session_state.get("resultado")
    if resultado is not None and poliza is not None and st.session_state.get("resultado_de") == poliza["huella"]:
        with st.container(key="tarjeta_resultado"):
            de_archivos = [(a["nombre"], a["paginas"]) for a in poliza.get("archivos", [])]
            st.caption(f"Pregunta: {resultado['pregunta']}")
            if resultado["modo"] == "aclaracion":
                st.info(f"**{resultado['aviso']}** Todavía no busqué nada: esto no gasta una consulta.", icon="💬")
                for i, q in enumerate(resultado["repreguntas"]):
                    st.text_input(q, key=f"aclara_{i}")
                st.button("Responder", type="primary", key="responder_aclaracion", on_click=pedir, args=("aclarar",))
            else:
                mostrar(resultado, de_archivos)
                with st.expander("Qué hacer ahora: pasos para reclamar y fecha límite"):
                    sugerida = (resultado.get("fecha_hecho") or {}).get("fecha")
                    fecha = st.date_input("¿Cuándo ocurrió?", value=dt.date.fromisoformat(sugerida) if sugerida else None,
                                          max_value=dt.date.today(), format="DD/MM/YYYY", key="fecha_hecho")
                    st.button("Ver los pasos", key="ver_pasos", on_click=pedir, args=("pedir_pasos",))
                    if st.session_state.pop("pedir_pasos", False):
                        try:
                            with st.spinner("Buscando en tu póliza cómo se reclama: tarda entre 10 y 20 segundos…"):
                                st.session_state["pasos"] = con_poliza("POST", "/pasos", poliza, archivos, {
                                    "situacion": resultado["pregunta"], "fecha_hecho": fecha.isoformat() if fecha else None})
                        except ErrorAPI as e:
                            (st.warning if e.status == 429 else st.error)(str(e))
                    if st.session_state.get("pasos"):
                        mostrar_pasos(st.session_state["pasos"], de_archivos)
            limites = resultado.get("limites") or {}
            if limites:
                st.caption(texto_limites(limites))


# ---------------------------------------------------------------------------
# Dónde atenderte: RENIPRESS (sin modelo, funciona aunque no haya cuota)
# ---------------------------------------------------------------------------


@st.cache_data(ttl=3600, show_spinner=False)
def departamentos() -> dict[str, str]:
    return {d["id"]: d["nombre"] for d in api("GET", "/mapa/departamentos")}


@st.cache_data(ttl=3600, show_spinner=False)
def distritos(departamento: str) -> list[dict]:
    return api("GET", "/mapa/distritos", params={"departamento": departamento})


@st.cache_data(ttl=3600, show_spinner=False)
def establecimientos(departamento: str, provincia: str, distrito: str, solo_internamiento: bool) -> dict:
    return api("GET", "/mapa/establecimientos", params={"departamento": departamento, "provincia": provincia,
                                                        "distrito": distrito, "solo_internamiento": solo_internamiento})


def pantalla_mapa() -> None:
    with st.container(key="tarjeta_mapa"):
        try:
            _mapa()
        except ErrorAPI as e:
            st.error(str(e))


def clinicas_de_la_poliza() -> list[dict]:
    """Las clínicas que la póliza en uso nombra literalmente, con su cita verificada (sin modelo)."""
    subida_ = st.session_state.get("poliza_subida")
    poliza_id = subida_["poliza_id"] if st.session_state.get("pdfs") and subida_ else st.session_state.get("fuente")
    if not poliza_id:
        return []
    try:
        return api("GET", f"/polizas/{poliza_id}/clinicas")["clinicas"]
    except ErrorAPI:
        return []


@st.cache_data(ttl=86400, show_spinner=False)
def con_internamiento() -> list:
    return api("GET", "/mapa/con-internamiento")["establecimientos"]


def mapa_cercano(centro: dict, zona: str, respaldo: list, nombradas: list[dict]) -> None:
    """El mapa corre entero en el navegador (app/mapa_cercano.html): la ubicación no pasa por aquí."""
    # Respaldo si OpenStreetMap no responde: la lista nacional de hospitales y clínicas con
    # internamiento del registro de SUSALUD. La cercanía se calcula en el navegador.
    datos = {"centro": centro, "zona": zona, "nombradas": nombradas, "respaldo": respaldo}
    plantilla = (Path(__file__).parent / "mapa_cercano.html").read_text(encoding="utf-8")
    components.html(plantilla.replace("__DATOS__", json.dumps(datos, ensure_ascii=False).replace("</", "<\\/")),
                    height=760, scrolling=True)


def _mapa() -> None:
    st.markdown("Te muestro clínicas y hospitales cercanos. Puedes usar tu ubicación (no se guarda ni se envía a esta "
                "app) o elegir tu distrito.")
    nombres_dep = departamentos()
    lista = list(nombres_dep)
    c1, c2 = st.columns(2)
    departamento = c1.selectbox("Departamento", lista, index=lista.index("SAN MARTIN") if "SAN MARTIN" in lista else 0,
                                format_func=nombres_dep.get, key="mapa_departamento")
    datos = distritos(departamento)
    opciones = [(d["provincia"], d["distrito"]) for d in datos]
    nombre = {(d["provincia"], d["distrito"]): (d["nombre"], d["nombre_provincia"]) for d in datos}
    solo_distrito = [d for _, d in opciones]
    repetidos = {d for d in solo_distrito if solo_distrito.count(d) > 1}

    def etiqueta(o: tuple[str, str]) -> str:
        propio, provincia = nombre[o]
        return propio + (f" (provincia {provincia})" if o[1] in repetidos else "")

    defecto = opciones.index(("SAN MARTIN", "TARAPOTO")) if ("SAN MARTIN", "TARAPOTO") in opciones else 0
    provincia, distrito = c2.selectbox("Distrito", opciones, index=defecto, format_func=etiqueta, key="mapa_distrito")
    internamiento = st.toggle("Solo hospitales y clínicas con internamiento", key="mapa_internamiento")
    r = establecimientos(departamento, provincia, distrito, internamiento)
    columnas = ["nombre", "clasificacion", "tipo", "categoria", "direccion", "telefono", "horario", "institucion", "lat", "lon"]
    sel = pd.DataFrame(r["establecimientos"], columns=columnas)

    if r.get("centro"):
        mapa_cercano(r["centro"], etiqueta((provincia, distrito)), con_internamiento(), clinicas_de_la_poliza())
    st.warning(r["aviso"], icon="🏥")
    st.markdown("**Registro de SUSALUD en este distrito**")
    st.caption(f"{r['total']} establecimientos activos en {etiqueta((provincia, distrito))}"
               + (f"; {r['sin_coordenadas']} no tienen coordenadas en el registro." if r["sin_coordenadas"] else "."))
    st.dataframe(
        sel[["nombre", "clasificacion", "categoria", "direccion", "telefono", "horario", "institucion"]].rename(columns={
            "nombre": "Nombre", "clasificacion": "Tipo", "categoria": "Categoría", "direccion": "Dirección",
            "telefono": "Teléfono", "horario": "Horario", "institucion": "Institución"}),
        hide_index=True, width="stretch",
    )
    f = r["fuente"]
    st.caption(f"Fuente: RENIPRESS, SUSALUD, en datosabiertos.gob.pe (corte del {f['corte']}, licencia ODC-BY). "
               "Solo establecimientos en estado activo.")


# ---------------------------------------------------------------------------
# Pantalla
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="qmc-banda"><p class="qmc-titulo" role="heading" aria-level="1">¿Qué me cubre?</p>'
    '<p class="qmc-bajada">Pregunta en español normal y te respondo citando la cláusula exacta de tu póliza, '
    "con artículo y página.</p></div>",
    unsafe_allow_html=True,
)
st.markdown(
    '<ol class="qmc-pasos">'
    "<li><span>1</span>Sube el PDF de tu póliza o usa un ejemplo.</li>"
    "<li><span>2</span>Pregunta en español normal.</li>"
    "<li><span>3</span>Te respondo con la cláusula exacta y su página.</li>"
    "</ol>",
    unsafe_allow_html=True,
)


def aviso_privacidad() -> str:
    i = info()
    partes = ["**Tu PDF se procesa en memoria y no se guarda** (ni en disco ni en registros)."
              + (" Si guardas la póliza en tu cuenta, se guarda su texto cifrado, no el archivo." if st.session_state.get("token") else ""),
              i["aviso_proveedor"]]
    if i.get("embeddings"):
        partes.append("Para buscar en ella, el texto de la póliza se envía también a Voyage AI, que calcula sus vectores.")
    if i.get("registra_preguntas"):
        partes.append("El texto de tu pregunta, sin la póliza ni la respuesta, se registra para medir el servicio.")
    if i.get("sin_modelo_por_tope"):
        partes.append("**Este mes el servicio llegó a su tope de gasto:** verás las cláusulas de tu póliza, sin veredicto.")
    return " ".join(partes) + "\n\n**Es informativo:** la decisión final sobre la cobertura la toma tu aseguradora."


try:
    st.info(aviso_privacidad(), icon="🔒")
    if st.session_state.get("token") and "cuenta" not in st.session_state:
        refrescar_cuenta()
    tab_poliza, tab_mapa, tab_cuenta = st.tabs(["Pregunta a tu póliza", "Dónde atenderte", "Mi cuenta"])
    with tab_poliza:
        pantalla_poliza()
    with tab_mapa:
        pantalla_mapa()
    with tab_cuenta:
        pantalla_cuenta()
except ErrorAPI as e:
    st.error(str(e))
    st.button("Volver a intentar", on_click=st.cache_data.clear)

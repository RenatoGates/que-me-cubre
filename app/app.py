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

import hashlib
import html
import os
import re
import uuid

import httpx
import pandas as pd
import streamlit as st

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
        r = httpx.request(metodo, api_url() + ruta, headers={"X-Dispositivo": dispositivo()}, timeout=150.0, **kwargs)
    except httpx.HTTPError as e:
        raise ErrorAPI("No pude conectarme con el servidor. Si estaba dormido tarda cerca de un minuto en "
                       "despertar: vuelve a intentar.") from e
    if r.status_code >= 400:
        try:
            detalle = r.json().get("detail")
        except ValueError:
            detalle = None
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


def preguntar(poliza: dict, pregunta: str, archivos) -> dict:
    try:
        return api("POST", "/preguntar", json={"poliza_id": poliza["poliza_id"], "pregunta": pregunta})
    except ErrorAPI as e:
        if e.codigo != "poliza_no_encontrada" or not archivos:
            raise
    # La póliza venció en la memoria del servidor (o este se reinició): se sube de nuevo
    st.session_state.pop("poliza_subida", None)
    return api("POST", "/preguntar", json={"poliza_id": poliza_subida(archivos)["poliza_id"], "pregunta": pregunta})


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
                    else f"Verificada: el texto está literal en la {donde} del PDF (leído con {lectores}).")
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


def mostrar(r: dict, archivos: Archivos | None = None) -> None:
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


def elegir_tarapoto(pregunta: str) -> None:
    """Ejemplo (solo visible con la póliza de Chubb): pone el texto exacto y pide responder."""
    st.session_state["fuente"] = POLIZA_TARAPOTO
    st.session_state["pregunta"] = pregunta
    st.session_state["consultar"] = True


def pedir_respuesta() -> None:
    st.session_state["consultar"] = True


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
        if archivos:
            try:
                n = len(archivos)
                with st.spinner(f"Leyendo tu póliza ({n} archivo{'s' if n > 1 else ''}). Un documento largo "
                                "puede tardar medio minuto…"):
                    poliza = poliza_subida(archivos)
                st.caption(f"Listo: {poliza.get('paginas', '?')} páginas, {poliza['fragmentos']} "
                           "fragmentos. Vive solo en la memoria del servidor mientras la usas. Para probar con un "
                           "ejemplo, quita tus archivos.")
            except ErrorAPI as e:
                st.error(f"No pude leer tu póliza: {e}")
        else:
            # Sin PDF a mano (quien entra solo a probar): los condicionados públicos precargados
            st.caption("¿No tienes una a mano? Prueba con un condicionado de ejemplo:")
            fuente = st.radio("Condicionado de ejemplo", list(fuentes()), key="fuente", horizontal=True,
                              format_func=etiqueta_fuente, label_visibility="collapsed")
            poliza = {"poliza_id": fuente, "huella": fuente, "archivos": []}

        st.text_area("Tu pregunta", key="pregunta", height=90,
                     placeholder="Por ejemplo: me robaron la maleta en el aeropuerto, ¿me cubre?")
        st.caption("Una pregunta a la vez.")
        st.button("Preguntar", type="primary", on_click=pedir_respuesta, disabled=poliza is None)
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
                except ErrorAPI as e:
                    st.session_state.pop("resultado", None)
                    (st.warning if e.status == 429 else st.error)(str(e))

    resultado = st.session_state.get("resultado")
    if resultado is not None and poliza is not None and st.session_state.get("resultado_de") == poliza["huella"]:
        with st.container(key="tarjeta_resultado"):
            st.caption(f"Pregunta: {resultado['pregunta']}")
            mostrar(resultado, [(a["nombre"], a["paginas"]) for a in poliza.get("archivos", [])])
            limites = resultado.get("limites") or {}
            if limites:
                st.caption(f"Te quedan {limites['restantes_hoy']} de {limites['limite_dia']} consultas por hoy.")


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


def _mapa() -> None:
    st.markdown("Elige la zona y te muestro los establecimientos de salud registrados en SUSALUD. "
                "No uso tu ubicación.")
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
    columnas = ["nombre", "clasificacion", "categoria", "direccion", "telefono", "horario", "institucion", "lat", "lon"]
    sel = pd.DataFrame(r["establecimientos"], columns=columnas)

    en_mapa = sel.dropna(subset=["lat", "lon"])
    if len(en_mapa):
        st.map(en_mapa, latitude="lat", longitude="lon", size=25, color="#4338CA")
    st.warning(r["aviso"], icon="🏥")
    st.caption(f"{r['total']} establecimientos activos en {etiqueta((provincia, distrito))}"
               + (f"; {r['sin_coordenadas']} no tienen coordenadas en el registro: salen en la lista, no en el mapa."
                  if r["sin_coordenadas"] else "."))
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
    partes = ["**Tu PDF se procesa en memoria y no se guarda** (ni en disco ni en registros).", i["aviso_proveedor"]]
    if i.get("embeddings"):
        partes.append("Para buscar en ella, el texto de la póliza se envía también a Voyage AI, que calcula sus vectores.")
    if i.get("registra_preguntas"):
        partes.append("El texto de tu pregunta, sin la póliza ni la respuesta, se registra para medir el servicio.")
    if i.get("sin_modelo_por_tope"):
        partes.append("**Este mes el servicio llegó a su tope de gasto:** verás las cláusulas de tu póliza, sin veredicto.")
    return " ".join(partes) + "\n\n**Es informativo:** la decisión final sobre la cobertura la toma tu aseguradora."


try:
    st.info(aviso_privacidad(), icon="🔒")
    tab_poliza, tab_mapa = st.tabs(["Pregunta a tu póliza", "Dónde atenderte"])
    with tab_poliza:
        pantalla_poliza()
    with tab_mapa:
        pantalla_mapa()
except ErrorAPI as e:
    st.error(str(e))
    st.button("Volver a intentar", on_click=st.cache_data.clear)

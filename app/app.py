"""¿Qué me cubre? Interfaz de Streamlit: una sola pantalla.

Subir el PDF de la póliza (uno o varios archivos, leídos como un solo documento: ai/subida.py)
o probar con un condicionado de ejemplo, preguntar en lenguaje común y ver la respuesta con el
contrato del README ("Cómo se muestra una respuesta"):

1. el veredicto arriba, como etiqueta, sacado del campo estructurado (`etiqueta_veredicto`);
2. el texto del modelo debajo, como explicación, con sus condiciones y exclusiones;
3. lo que la póliza menciona pero no trae: cláusulas con nombre propio (B4) resaltadas y
   remisiones genéricas (Condiciones Particulares, Certificado) plegadas;
4. las citas, cada una desplegable, con su texto literal, cláusula, artículo y página;
5. "exclusiones que podrían aplicar según tu caso", aparte y como posibilidad.

Si el proveedor falla o se acaba la cuota: las cláusulas encontradas, resaltadas, con el
aviso de por qué no hay texto generado (red de seguridad de ai/respuesta.py).

Pestaña "Dónde atenderte": la persona elige departamento y distrito y ve los
establecimientos activos de RENIPRESS (SUSALUD) en un mapa y una lista. No usa el modelo ni
la ubicación de la persona; son establecimientos registrados, no la red de su aseguradora.

Privacidad: el PDF subido vive solo en la memoria de esta sesión (st.session_state); no se
escribe en disco ni en la caché compartida entre sesiones. Nada de lo que se pregunta se
registra.

    streamlit run app/app.py
"""

from __future__ import annotations

import html
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st  # noqa: E402

from ai import renipress, subida  # noqa: E402
from ai.indice import Indice  # noqa: E402
from ai.llm import ErrorLLM, ProveedorNoDisponible, obtener_proveedor  # noqa: E402
from ai.respuesta import ETIQUETA_VEREDICTO, Poliza, responder  # noqa: E402

POLIZAS = RAIZ / "data" / "polizas"
INDICES = RAIZ / "data" / "indices"
POLIZA_TARAPOTO = "chubb_viajes_jetsmart"
# Las preguntas de los casos reales, con el texto exacto con el que están en la caché
PREGUNTAS_TARAPOTO = [
    q["pregunta"]
    for q in json.loads((RAIZ / "data" / "demo" / "preguntas_ensayo.json").read_text(encoding="utf-8"))
    if q["documento"] == POLIZA_TARAPOTO and ("Tarapoto" in q["pregunta"] or "al llegar a Lima" in q["pregunta"])
]
COLORES = {  # fondo, texto, borde
    "si": ("#e3f4e8", "#14532d", "#4f9a69"),
    "con_limites": ("#fff3d1", "#6b4500", "#a67c00"),
    "no": ("#fde4e2", "#8a1c13", "#d0645a"),
    "no_encontrado": ("#eceff3", "#2f3640", "#7d8796"),
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
# Datos
# ---------------------------------------------------------------------------


@st.cache_resource(show_spinner=False)
def fuentes() -> dict[str, dict]:
    return {f["id"]: f for f in json.loads((POLIZAS / "fuentes.json").read_text(encoding="utf-8"))}


def etiqueta_fuente(doc_id: str) -> str:
    f = fuentes()[doc_id]
    return f"{f['aseguradora']} · {f['producto']}"


@st.cache_resource(show_spinner="Cargando la póliza…")
def poliza_precargada(doc_id: str) -> Poliza:
    """Condicionados públicos: índice ya construido en data/indices/ (python -m ai.ingesta)."""
    indice = Indice.cargar(INDICES, doc_id)
    pdf = (POLIZAS / fuentes()[doc_id]["archivo"]).read_bytes()
    return Poliza(doc_id, indice.meta["documento"], indice, pdf)


def poliza_subida(archivos) -> Poliza:
    """Los PDF del usuario, uno o varios, como un solo documento (ai/subida.py): se procesan en
    memoria y viven solo en esta sesión. No se escriben en disco ni en st.cache (compartida)."""
    pares = [(a.name, a.getvalue()) for a in archivos]
    clave = subida.huella([datos for _, datos in pares])
    guardada = st.session_state.get("poliza_subida")
    if guardada is not None and guardada.sha256 == clave:
        return guardada
    poliza = subida.poliza_de_pdfs(pares)
    st.session_state["poliza_subida"] = poliza
    return poliza


class SinProveedor:
    """Sin clave o con un proveedor mal configurado: todo va a la red de seguridad."""

    nombre = "ninguno"
    modelos = {"normalizacion": "—", "respuesta": "—"}
    reutiliza_datos = False

    def __init__(self, motivo: str) -> None:
        self.aviso = motivo

    def json(self, *args, **kwargs):
        raise ProveedorNoDisponible(self.aviso)


@st.cache_resource(show_spinner=False)
def proveedor():
    try:
        return obtener_proveedor()
    except ErrorLLM as e:
        return SinProveedor(str(e))


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
        return subida.paginas_con_archivo(archivos, ps)
    return f"pág. {ps[0]}" if len(ps) == 1 else f"págs. {ps[0]}–{ps[-1]}"


def refs(numeros: list[int]) -> str:
    return f" (cita {numeros[0]})" if len(numeros) == 1 else f" (citas {', '.join(map(str, numeros))})"


def veredicto(r: dict) -> None:
    cubre = r.get("cubre")
    texto = r.get("etiqueta_veredicto") or ETIQUETA_VEREDICTO.get(cubre, "Sin veredicto")
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
    info = r.get("proveedor") or {}
    st.caption(f"Modelo: {info.get('modelo', '—')} en {info.get('nombre', '—')} · costo de esta consulta: USD 0 "
               "(plan gratuito)")


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


def pantalla_poliza() -> None:
    with st.container(key="tarjeta_consulta"):
        st.markdown("#### Sube el PDF de tu póliza")
        archivos = st.file_uploader("PDF de tu póliza", type=["pdf"], accept_multiple_files=True, key="pdfs",
                                    label_visibility="collapsed")
        st.caption("Si tu póliza viene en varios archivos, súbelos juntos: se leen como un solo documento. "
                   "Necesita texto seleccionable (no escaneado).")
        poliza: Poliza | None = None
        fuente: str | None = None
        if archivos:
            try:
                n = len(archivos)
                with st.spinner(f"Leyendo tu póliza ({n} archivo{'s' if n > 1 else ''}). Un documento largo "
                                "puede tardar medio minuto…"):
                    poliza = poliza_subida(archivos)
                st.caption(f"Listo: {poliza.indice.meta.get('paginas', '?')} páginas, {len(poliza.indice.trozos)} "
                           "fragmentos. Vive solo en esta sesión. Para probar con un ejemplo, quita tus archivos.")
            except Exception as e:  # noqa: BLE001 - PDF dañado, protegido o escaneado
                st.error(f"No pude leer tu póliza: {e}")
        else:
            # Sin PDF a mano (quien entra solo a probar): los condicionados públicos precargados
            st.caption("¿No tienes una a mano? Prueba con un condicionado de ejemplo:")
            fuente = st.radio("Condicionado de ejemplo", list(fuentes()), key="fuente", horizontal=True,
                              format_func=etiqueta_fuente, label_visibility="collapsed")
            poliza = poliza_precargada(fuente)

        st.text_area("Tu pregunta", key="pregunta", height=90,
                     placeholder="Por ejemplo: me robaron la maleta en el aeropuerto, ¿me cubre?")
        st.caption("Una pregunta a la vez.")
        st.button("Preguntar", type="primary", on_click=pedir_respuesta, disabled=poliza is None)
        # Los ejemplos son de la póliza de Chubb: solo tienen sentido con ella elegida. Con el texto
        # exacto usan la normalización de la caché (una llamada al modelo en vez de dos).
        if fuente == POLIZA_TARAPOTO:
            st.caption("Prueba con un ejemplo:")
            for i, texto in enumerate(PREGUNTAS_TARAPOTO):
                st.button(texto, key=f"tarapoto_{i}", on_click=elegir_tarapoto, args=(texto,), type="tertiary")

        if st.session_state.pop("consultar", False):
            pregunta = (st.session_state.get("pregunta") or "").strip()
            if poliza is None:
                st.warning("Primero sube tu PDF o elige un condicionado de ejemplo.")
            elif not pregunta:
                st.warning("Escribe una pregunta.")
            else:
                # Avance visible mientras busca, redacta y verifica: que no parezca colgada
                marcador = st.empty()
                with marcador.status("Buscando en tu póliza…", expanded=False) as estado:
                    st.session_state["resultado"] = responder(pregunta, poliza, proveedor(),
                                                              avance=lambda texto: estado.update(label=texto))
                marcador.empty()
                st.session_state["resultado_de"] = (poliza.doc_id, poliza.sha256, pregunta)

    resultado = st.session_state.get("resultado")
    de = st.session_state.get("resultado_de", (None, None))
    if resultado is not None and poliza is not None and de[:2] == (poliza.doc_id, poliza.sha256):
        with st.container(key="tarjeta_resultado"):
            st.caption(f"Pregunta: {resultado['pregunta']}")
            mostrar(resultado, poliza.archivos)


# ---------------------------------------------------------------------------
# Dónde atenderte: RENIPRESS (sin modelo, funciona aunque no haya cuota)
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def establecimientos_registrados():
    return renipress.cargar()


def pantalla_mapa() -> None:
    with st.container(key="tarjeta_mapa"):
        _mapa()


def _mapa() -> None:
    df = establecimientos_registrados()
    st.markdown("Elige la zona y te muestro los establecimientos de salud registrados en SUSALUD. "
                "No uso tu ubicación.")
    departamentos = sorted(df["departamento"].unique())
    c1, c2 = st.columns(2)
    departamento = c1.selectbox("Departamento", departamentos, index=departamentos.index("SAN MARTIN"),
                                format_func=renipress.nombre_propio, key="mapa_departamento")
    opciones = renipress.distritos(df, departamento)
    nombres = [d for _, d in opciones]
    repetidos = {d for d in nombres if nombres.count(d) > 1}

    def etiqueta(o: tuple[str, str]) -> str:
        provincia, distrito = o
        extra = f" (provincia {renipress.nombre_propio(provincia)})" if distrito in repetidos else ""
        return renipress.nombre_propio(distrito) + extra

    defecto = opciones.index(("SAN MARTIN", "TARAPOTO")) if ("SAN MARTIN", "TARAPOTO") in opciones else 0
    provincia, distrito = c2.selectbox("Distrito", opciones, index=defecto, format_func=etiqueta, key="mapa_distrito")
    sel = renipress.establecimientos(df, departamento, provincia, distrito)
    if st.toggle("Solo hospitales y clínicas con internamiento", key="mapa_internamiento"):
        sel = sel[sel["tipo"].str.contains("CON INTERNAMIENTO")]

    en_mapa = sel.dropna(subset=["lat", "lon"])
    if len(en_mapa):
        st.map(en_mapa, latitude="lat", longitude="lon", size=25, color="#4338CA")
    st.warning("Son establecimientos registrados en SUSALUD, no la red de tu aseguradora.", icon="🏥")
    st.caption(f"{len(sel)} establecimientos activos en {etiqueta((provincia, distrito))}"
               + (f"; {len(sel) - len(en_mapa)} no tienen coordenadas en el registro: salen en la lista, no en el mapa."
                  if len(sel) > len(en_mapa) else "."))
    st.dataframe(
        sel[["nombre", "clasificacion", "categoria", "direccion", "telefono", "horario", "institucion"]].rename(columns={
            "nombre": "Nombre", "clasificacion": "Tipo", "categoria": "Categoría", "direccion": "Dirección",
            "telefono": "Teléfono", "horario": "Horario", "institucion": "Institución"}),
        hide_index=True, width="stretch",
    )
    f = renipress.fuente()
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
st.info(
    "**Tu PDF se procesa en memoria y no se guarda** (ni en disco ni en registros). "
    f"{proveedor().aviso}\n\n"
    "**Es informativo:** la decisión final sobre la cobertura la toma tu aseguradora.",
    icon="🔒",
)
tab_poliza, tab_mapa = st.tabs(["Pregunta a tu póliza", "Dónde atenderte"])
with tab_poliza:
    pantalla_poliza()
with tab_mapa:
    pantalla_mapa()

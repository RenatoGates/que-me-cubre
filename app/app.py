"""¿Qué me cubre? Interfaz de Streamlit: una sola pantalla.

Elegir la póliza (precargada o un PDF propio), preguntar en lenguaje común y ver la
respuesta con el contrato del README ("Cómo se muestra una respuesta"):

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

import hashlib
import html
import json
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
    sys.path.insert(0, str(RAIZ))

import streamlit as st  # noqa: E402

from ai import renipress  # noqa: E402
from ai.extraccion import extraer  # noqa: E402
from ai.indice import Indice  # noqa: E402
from ai.llm import ErrorLLM, ProveedorNoDisponible, obtener_proveedor  # noqa: E402
from ai.respuesta import ETIQUETA_VEREDICTO, Poliza, responder  # noqa: E402
from ai.troceado import trocear  # noqa: E402

POLIZAS = RAIZ / "data" / "polizas"
INDICES = RAIZ / "data" / "indices"
SUBIR = "Subir el PDF de mi póliza"
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
    .qmc-cita {border-left: 4px solid #4F46E5; padding: .35rem 0 .35rem .9rem; margin: .3rem 0 .6rem 0;
               font-size: 1rem; line-height: 1.55;}
    /* Streamlit dibuja st.caption al 60 % de opacidad: sobre el fondo azul claro del tema queda en
       4,2:1, bajo el 4,5:1 de WCAG AA. Ahí van la página y la verificación de cada cita. */
    [data-testid="stCaptionContainer"] {opacity: .75;}
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


def poliza_subida(archivo) -> Poliza:
    """El PDF del usuario: se procesa en memoria con las mismas funciones que la ingesta y
    vive solo en esta sesión. No se escribe en disco ni en st.cache (compartida)."""
    datos = archivo.getvalue()
    sha = hashlib.sha256(datos).hexdigest()
    guardada = st.session_state.get("poliza_subida")
    if guardada is not None and guardada.sha256 == sha:
        return guardada
    doc = extraer(datos)
    if doc.es_escaneado:
        raise ValueError("El PDF no tiene texto seleccionable en la mayoría de páginas (parece escaneado). "
                         "Necesitaría OCR, que esta versión no hace.")
    nombre = "Tu póliza"
    trozos = trocear(doc.bloques, "subida", nombre)
    if not trozos:
        raise ValueError("No encontré texto en el PDF.")
    indice = Indice.construir(trozos, {"doc_id": "subida", "documento": nombre, "paginas": doc.paginas_total},
                              con_embeddings=False)
    poliza = Poliza("subida", nombre, indice, datos, sha)
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


def paginas(c: dict) -> str:
    ps = c.get("paginas") or [c.get("pagina")]
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


def mencionadas_ausentes(r: dict) -> None:
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
            f"Se menciona en {md(m['seccion'])} › {md(m['articulo'])}, {paginas(m)}: «{md(m['mencion'])}»",
            icon="📄",
        )
    for m in del_modelo:
        st.warning(f"**{md(m['nombre'])}** no está en este documento. {md(m['por_que_importa'])}{refs([m['cita']])}",
                   icon="📄")
    if remisiones:
        with st.expander(f"Remisiones a otros documentos ({len(remisiones)}): ahí suelen estar los montos"):
            for m in remisiones:
                st.markdown(f"- {md(m['mensaje'])} Se menciona en {md(m['seccion'])} › {md(m['articulo'])}, {paginas(m)}.")


def citas(r: dict) -> None:
    if not r["citas"]:
        return
    st.markdown("#### Citas de tu póliza")
    for c in r["citas"]:
        with st.expander(f"Cita {c['n']} · {c['articulo']} · {paginas(c)}"):
            st.caption(f"{c['seccion']} › {c['articulo']} · {paginas(c)}")
            literal = html.escape(c["texto_literal"]).replace("\n", "<br>")
            st.markdown(f'<div class="qmc-cita">{literal}</div>', unsafe_allow_html=True)
            v = c["verificacion"]
            lectores = " y ".join(n for n in ("pdfplumber", "pypdf") if v.get(n))
            nota = f"Verificada: el texto está literal en la {paginas(c)} del PDF (leído con {lectores})."
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


def pasajes(r: dict, abiertos: bool) -> None:
    for p in r["pasajes"]:
        etiqueta = f"{p['seccion']} › {p['articulo']} · {paginas(p)}"
        with st.expander(etiqueta, expanded=abiertos):
            st.markdown(pasaje_resaltado(p), unsafe_allow_html=True)


def mostrar(r: dict) -> None:
    veredicto(r)
    if r["modo"] != "completo":  # red de seguridad: sin texto generado
        st.warning(r["aviso"], icon="⚠️")
        mencionadas_ausentes(r)
        st.markdown("#### Cláusulas que encontré para tu pregunta")
        st.caption("Resaltadas, las palabras de la búsqueda. Aquí no hay un veredicto: léelas tú.")
        pasajes(r, abiertos=False)
        return
    explicacion(r)
    mencionadas_ausentes(r)
    citas(r)
    podrian_aplicar(r)
    with st.expander(f"Pasajes que revisé ({len(r['pasajes'])})"):
        st.caption("Lo que se le envió al modelo, en el orden de la búsqueda.")
        pasajes(r, abiertos=False)
    info = r.get("proveedor") or {}
    st.caption(f"Modelo: {info.get('modelo', '—')} en {info.get('nombre', '—')} · costo de esta consulta: USD 0 "
               "(plan gratuito)")


# ---------------------------------------------------------------------------
# Tu póliza
# ---------------------------------------------------------------------------


def elegir_tarapoto(pregunta: str) -> None:
    """Botón de caso real: pone la póliza de Chubb y el texto exacto, y pide responder."""
    st.session_state["fuente"] = POLIZA_TARAPOTO
    st.session_state["pregunta"] = pregunta
    st.session_state["consultar"] = True


def pedir_respuesta() -> None:
    st.session_state["consultar"] = True


def pantalla_poliza() -> None:
    opciones = [*fuentes(), SUBIR]
    fuente = st.radio(
        "Póliza", opciones, key="fuente", horizontal=True,
        format_func=lambda x: x if x == SUBIR else etiqueta_fuente(x),
    )
    poliza: Poliza | None = None
    if fuente == SUBIR:
        archivo = st.file_uploader("PDF de tu póliza (condicionado con texto seleccionable)", type=["pdf"])
        if archivo is not None:
            try:
                with st.spinner("Leyendo tu póliza…"):
                    poliza = poliza_subida(archivo)
                st.caption(f"Listo: {poliza.indice.meta.get('paginas', '?')} páginas, {len(poliza.indice.trozos)} "
                           "fragmentos. Vive solo en esta sesión.")
            except Exception as e:  # noqa: BLE001 - PDF dañado, protegido o escaneado
                st.error(f"No pude leer ese PDF: {e}")
    else:
        poliza = poliza_precargada(fuente)

    st.text_area("Tu pregunta", key="pregunta", height=90,
                 placeholder="Por ejemplo: me robaron la maleta en el aeropuerto, ¿me cubre?")
    st.button("Preguntar", type="primary", on_click=pedir_respuesta, disabled=poliza is None)
    st.caption("Casos reales, sobre la póliza de Chubb · JetSmart:")
    for i, texto in enumerate(PREGUNTAS_TARAPOTO):
        st.button(texto, key=f"tarapoto_{i}", on_click=elegir_tarapoto, args=(texto,), width="stretch")

    if st.session_state.pop("consultar", False):
        pregunta = (st.session_state.get("pregunta") or "").strip()
        if poliza is None:
            st.warning("Primero elige una póliza o sube tu PDF.")
        elif not pregunta:
            st.warning("Escribe una pregunta.")
        else:
            with st.spinner("Buscando en tu póliza y verificando las citas…"):
                st.session_state["resultado"] = responder(pregunta, poliza, proveedor())
            st.session_state["resultado_de"] = (poliza.doc_id, poliza.sha256, pregunta)

    resultado = st.session_state.get("resultado")
    de = st.session_state.get("resultado_de", (None, None))
    if resultado is not None and poliza is not None and de[:2] == (poliza.doc_id, poliza.sha256):
        st.divider()
        st.caption(f"Pregunta: {resultado['pregunta']}")
        mostrar(resultado)


# ---------------------------------------------------------------------------
# Dónde atenderte: RENIPRESS (sin modelo, funciona aunque no haya cuota)
# ---------------------------------------------------------------------------


@st.cache_data(show_spinner=False)
def establecimientos_registrados():
    return renipress.cargar()


def pantalla_mapa() -> None:
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
        st.map(en_mapa, latitude="lat", longitude="lon", size=25, color="#4F46E5")
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

st.title("¿Qué me cubre?")
st.markdown("Pregunta en español normal y te respondo citando la cláusula exacta de tu póliza, con artículo y página.")
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

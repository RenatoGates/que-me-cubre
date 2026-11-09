"""Document AI (sesión 10): del PDF de la póliza a bloques con sección, artículo y página.

Todo trabaja sobre los bytes del PDF en memoria (io.BytesIO): nada se escribe a disco.

Pasos:
1. Texto por página con pdfplumber. Si la página está a dos columnas (hay un canal
   vertical vacío cerca del centro), se lee primero la izquierda y luego la derecha.
2. Se quitan membretes y pies de página: líneas que se repiten arriba o abajo en
   muchas páginas (por ejemplo, la dirección de la aseguradora o el código SBS).
3. Se reconoce la estructura típica de un condicionado peruano:
   - sección: "Resumen Informativo", "Condiciones Generales", cada "Cláusula Adicional",
     "Cláusulas Generales de Contratación", "PARTE B. COBERTURAS", etc.;
   - dentro de la sección, el artículo ("Artículo 3° Cobertura", "ARTÍCULO 9°.- ...")
     o, si la sección no tiene artículos, el numeral ("2.1.3. VALIDEZ TERRITORIAL").
   Cada línea conserva su número de página.

Los números de artículo se repiten entre secciones (cada Cláusula Adicional vuelve a
empezar en "Artículo 1°"), así que una cita siempre lleva sección + artículo + página.
"""

from __future__ import annotations

import io
import math
import re
from collections import Counter
from dataclasses import dataclass, field

import pdfplumber

# ---------------------------------------------------------------------------
# Estructuras
# ---------------------------------------------------------------------------


@dataclass
class Linea:
    texto: str
    pagina: int
    indice: bool = False  # línea de un índice/tabla de contenido: no es estructura ni contenido


@dataclass
class Bloque:
    """Unidad mínima citable: un artículo (o numeral) completo de una sección."""

    seccion: str
    ruta: list[str]  # encabezados dentro de la sección, del más general al más específico
    lineas: list[Linea] = field(default_factory=list)
    n_encabezado: int = 0  # cuántas de las primeras líneas son el encabezado
    sin_articulos: bool = False  # la sección entera no tiene artículos ni numerales

    @property
    def articulo(self) -> str:
        if self.ruta:
            return " › ".join(self.ruta)
        return "Texto completo de la sección" if self.sin_articulos else "Texto inicial de la sección"

    @property
    def paginas(self) -> list[int]:
        return sorted({ln.pagina for ln in self.lineas if not ln.indice})


@dataclass
class DocumentoExtraido:
    paginas_total: int
    paginas_sin_texto: list[int]
    paginas_dos_columnas: list[int]
    lineas_quitadas: list[str]  # membretes y pies detectados (sin repetir)
    bloques: list[Bloque]
    paginas_por_archivo: list[int] = field(default_factory=list)  # varios PDF: páginas de cada uno, en orden

    @property
    def es_escaneado(self) -> bool:
        """Más de la mitad de las páginas sin capa de texto: haría falta OCR."""
        return self.paginas_total > 0 and len(self.paginas_sin_texto) > self.paginas_total / 2

    def archivos_escaneados(self) -> list[int]:
        """Índices (desde 0) de los archivos con más de la mitad de sus páginas sin texto."""
        malos, desde = [], 0
        for i, n in enumerate(self.paginas_por_archivo or [self.paginas_total]):
            vacias = sum(desde < p <= desde + n for p in self.paginas_sin_texto)
            if n > 0 and vacias > n / 2:
                malos.append(i)
            desde += n
        return malos


# ---------------------------------------------------------------------------
# 1. Texto por página, con detección de dos columnas
# ---------------------------------------------------------------------------

# Viñetas de fuentes Symbol/Wingdings que llegan como caracteres de uso privado
_PUA = re.compile(r"[-]")


def _limpiar_caracteres(texto: str) -> str:
    texto = _PUA.sub("•", texto)
    return texto.replace(" ", " ").replace("­", "")


def _canal_central(page) -> float | None:
    """Devuelve la x del canal entre dos columnas, o None si la página es de una columna.

    Busca, entre el 35 % y el 65 % del ancho, la franja vertical más ancha que ninguna
    palabra cruza. Exige que haya texto suficiente a ambos lados.
    """
    palabras = page.extract_words(keep_blank_chars=False, use_text_flow=False)
    if len(palabras) < 60:
        return None
    ancho = page.width
    x_ini, x_fin = int(ancho * 0.35), int(ancho * 0.65)
    cubierto = [0] * (x_fin - x_ini)
    for w in palabras:
        a, b = max(int(w["x0"]), x_ini), min(int(math.ceil(w["x1"])), x_fin)
        for x in range(a, b):
            cubierto[x - x_ini] += 1
    # franja vacía más ancha
    mejor, inicio = (0, None), None
    for i, c in enumerate(cubierto + [1]):
        if c == 0 and inicio is None:
            inicio = i
        elif c != 0 and inicio is not None:
            if i - inicio > mejor[0]:
                mejor = (i - inicio, inicio)
            inicio = None
    largo, ini = mejor
    if ini is None or largo < 8:
        return None
    x = x_ini + ini + largo / 2
    izq = sum(1 for w in palabras if w["x1"] <= x)
    der = sum(1 for w in palabras if w["x0"] >= x)
    if min(izq, der) < 0.2 * len(palabras):
        return None
    return x


def _texto_pagina(page) -> tuple[list[str], bool]:
    x = _canal_central(page)
    if x is None:
        texto = page.extract_text() or ""
        return _limpiar_caracteres(texto).splitlines(), False
    izq = page.crop((0, 0, x, page.height)).extract_text() or ""
    der = page.crop((x, 0, page.width, page.height)).extract_text() or ""
    return _limpiar_caracteres(izq + "\n" + der).splitlines(), True


# ---------------------------------------------------------------------------
# 2. Membretes y pies de página
# ---------------------------------------------------------------------------

_ZONA_ARRIBA, _ZONA_ABAJO = 6, 3
_RE_NUM_PAGINA = re.compile(r"^(p[aá]g(ina)?\.?\s*)?\d{1,3}(\s*(de|/)\s*\d{1,3})?$", re.I)


def _clave(linea: str) -> str:
    return re.sub(r"\d+", "#", linea.strip().lower())


def _quitar_membretes(paginas: list[list[str]]) -> tuple[list[list[str]], list[str]]:
    con_texto = [p for p in paginas if p]
    if len(con_texto) < 3:
        return paginas, []
    conteo: Counter[str] = Counter()
    for lineas in con_texto:
        zona = {_clave(ln) for ln in lineas[:_ZONA_ARRIBA] + lineas[-_ZONA_ABAJO:] if ln.strip()}
        conteo.update(zona)
    umbral = max(3, math.ceil(0.4 * len(con_texto)))
    repetidas = {k for k, n in conteo.items() if n >= umbral}

    quitadas: list[str] = []
    limpias = []
    for lineas in paginas:
        n = len(lineas)
        nuevas = []
        for i, ln in enumerate(lineas):
            en_zona = i < _ZONA_ARRIBA or i >= n - _ZONA_ABAJO
            s = ln.strip()
            if not s:
                continue
            if en_zona and (_clave(s) in repetidas or _RE_NUM_PAGINA.match(s)):
                if s not in quitadas:
                    quitadas.append(s)
                continue
            nuevas.append(s)
        limpias.append(nuevas)
    return limpias, quitadas



# ---------------------------------------------------------------------------
# 3. Estructura: secciones y artículos
# ---------------------------------------------------------------------------

_RE_SECCION_NOMBRADA = re.compile(
    r"^(Resumen Informativo|Resumen de la P[oó]liza|Condiciones Generales( del Seguro)?|"
    r"Condicionado General( de la P[oó]liza)?|Condiciones Particulares|Condiciones Especiales|"
    r"Cl[aá]usulas Generales de Contrataci[oó]n.*|Anexo\b.*)$",
    re.I,
)
_RE_CLAUSULA_SOLA = re.compile(r"^Cl[aá]usula Adicional$", re.I)
_RE_CLAUSULA_TITULO = re.compile(r"^Cl[aá]usula Adicional (de|del|por|para|sobre)\s+\S.*$", re.I)
_RE_PARTE = re.compile(
    r"^(PARTE|CAP[IÍ]TULO|T[IÍ]TULO|SECCI[OÓ]N)\s+([A-Z]|[IVXLC]+|\d{1,2})\b[\s.:\-–]*(.*)$"
)
_ORDINALES = (
    "PRIMERO|SEGUNDO|TERCERO|CUARTO|QUINTO|SEXTO|S[EÉ]PTIMO|OCTAVO|NOVENO|D[EÉ]CIMO|"
    "Primero|Segundo|Tercero|Cuarto|Quinto|Sexto|S[eé]ptimo|Octavo|Noveno|D[eé]cimo"
)
_RE_ARTICULO = re.compile(
    rf"^(?:Art[ií]culo|ART[IÍ]CULO|Art\.)\s*(\d{{1,3}}|{_ORDINALES})\s*[°º]?\s*[.:\-–]*\s*(.*)$"
)
_RE_NUMERAL = re.compile(r"^(\d{1,2}(?:\.\d{1,2}){0,3})\.?\s*(?=[A-ZÁÉÍÓÚÑ¿])(.{2,})$")
_RE_LETRA = re.compile(r"^([A-H])\.\s+(.+)$")


def _es_mayusculas(texto: str) -> bool:
    # "º" y "ª" son minúsculas para Python ('º'.islower() es True): se ignoran.
    letras = [c for c in texto if c not in "ºª" and (c.isupper() or c.islower())]
    return len(letras) >= 3 and not any(c.islower() for c in letras)


def _corto(linea: str, maximo: int = 110) -> bool:
    return len(linea) <= maximo


def _tipo_seccion(linea: str) -> str | None:
    s = linea.strip()
    if not _corto(s) or ":" in s or s.endswith((".", ",", ";")):
        return None
    if _RE_CLAUSULA_SOLA.match(s):
        return "clausula_sola"
    m = _RE_PARTE.match(s)
    if m and _es_mayusculas(s):
        return "parte"
    # Un título de sección no tiene punto en medio: si lo tiene, es texto corrido que
    # casualmente empieza con esas palabras ("Cláusulas Generales de Contratación. La ...").
    if "." in s:
        return None
    if _RE_CLAUSULA_TITULO.match(s):
        return "clausula_titulo"
    if _RE_SECCION_NOMBRADA.match(s):
        return "nombrada"
    return None


def _parece_encabezado(s: str) -> bool:
    return bool(
        _corto(s, 95)
        and (_tipo_seccion(s) or _RE_ARTICULO.match(s) or _RE_NUMERAL.match(s) or _RE_LETRA.match(s))
    )


def _marcar_indices(lineas: list[Linea]) -> None:
    """Marca las líneas de un índice: 5 o más encabezados seguidos sin texto entre ellos.

    Sin esto, el índice de la póliza genera secciones y artículos vacíos.
    """
    i = 0
    while i < len(lineas):
        if not _parece_encabezado(lineas[i].texto):
            i += 1
            continue
        j, encabezados = i, 0
        while j < len(lineas):
            s = lineas[j].texto
            if _parece_encabezado(s):
                encabezados += 1
            elif not (len(s) <= 45 and j > i and _parece_encabezado(lineas[j - 1].texto)):
                break  # se admite una línea corta de continuación ("seguro", "RECLAMOS")
            j += 1
        if encabezados >= 5:
            # El título de la sección que precede al índice ("Condiciones Generales",
            # "Índice") no es parte del índice: es la sección real que empieza ahí.
            k = i
            while k < j and (
                _tipo_seccion(lineas[k].texto) in ("nombrada", "clausula_titulo", "clausula_sola")
                or not _parece_encabezado(lineas[k].texto)
            ):
                k += 1
            for ln in lineas[k:j]:
                ln.indice = True
        i = max(j, i + 1)


def _continuar_titulo(titulo: str, lineas: list[Linea], i: int) -> tuple[str, int]:
    """Une al encabezado sus líneas de continuación (títulos en mayúsculas partidos).

    Devuelve el título completo y el índice de la primera línea que ya no es título.
    """
    while i < len(lineas):
        sig = lineas[i].texto
        if lineas[i].indice or _parece_encabezado(sig):
            break
        partido = titulo.endswith("-")
        continua = _es_mayusculas(titulo) and _es_mayusculas(sig) and len(sig) <= 60
        if not (partido or continua):
            break
        titulo = titulo[:-1] + sig if partido else f"{titulo} {sig}"
        i += 1
    return titulo, i


def _partir_en_secciones(lineas: list[Linea]) -> list[tuple[str, list[Linea], int]]:
    """Devuelve (nombre, líneas, cuántas de las primeras líneas son el título)."""
    secciones: list[tuple[str, list[Linea], int]] = [("Inicio del documento", [], 0)]
    i = 0
    while i < len(lineas):
        ln = lineas[i]
        tipo = None if ln.indice else _tipo_seccion(ln.texto)
        if tipo is None:
            secciones[-1][1].append(ln)
            i += 1
            continue
        if tipo == "clausula_sola":
            # El título está en las líneas anteriores de la misma página (puede ocupar varias)
            previas = secciones[-1][1]
            titulo: list[Linea] = []
            while (
                previas
                and len(titulo) < 5
                and previas[-1].pagina == ln.pagina
                and not previas[-1].texto.endswith((".", ":", ";"))
                and _corto(previas[-1].texto)
                and not _parece_encabezado(previas[-1].texto)
            ):
                titulo.insert(0, previas.pop())
            nombre = " ".join(t.texto for t in titulo).strip() or "Sin título"
            secciones.append((f"Cláusula Adicional: {nombre}", titulo + [ln], len(titulo) + 1))
            i += 1
        else:
            nombre, j = _continuar_titulo(ln.texto.strip(), lineas, i + 1)
            secciones.append((nombre, lineas[i:j], j - i))
            i = j
    return [s for s in secciones if s[1]]


_CONECTORES = {"de", "del", "la", "las", "el", "los", "que", "por", "y", "o", "a", "en", "con", "para", "al", "su", "sus", "se", "un", "una"}


def _etiqueta_numeral(numero: str, titulo: str) -> str:
    """'9.5. Exámenes de ayuda al diagnóstico' o, si es el inicio de un párrafo, 'numeral 11.1'."""
    titulo = titulo.strip()
    if _es_mayusculas(titulo):
        return f"{numero}. {titulo}"
    palabras = titulo.split()
    corta = len(palabras) <= 8 and ". " not in titulo
    sigue_la_oracion = titulo.endswith("-") or palabras[-1].lower() in _CONECTORES
    if corta and not sigue_la_oracion:
        return f"{numero}. {titulo}"
    return f"numeral {numero}"


def _bloques_de_seccion(nombre: str, lineas: list[Linea], n_titulo: int) -> list[Bloque]:
    utiles = [ln for ln in lineas if not ln.indice]
    modo_articulo = sum(1 for ln in utiles if _RE_ARTICULO.match(ln.texto)) >= 2
    numerales_mayus = sum(
        1
        for ln in utiles
        if (m := _RE_NUMERAL.match(ln.texto)) and _es_mayusculas(m.group(2)) and _corto(ln.texto)
    )
    # Si la sección titula sus numerales en mayúsculas, los numerales en minúsculas son
    # ítems de una lista ("1. Una declaración escrita..."), no encabezados.
    permitir_mixtos = numerales_mayus < 2

    bloques = [Bloque(nombre, [], n_encabezado=n_titulo)]
    ruta: list[tuple[int, str]] = []  # (profundidad, etiqueta); 0 = grupo o artículo
    articulo_num: str | None = None
    ultimo_principal = 0
    i = 0
    while i < len(lineas):
        ln = lineas[i]
        s = ln.texto
        j = i + 1
        nueva: list[tuple[int, str]] | None = None
        prefijo: list[Linea] = []

        if ln.indice:
            pass
        elif modo_articulo:
            m_art = _RE_ARTICULO.match(s)
            m_num = _RE_NUMERAL.match(s)
            if m_art:
                titulo, j = _continuar_titulo(s, lineas, i + 1)
                articulo_num = m_art.group(1) if m_art.group(1).isdigit() else None
                nueva = [(0, titulo)]
            elif m_num and articulo_num and _corto(s):
                partes = m_num.group(1).split(".")
                # Subnumeral del artículo en curso: "9.5 Exámenes..." dentro del Artículo 9°
                if len(partes) >= 2 and partes[0] == articulo_num:
                    etiqueta = _etiqueta_numeral(m_num.group(1), m_num.group(2))
                    if _es_mayusculas(m_num.group(2)):
                        etiqueta, j = _continuar_titulo(etiqueta, lineas, i + 1)
                    profundidad = len(partes) - 1
                    nueva = [r for r in ruta if r[0] < profundidad] + [(profundidad, etiqueta)]
        else:
            m_num = _RE_NUMERAL.match(s)
            m_letra = _RE_LETRA.match(s)
            if m_letra and _es_mayusculas(m_letra.group(2)) and _corto(s, 80):
                titulo, j = _continuar_titulo(s, lineas, i + 1)
                nueva = [(0, titulo)]
                ultimo_principal = 0
            elif m_num and _corto(s):
                numero, titulo = m_num.group(1), m_num.group(2)
                partes = numero.split(".")
                profundidad, principal = len(partes), int(partes[0])
                previa = bloques[-1].lineas[-1] if bloques[-1].lineas else None
                es_rotulo = bool(
                    previa is not None
                    and not previa.indice
                    and _es_mayusculas(previa.texto)
                    and _corto(previa.texto, 60)
                    and not _parece_encabezado(previa.texto)
                )
                if _es_mayusculas(titulo):
                    es_titulo = True
                else:
                    es_titulo = permitir_mixtos and profundidad == 1 and (
                        principal == ultimo_principal + 1
                        or (principal == 1 and (ultimo_principal == 0 or es_rotulo))
                    )
                if es_titulo:
                    etiqueta = f"{numero}. {titulo}"
                    if _es_mayusculas(titulo):
                        etiqueta, j = _continuar_titulo(etiqueta, lineas, i + 1)
                    base = ruta
                    if profundidad == 1 and principal == 1 and es_rotulo:
                        # "INFORMACIÓN DE LA PÓLIZA DE SEGURO" + "1.Riesgos Cubiertos":
                        # el rótulo encabeza un grupo nuevo y su línea pasa al bloque nuevo.
                        prefijo = [bloques[-1].lineas.pop()]
                        base = [(0, previa.texto)]
                    elif profundidad == 1 and principal == 1 and ultimo_principal > 0:
                        base = [r for r in ruta if r[0] == 0 and _RE_LETRA.match(r[1])]
                    nueva = [r for r in base if r[0] < profundidad] + [(profundidad, etiqueta)]
                    if profundidad == 1:
                        ultimo_principal = principal

        if nueva is not None:
            ruta = nueva
            bloque = Bloque(nombre, [r[1] for r in ruta])
            bloque.lineas.extend(prefijo + lineas[i:j])  # el encabezado es texto literal del PDF
            bloque.n_encabezado = len(prefijo) + (j - i)
            bloques.append(bloque)
        else:
            bloques[-1].lineas.extend(lineas[i:j])
        i = j
    return bloques


def _cuerpo(bloque: Bloque) -> str:
    return " ".join(ln.texto for ln in bloque.lineas[bloque.n_encabezado :] if not ln.indice)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------


def lineas_por_pagina(pdf_bytes: bytes) -> tuple[list[list[str]], list[int], list[int]]:
    """Texto crudo por página (con columnas resueltas), páginas vacías y a dos columnas."""
    paginas: list[list[str]] = []
    vacias, dos_columnas = [], []
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        for n, page in enumerate(pdf.pages, start=1):
            lineas, columnas = _texto_pagina(page)
            if sum(len(x.strip()) for x in lineas) < 40:
                vacias.append(n)
            if columnas:
                dos_columnas.append(n)
            paginas.append(lineas)
            page.flush_cache()
    return paginas, vacias, dos_columnas


def texto_de_paginas(pdf_bytes: bytes, paginas: list[int]) -> str:
    """Texto de algunas páginas (numeradas desde 1), leído de nuevo desde el PDF."""
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join("\n".join(_texto_pagina(pdf.pages[n - 1])[0]) for n in paginas if 0 < n <= len(pdf.pages))


def extraer(pdf_bytes: bytes) -> DocumentoExtraido:
    """Del PDF (bytes en memoria) a bloques por sección y artículo, con su página."""
    return extraer_varios([pdf_bytes])


def extraer_varios(pdfs: list[bytes]) -> DocumentoExtraido:
    """Una póliza que viene en varios PDF, como un solo documento. Los membretes se quitan por
    archivo (cada uno tiene los suyos); las páginas se numeran de corrido en el orden dado, que
    es el de las páginas del PDF unido (ai/subida.py), y la estructura se lee de corrido: un
    artículo que empieza en un archivo y sigue en el otro queda en un mismo bloque."""
    limpias: list[list[str]] = []
    vacias: list[int] = []
    dos_columnas: list[int] = []
    quitadas: list[str] = []
    por_archivo: list[int] = []
    for pdf_bytes in pdfs:
        crudas, v, d = lineas_por_pagina(pdf_bytes)
        estas, q = _quitar_membretes(crudas)
        base = len(limpias)
        vacias += [base + n for n in v]
        dos_columnas += [base + n for n in d]
        quitadas += [x for x in q if x not in quitadas]
        limpias += estas
        por_archivo.append(len(crudas))

    lineas = [Linea(t, n) for n, pag in enumerate(limpias, start=1) for t in pag]
    _marcar_indices(lineas)
    bloques: list[Bloque] = []
    for nombre, lineas_seccion, n_titulo in _partir_en_secciones(lineas):
        de_la_seccion = _bloques_de_seccion(nombre, lineas_seccion, n_titulo)
        if len(de_la_seccion) == 1 and not de_la_seccion[0].ruta:
            de_la_seccion[0].sin_articulos = True
        if nombre == "Inicio del documento" and len(_cuerpo(de_la_seccion[0])) < 60:
            de_la_seccion = de_la_seccion[1:]  # solo el título de la portada
        bloques.extend(de_la_seccion)
    # Fuera: portadas e índices (bloques sin texto propio más allá del encabezado)
    bloques = [b for b in bloques if len(_cuerpo(b)) >= 20]

    return DocumentoExtraido(
        paginas_total=len(limpias),
        paginas_sin_texto=vacias,
        paginas_dos_columnas=dos_columnas,
        lineas_quitadas=quitadas,
        bloques=bloques,
        paginas_por_archivo=por_archivo,
    )

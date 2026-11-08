"""Recuperación (RAG, sesión 08): de la pregunta normalizada a los pasajes de la póliza.

Producto: BM25 con varias consultas. Cada variante de la normalización, la cláusula del
documento que la normalización eligió y la pregunta original (a medio peso) se buscan por
separado y los rankings se combinan con Reciprocal Rank Fusion (RRF). Así una sola
reformulación desafortunada no deja fuera la cláusula: basta que una consulta use las
palabras de la póliza.

Filtro suave por cláusula: los pasajes de la cláusula que eligió la normalización
multiplican su puntaje por FACTOR_CLAUSULA (×2). No se excluye el resto: si el modelo eligió
mal la cláusula, un artículo de otra parte todavía puede llegar si coincide mucho más con
las consultas (en P10 no alcanzó: pruebas/normalizacion.md).

Índice de títulos (PESO_TITULO): cada consulta se puede buscar también en un índice que
solo tiene los títulos de cada trozo. Está apagado (0): medido, empeora la búsqueda con y
sin el filtro por cláusula (pruebas/normalizacion.md). Los artículos que elige la
normalización tampoco se usan, por lo mismo.

Determinista: con las mismas consultas sale siempre el mismo orden. Los empates se deciden
por la posición del trozo en el documento (orden estable), no por el algoritmo de numpy ni
por la CPU.

Los métodos con embeddings existen solo para la comparación de pruebas/: la app no carga
el modelo (ocupa ~1,2 GB de RAM con torch).
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

import numpy as np

from ai.indice import Indice, tokens
from ai.troceado import Trozo

K_RRF = 60
PESO_PREGUNTA = 0.5  # la pregunta coloquial trae palabras que confunden ("dedo" -> desmembramiento)
PESO_TITULO = 0.0  # ranking por títulos frente al del texto (0 = apagado; ver arriba)
FACTOR_CLAUSULA = 2.0  # puntaje de los pasajes de la cláusula elegida; fijado antes de medir
METODOS = ("bm25_pregunta", "bm25_variantes", "emb_pregunta", "emb_variantes")


@dataclass
class Pasaje:
    id: str  # "P1", "P2"... tal como lo ve el modelo
    trozo: Trozo
    puntaje: float
    rango: int  # 1 = el más relevante; 0 = agregado como continuación de su artículo


def _ranking_bm25(indice: Indice, consulta: str) -> np.ndarray:
    tk = tokens(consulta)
    if not tk:
        return np.array([], dtype=int)
    puntajes = indice.bm25.get_scores(tk)
    orden = np.argsort(-puntajes, kind="stable")
    return orden[puntajes[orden] > 0]


def _ranking_titulos(indice: Indice, consulta: str) -> tuple[np.ndarray, np.ndarray]:
    """Trozos cuyo título coincide con la consulta y su puesto. Los empatados (las partes de
    un mismo artículo, que comparten título) comparten puesto: el título sube el artículo
    entero, no una parte al azar."""
    tk = tokens(consulta)
    if not tk:
        return np.array([], dtype=int), np.array([], dtype=int)
    puntajes = np.round(indice.bm25_titulos.get_scores(tk), 6)
    orden = np.argsort(-puntajes, kind="stable")
    orden = orden[puntajes[orden] > 0]
    distintos = -np.unique(-puntajes[orden])  # de mayor a menor
    puesto = {v: r for r, v in enumerate(distintos)}
    return orden, np.array([puesto[v] for v in puntajes[orden]], dtype=int)


def _ranking_embeddings(indice: Indice, consulta: str) -> np.ndarray:
    from ai.indice import embeber_consulta  # carga perezosa: solo en evaluación

    if indice.vectores is None:
        raise ValueError("este índice no tiene embeddings")
    return np.argsort(-(indice.vectores @ embeber_consulta(consulta)), kind="stable")


def _rrf(rankings: list[tuple[np.ndarray, np.ndarray | None, float]], n: int) -> np.ndarray:
    """Puntaje RRF de cada trozo. rankings: (orden, puesto de cada uno o None si es su posición, peso)."""
    puntaje = np.zeros(n)
    for orden, puestos, peso in rankings:
        for pos, i in enumerate(orden[:100]):
            r = pos if puestos is None else puestos[pos]
            puntaje[i] += peso / (K_RRF + r + 1)
    return puntaje


def _ordenar(puntaje: np.ndarray) -> list[tuple[int, float]]:
    orden = np.argsort(-puntaje, kind="stable")
    return [(int(i), float(puntaje[i])) for i in orden if puntaje[i] > 0]


def _en_clausulas(indice: Indice, clausulas: list[str]) -> np.ndarray:
    elegidas = {" ".join(tokens(c)) for c in clausulas}
    return np.array([" ".join(tokens(c or "")) in elegidas for c in indice.clausula_de_trozo])


def _rankings_bm25(indice: Indice, consultas: list[tuple[str, float]], peso_titulo: float):
    salida = [(_ranking_bm25(indice, c), None, p) for c, p in consultas]
    if peso_titulo > 0:
        salida += [(*_ranking_titulos(indice, c), p * peso_titulo) for c, p in consultas]
    return salida


def rankear(
    indice: Indice,
    pregunta: str,
    variantes: list[str],
    terminos: list[str],
    metodo: str,
    titulos: list[str] | None = None,
    peso_titulo: float = PESO_TITULO,
    clausulas: list[str] | None = None,
    factor_clausula: float = FACTOR_CLAUSULA,
) -> list[tuple[int, float]]:
    """Ranking completo (índice del trozo, puntaje) según el método. `titulos` son los
    títulos del documento que eligió la normalización: cada uno es una consulta más.
    `peso_titulo=0` apaga el índice de títulos (BM25 solo sobre el texto). Los trozos de
    `clausulas` multiplican su puntaje por `factor_clausula` (filtro suave)."""
    n = len(indice.trozos)
    if metodo == "bm25_pregunta":
        if peso_titulo > 0:
            return _ordenar(_rrf(_rankings_bm25(indice, [(pregunta, 1.0)], peso_titulo), n))
        orden = _ranking_bm25(indice, pregunta)
        return [(int(i), 1.0 / (r + 1)) for r, i in enumerate(orden)]
    if metodo == "emb_pregunta":
        orden = _ranking_embeddings(indice, pregunta)
        return [(int(i), 1.0 / (r + 1)) for r, i in enumerate(orden)]

    consultas = [(v, 1.0) for v in variantes]
    consultas += [(t, 1.0) for t in titulos or []]
    if terminos:
        consultas.append((" ".join(terminos), 1.0))
    consultas.append((pregunta, PESO_PREGUNTA))
    if metodo == "bm25_variantes":
        puntaje = _rrf(_rankings_bm25(indice, consultas, peso_titulo), n)
    elif metodo == "emb_variantes":
        puntaje = _rrf([(_ranking_embeddings(indice, c), None, p) for c, p in consultas], n)
    else:
        raise ValueError(f"método desconocido: {metodo}")
    if clausulas and factor_clausula != 1.0:
        puntaje = np.where(_en_clausulas(indice, clausulas), puntaje * factor_clausula, puntaje)
    return _ordenar(puntaje)


def top_k(
    indice: Indice,
    pregunta: str,
    variantes: list[str],
    terminos: list[str],
    metodo: str,
    k: int,
    titulos: list[str] | None = None,
    peso_titulo: float = PESO_TITULO,
    clausulas: list[str] | None = None,
    factor_clausula: float = FACTOR_CLAUSULA,
) -> list[tuple[int, float]]:
    """Los k mejores trozos sin repetir texto.

    Los condicionados repiten artículos idénticos en cada cláusula adicional (en Chubb,
    "Artículo 2° Vigencia Individual y Territorio" aparece 9 veces). Cada texto ocupa un
    solo lugar, y entre sus copias se elige la de la sección cuyo nombre más coincide con
    la consulta: para una pregunta de gastos médicos, la copia de "Gastos Médicos".
    """
    consulta = Counter(tokens(" ".join([*variantes, *(titulos or []), *terminos, pregunta])))

    def afinidad(i: int) -> int:
        return sum(consulta[t] for t in set(tokens(indice.trozos[i].seccion)))

    grupos: dict[str, list[tuple[int, float]]] = {}
    for i, p in rankear(indice, pregunta, variantes, terminos, metodo, titulos, peso_titulo, clausulas, factor_clausula):
        grupos.setdefault(indice.claves_texto[i], []).append((i, p))
    elegidos = []
    for miembros in list(grupos.values())[:k]:  # los grupos conservan el orden del ranking
        mejor = max(miembros, key=lambda m: (afinidad(m[0]), m[1]))
        elegidos.append((mejor[0], miembros[0][1]))
    return elegidos


def recuperar(
    indice: Indice,
    pregunta: str,
    variantes: list[str],
    terminos: list[str],
    k: int = 5,
    metodo: str = "bm25_variantes",
    continuar: int = 2,
    maximo: int = 12,
    presupuesto_caracteres: int = 6500,
    titulos: list[str] | None = None,
    peso_titulo: float = PESO_TITULO,
    clausulas: list[str] | None = None,
    factor_clausula: float = FACTOR_CLAUSULA,
) -> list[Pasaje]:
    """Los k pasajes más relevantes y, para los `continuar` primeros, las otras partes de
    su mismo artículo (un artículo largo partido en dos no debe llegar a medias).

    `presupuesto_caracteres` limita las continuaciones (los k primeros entran siempre): el
    plan gratuito cuenta tokens por minuto. k = 5 y 6500 caracteres es la opción A de
    pruebas/opciones.md: unos 4600 tokens por respuesta en vez de 6600."""
    ranking = top_k(indice, pregunta, variantes, terminos, metodo, k, titulos, peso_titulo, clausulas, factor_clausula)
    elegidos: list[tuple[int, float, int]] = [(i, p, r + 1) for r, (i, p) in enumerate(ranking)]
    presentes = {i for i, _, _ in elegidos}
    total = sum(len(indice.trozos[i].texto) for i in presentes)

    for i, _, _ in list(elegidos[:continuar]):
        t = indice.trozos[i]
        if t.partes == 1:
            continue
        for j in range(max(0, i - t.partes), min(len(indice.trozos), i + t.partes)):
            vecino = indice.trozos[j]
            if j not in presentes and vecino.seccion == t.seccion and vecino.articulo == t.articulo:
                if len(elegidos) >= maximo or total + len(vecino.texto) > presupuesto_caracteres:
                    break
                elegidos.append((j, 0.0, 0))
                presentes.add(j)
                total += len(vecino.texto)

    return [
        Pasaje(id=f"P{n}", trozo=indice.trozos[i], puntaje=p, rango=r)
        for n, (i, p, r) in enumerate(elegidos, start=1)
    ]


def recuperar_normalizada(indice: Indice, pregunta: str, norm: dict, **opciones) -> list[Pasaje]:
    """recuperar() con lo que la app usa de una normalización: sus variantes y su cláusula
    elegida, como consulta y como filtro suave. Las normalizaciones v1 (sin cláusulas) usan
    sus términos. La app, las pruebas y los scripts pasan todos por aquí."""
    return recuperar(indice, pregunta, norm["variantes"], norm.get("terminos", []),
                     titulos=norm.get("clausulas"), clausulas=norm.get("clausulas"), **opciones)


_RE_PALABRA = re.compile(r"[0-9A-Za-zÁÉÍÓÚÜÑáéíóúüñ]+")


def resaltar(texto: str, consultas: list[str]) -> list[list[int]]:
    """Posiciones [inicio, fin) de las palabras del texto que coinciden (por raíz) con las
    consultas. Para el modo sin texto generado: muestra por qué se encontró cada cláusula."""
    buscadas = {t for c in consultas for t in tokens(c)}
    marcas = []
    for m in _RE_PALABRA.finditer(texto):
        raiz = tokens(m.group(0))
        if raiz and raiz[0] in buscadas:
            marcas.append([m.start(), m.end()])
    return marcas


def pasajes_xml(pasajes: list[Pasaje]) -> str:
    def esc(s: str) -> str:  # solo atributos: el texto va tal cual para que la cita sea literal
        return s.replace('"', "'").replace("<", "(").replace(">", ")")

    bloques = []
    for p in pasajes:
        t = p.trozo
        parte = f" (parte {t.parte} de {t.partes})" if t.partes > 1 else ""
        bloques.append(
            f'<pasaje id="{p.id}" seccion="{esc(t.seccion)}" articulo="{esc(t.articulo)}{parte}" '
            f'paginas="{t.paginas_texto}">\n{t.texto}\n</pasaje>'
        )
    return "\n".join(bloques)

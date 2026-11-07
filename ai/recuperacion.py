"""Recuperación (RAG, sesión 08): de la pregunta normalizada a los pasajes de la póliza.

Producto: BM25 con varias consultas. Cada variante de la normalización, los términos del
seguro y la pregunta original (a medio peso) se buscan por separado y los rankings se
combinan con Reciprocal Rank Fusion (RRF). Así una sola reformulación desafortunada no
deja fuera la cláusula: basta que una variante use las palabras de la póliza.

Los métodos con embeddings existen solo para la comparación de pruebas/: la app no carga
el modelo (ocupa ~1,2 GB de RAM con torch).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np

from ai.indice import Indice, tokens
from ai.troceado import Trozo

K_RRF = 60
PESO_PREGUNTA = 0.5  # la pregunta coloquial trae palabras que confunden ("dedo" -> desmembramiento)
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
    orden = np.argsort(-puntajes)
    return orden[puntajes[orden] > 0]


def _ranking_embeddings(indice: Indice, consulta: str) -> np.ndarray:
    from ai.indice import embeber_consulta  # carga perezosa: solo en evaluación

    if indice.vectores is None:
        raise ValueError("este índice no tiene embeddings")
    return np.argsort(-(indice.vectores @ embeber_consulta(consulta)))


def _rrf(rankings: list[tuple[np.ndarray, float]], n: int) -> list[tuple[int, float]]:
    puntaje = np.zeros(n)
    for orden, peso in rankings:
        for r, i in enumerate(orden[:100]):
            puntaje[i] += peso / (K_RRF + r + 1)
    orden = np.argsort(-puntaje)
    return [(int(i), float(puntaje[i])) for i in orden if puntaje[i] > 0]


def rankear(indice: Indice, pregunta: str, variantes: list[str], terminos: list[str], metodo: str) -> list[tuple[int, float]]:
    """Ranking completo (índice del trozo, puntaje) según el método."""
    n = len(indice.trozos)
    if metodo == "bm25_pregunta":
        orden = _ranking_bm25(indice, pregunta)
        return [(int(i), 1.0 / (r + 1)) for r, i in enumerate(orden)]
    if metodo == "emb_pregunta":
        orden = _ranking_embeddings(indice, pregunta)
        return [(int(i), 1.0 / (r + 1)) for r, i in enumerate(orden)]

    consultas = [(v, 1.0) for v in variantes]
    if terminos:
        consultas.append((" ".join(terminos), 1.0))
    consultas.append((pregunta, PESO_PREGUNTA))
    if metodo == "bm25_variantes":
        return _rrf([(_ranking_bm25(indice, c), p) for c, p in consultas], n)
    if metodo == "emb_variantes":
        return _rrf([(_ranking_embeddings(indice, c), p) for c, p in consultas], n)
    raise ValueError(f"método desconocido: {metodo}")


def top_k(indice: Indice, pregunta: str, variantes: list[str], terminos: list[str], metodo: str, k: int) -> list[tuple[int, float]]:
    """Los k mejores trozos sin repetir texto.

    Los condicionados repiten artículos idénticos en cada cláusula adicional (en Chubb,
    "Artículo 2° Vigencia Individual y Territorio" aparece 9 veces). Cada texto ocupa un
    solo lugar, y entre sus copias se elige la de la sección cuyo nombre más coincide con
    la consulta: para una pregunta de gastos médicos, la copia de "Gastos Médicos".
    """
    consulta = Counter(tokens(" ".join([*variantes, *terminos, pregunta])))

    def afinidad(i: int) -> int:
        return sum(consulta[t] for t in set(tokens(indice.trozos[i].seccion)))

    grupos: dict[int, list[tuple[int, float]]] = {}
    for i, p in rankear(indice, pregunta, variantes, terminos, metodo):
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
    k: int = 8,
    metodo: str = "bm25_variantes",
    continuar: int = 3,
    maximo: int = 12,
) -> list[Pasaje]:
    """Los k pasajes más relevantes y, para los `continuar` primeros, las otras partes de
    su mismo artículo (un artículo largo partido en dos no debe llegar a medias)."""
    ranking = top_k(indice, pregunta, variantes, terminos, metodo, k)
    elegidos: list[tuple[int, float, int]] = [(i, p, r + 1) for r, (i, p) in enumerate(ranking)]
    presentes = {i for i, _, _ in elegidos}

    for i, _, _ in list(elegidos[:continuar]):
        t = indice.trozos[i]
        if t.partes == 1:
            continue
        for j in range(max(0, i - t.partes), min(len(indice.trozos), i + t.partes)):
            vecino = indice.trozos[j]
            if j not in presentes and vecino.seccion == t.seccion and vecino.articulo == t.articulo:
                if len(elegidos) >= maximo:
                    break
                elegidos.append((j, 0.0, 0))
                presentes.add(j)

    return [
        Pasaje(id=f"P{n}", trozo=indice.trozos[i], puntaje=p, rango=r)
        for n, (i, p, r) in enumerate(elegidos, start=1)
    ]


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

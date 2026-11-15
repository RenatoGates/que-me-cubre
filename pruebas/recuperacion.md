# Recuperación: BM25 con variantes frente a embeddings

Generado por `pruebas/evaluar_recuperacion.py` con las normalizaciones de `pruebas/salidas/` (Claude Haiku). Embeddings: `voyage-4-large`.

9 de las 10 preguntas tienen un artículo esperado (la P08 es de control: la respuesta
correcta es no encontrar nada, así que no se puede acertar ni fallar en la búsqueda).
Acierta = el artículo esperado está entre los k primeros pasajes (sin repetir textos idénticos).
La app manda al modelo k = 5 (opción A de `pruebas/opciones.md`).

| Método | Aciertos con k = 3 | Aciertos con k = 5 | Aciertos con k = 8 |
|---|---:|---:|---:|
| BM25, pregunta original | 1 de 9 | 2 de 9 | 4 de 9 |
| BM25, 3-5 variantes normalizadas (respaldo) | 1 de 9 | 2 de 9 | 4 de 9 |
| Embeddings por API, pregunta original (app) | 7 de 9 | 7 de 9 | 8 de 9 |
| Embeddings por API, mismas variantes | 7 de 9 | 7 de 9 | 8 de 9 |
| Híbrido: BM25 + embeddings, mismas variantes | 5 de 9 | 6 de 9 | 7 de 9 |

## Por pregunta (k = 5)

| Pregunta | bm25_pregunta | bm25_variantes | emb_pregunta | emb_variantes | hibrido_variantes |
|---|---|---|---|---|---|
| P01 | ✗ | ✗ | ✓ | ✓ | ✓ |
| P02 | ✗ | ✗ | ✗ | ✗ | ✗ |
| P03 | ✗ | ✗ | ✓ | ✓ | ✓ |
| P04 | ✗ | ✗ | ✗ | ✗ | ✗ |
| P05 | ✗ | ✗ | ✓ | ✓ | ✗ |
| P06 | ✗ | ✗ | ✓ | ✓ | ✓ |
| P07 | ✗ | ✗ | ✓ | ✓ | ✓ |
| P09 | ✓ | ✓ | ✓ | ✓ | ✓ |
| P10 | ✓ | ✓ | ✓ | ✓ | ✓ |

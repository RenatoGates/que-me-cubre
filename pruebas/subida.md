# Subir una póliza con embeddings

Generado por `pruebas/medir_subida.py` con `voyage-4-large`, en esta máquina, con la cuenta de Voyage ya con medio de pago (límite normal por minuto).

- Subida completa de una póliza de 62 páginas (246 pasajes): extracción, troceado, embeddings e índice: **17.4 s**.
- De eso, los embeddings de los 246 pasajes: 3.8 s y 68973 tokens.
- Embedding de una consulta: 0.64 s.
- Con el saldo gratuito de Voyage (200 millones de tokens) alcanza para unas 2899 pólizas de este tamaño.

Sin medio de pago, Voyage limita la cuenta a 3 peticiones y 10 000 tokens por minuto: la misma póliza, en lotes con pausas (`python -m ai.ingesta --paciente`), tardó 400 s el 2026-11-15, y una subida en vivo se queda sin vectores (se busca con BM25).

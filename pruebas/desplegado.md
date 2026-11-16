# Flujo completo contra el backend desplegado

Generado por `pruebas/probar_desplegado.py` contra `https://que-me-cubre-api.onrender.com` el 2026-11-15 18:39.

| Comprobación | ¿Pasa? |
|---|---|
| el servidor responde y usa Claude Haiku con embeddings de Voyage | sí |
| subir un PDF de 62 páginas: indexado con embeddings | sí |
| P01: veredicto aceptable (con_limites) | sí |
| P01: las 2 citas vienen verificadas contra el PDF y con artículo y página | sí |
| P02: veredicto aceptable (con_limites) | sí |
| P02: las 2 citas vienen verificadas contra el PDF y con artículo y página | sí |
| P02: B4 aparece en el bloque de lo mencionado pero ausente, con su página | sí |
| mapa: establecimientos de Tarapoto con el aviso de que no es la red de la aseguradora | sí |
| borrar la póliza subida | sí |

Subir e indexar la póliza de 62 páginas en el servidor: 110.4 s.

| Pregunta | Veredicto | Citas verificadas | Páginas citadas | USD | Segundos (ida y vuelta) |
|---|---|---:|---|---:|---:|
| P01 | con_limites | 2 | 16, 17 | 0.0017 | 25.8 |
| P02 | con_limites | 2 | 16, 16 | 0.0022 | 20.9 |

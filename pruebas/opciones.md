# Recortar tokens por consulta: opciones medidas

Generado por `pruebas/comparar_opciones.py resumen`. Corridas del 2026-11-07 con las mismas
normalizaciones de la caché (una llamada por respuesta) y `openai/gpt-oss-120b` salvo en C.

Meta: 5 consultas en 3 minutos = una cada 36 s. En 36 s el plan repone 4800 tokens, así que cada consulta tiene que gastar unos 4800 o menos.
Separación mínima calculada con `pruebas/simular_cuota.py` sobre las 5 consultas más caras de
cada configuración. *Balde recién usado*: alguien acaba de hacer una consulta antes de empezar.

| Configuración | Aceptables | Citas válidas / propuestas | Pasajes | Entrada | Salida (razonamiento) | Tokens por respuesta | Pregunta nueva | Separación mínima, en caché | …nuevas | …balde recién usado | A 36 s con el balde recién usado, entran (de 5) | Errores |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Actual al medir: k = 8 (+3 continuaciones, 13 000 caracteres), razonamiento medio, 120b | 6 de 10 | 19 / 23 | 10.5 | 4770 | 1813 (71%) | 6583 (máx. 7421) | 7541 | 46 s | 54 s | 49 s | 1 | — |
| A. Menos pasajes: k = 5 (+2 continuaciones, 6500 caracteres) | 7 de 9 | 17 / 17 | 5.2 | 3137 | 1473 (74%) | 4610 (máx. 5418) | 5562 | 28 s | 36 s | 34 s | 5 | 1 |
| A + B. Menos pasajes y razonamiento bajo | 6 de 10 | 10 / 11 | 5.2 | 3070 | 455 (26%) | 3525 (máx. 4139) | 4484 | 19 s | 27 s | 27 s | 5 | — |
| C. gpt-oss-20b con la configuración actual | 2 de 5 | 10 / 10 | 10.4 | 4614 | 2183 (85%) | 6797 (máx. 7941) | 7762 | no aplica | no aplica | no aplica | no aplica | 5 |

Con gpt-oss-20b la separación no se puede simular con la regla de 120b: Groq le suma el máximo
de salida (3000) a lo pedido, así que cada llamada necesita casi el balde entero (ver abajo).

## Veredicto por pregunta

| Pregunta | base_k8 | A_k5 | AB_k5_low | C_20b |
|---|---|---|---|---|
| P01 | no_encontrado ✗ | no_encontrado ✗ | no_encontrado ✗ | si ✗ |
| P02 | con_limites ✗ | con_limites ✗ | no_encontrado ✗ | no ✗ |
| P03 | no_encontrado ✗ | con_limites ✓ | no_encontrado ✗ | con_limites ✓ |
| P04 | con_limites ✓ | con_limites ✓ | con_limites ✓ | error |
| P05 | con_limites ✓ | con_limites ✓ | con_limites ✓ | error |
| P06 | con_limites ✓ | con_limites ✓ | no ✗ | error |
| P07 | no ✓ | no ✓ | no ✓ | error |
| P08 | no_encontrado ✓ | no_encontrado ✓ | no_encontrado ✓ | error |
| P09 | no ✗ | error | no_encontrado ✓ | no ✗ |
| P10 | con_limites ✓ | con_limites ✓ | con_limites ✓ | con_limites ✓ |

## Pasajes según k (sin LLM)

Lo que de verdad llega al modelo (con continuaciones) y si el artículo esperado está entre
eso, en las 9 preguntas con artículo esperado.

| Pasajes | Pasajes promedio | Caracteres del mensaje (prom. / máx.) | Artículo esperado presente | Falla en |
|---|---:|---:|---:|---|
| k = 8 (actual al medir) | 10.5 | 14721 / 17654 | 7 de 9 | P01, P02 |
| k = 6, 8000 caracteres | 6.4 | 9551 / 10781 | 6 de 9 | P01, P02, P09 |
| k = 5, 6500 caracteres (A) | 5.2 | 7915 / 9372 | 6 de 9 | P01, P02, P09 |
| k = 4, 5500 caracteres | 4.3 | 6672 / 7808 | 6 de 9 | P01, P02, P09 |
| k = 3, 4500 caracteres | 3.4 | 5508 / 6841 | 4 de 9 | P01, P02, P06, P07, P09 |

## Observaciones sueltas

- **openai/gpt-oss-120b**, dos respuestas seguidas de P01 (k = 8, entrada de 5040 tokens, max_completion_tokens 3000): la primera entró; la segunda dio 429. Groq: "Rate limit reached for model `openai/gpt-oss-120b` ... on tokens per minute (TPM): Limit 8000, Used 6236, Requested 5428. Please try again in 27.48s." Lo pedido es la entrada estimada, no la entrada más el máximo de salida.
- **openai/gpt-oss-120b**, P09 con la opción A: 400 json_validate_failed la primera vez; repetida con la misma entrada respondió bien (2940 + 1344 tokens). Intermitente: 1 de unas 31 llamadas a 120b en estas corridas.
- **openai/gpt-oss-20b**, límites de la cuenta (cabeceras de una llamada mínima): x-ratelimit-limit-tokens 8000, x-ratelimit-limit-requests 1000. El mismo tope por minuto que 120b.
- **openai/gpt-oss-20b**, P08 con k = 8 y el balde lleno (x-ratelimit-remaining-tokens 8000): 413. Groq: "Request too large for model `openai/gpt-oss-20b` ... (TPM): Limit 8000, Requested 8531". Entrada (~5530) + max_completion_tokens (3000).
- **openai/gpt-oss-20b**, P05 con k = 8 y el balde lleno: 413. Requested 8174.
- **openai/gpt-oss-20b**, P06 con k = 8: 400 json_validate_failed. Groq: "Failed to validate JSON. Please adjust your prompt." (failed_generation vacío).
- **openai/gpt-oss-20b**, P04 y P07 repetidas fuera de la corrida: respondieron bien (4031 + 2194 y 4908 + 1303 tokens). Los 400 de 20b no se repiten siempre con la misma entrada.

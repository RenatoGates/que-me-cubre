# Resultados de las 10 preguntas

Proveedor: groq · modelo: `openai/gpt-oss-120b` (plan gratuito: costo USD 0 por consulta).
Generado por `pruebas/correr_pruebas.py`. Cada salida completa (variantes de la normalización,
pasajes, respuesta cruda del modelo, citas verificadas y descartes) está en `pruebas/salidas/`.

Tokens: lo que cuenta el límite de tokens por minuto del plan gratuito (entrada + salida; la
salida incluye el razonamiento del modelo). *Normalización* es lo que costó generar la entrada
de la caché: una pregunta nueva en vivo lo gasta además de la respuesta.

*Mencionadas pero ausentes* es el bloque que calcula el código (ai/referencias.py), sin el modelo;
*No incluido* es lo que el modelo señaló y sobrevivió a la validación.

| # | Pregunta | Veredicto | ¿Aceptable? | Citas válidas / propuestas | Mencionadas pero ausentes (código) | No incluido (modelo) | Pasajes | Normalización | Respuesta: entrada | salida (razonamiento) | Consulta completa | Segundos |
|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| P01 | Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos? | con límites | sí | 3 / 3 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 5 | 1990 | 3222 | 2095 (1499) | 7307 | 5.6 |
| P02 | Me dijeron que me saque una radiografía al llegar a Lima porque allá no tenían la especialidad, ¿eso también me cubre? | con límites | sí | 2 / 2 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 6 | 2065 | 3734 | 1206 (875) | 7005 | 3.1 |
| P03 | La aerolínea perdió mi maleta en el vuelo, ¿qué me pagan? | con límites | sí | 3 / 3 | +2 remisiones | — | 5 | 1925 | 3429 | 2420 (1868) | 7774 | 5.5 |
| P04 | Tengo diabetes desde hace años; si me descompenso durante el viaje, ¿me cubren la atención? | con límites | sí | 4 / 4 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 5 | 2000 | 3330 | 2307 (1603) | 7637 | 5.3 |
| P05 | Me enfermé dos días antes de viajar y no pude subir al avión, ¿me devuelven lo que pagué? | con límites | sí | 3 / 3 | +2 remisiones | — | 5 | 1971 | 3246 | 2550 (1468) | 7767 | 6.5 |
| P06 | Se me rompió un diente comiendo durante el viaje, ¿me cubre el dentista? | con límites | sí | 2 / 3 | +2 remisiones | — | 5 | 2095 | 3347 | 2119 (1555) | 7561 | 5.0 |
| P07 | Quiero aprovechar el viaje para operarme la nariz por estética, ¿lo cubre el seguro? | no | sí | 2 / 2 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 6 | 1967 | 3652 | 1163 (866) | 6782 | 3.0 |
| P08 | Choqué el auto que alquilé durante el viaje, ¿el seguro paga la reparación? | no encontrado | sí | 0 / 0 | +2 remisiones | — | 6 | 1951 | 3694 | 445 (346) | 6090 | 1.6 |
| P09 | Me fracturé la pierna esquiando en una pista autorizada en Bariloche, ¿Pacífico me cubre? | con límites | sí | 1 / 1 | +2 remisiones | — | 6 | 2039 | 3358 | 970 (748) | 6367 | 3.0 |
| P10 | Si durante el viaje el médico me pide una radiografía, ¿Rimac la cubre? | no encontrado | **no** | 0 / 0 | +1 remisiones | — | 5 | 1997 | 3267 | 426 (323) | 5690 | 1.4 |

- Veredictos aceptables: 9 de 10.
- Citas propuestas por el modelo: 21; aceptadas tras verificar contra el pasaje y el PDF: 20.
- Tokens por respuesta (normalización desde la caché, una llamada): promedio 4998, mínimo 3693, máximo 5849.
- Tokens por consulta completa (pregunta nueva, dos llamadas): promedio 6998, máximo 7774.
- De la salida, razonamiento: 71%.
- Tiempo promedio por respuesta: 4.0 s.

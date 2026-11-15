# Resultados de las 10 preguntas

Proveedor: claude · modelo: `claude-haiku-5-5` · esfuerzo de razonamiento de la respuesta: low · precio USD 0.1 por millón de tokens de entrada y 0.5 de salida.
Generado por `pruebas/correr_pruebas.py`. Cada salida completa (variantes de la normalización,
pasajes, respuesta cruda del modelo, citas verificadas y descartes) está en `pruebas/salidas/`.

Tokens: entrada + salida (la salida incluye el razonamiento del modelo, que Claude no informa
por separado: sale 0). *Normalización* es lo que costó generar la entrada
de la caché: una pregunta nueva en vivo lo gasta además de la respuesta.

*Mencionadas pero ausentes* es el bloque que calcula el código (ai/referencias.py), sin el modelo;
*No incluido* es lo que el modelo señaló y sobrevivió a la validación.

| # | Pregunta | Veredicto | ¿Aceptable? | Citas válidas / propuestas | Mencionadas pero ausentes (código) | No incluido (modelo) | Pasajes | Normalización | Respuesta: entrada | salida (razonamiento) | Consulta completa | USD consulta completa | Segundos |
|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| P01 | Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos? | con límites | sí | 2 / 2 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 5 | 3380 | 5957 | 2271 (0) | 11608 | 0.0022 | 10.5 |
| P02 | Me dijeron que me saque una radiografía al llegar a Lima porque allá no tenían la especialidad, ¿eso también me cubre? | con límites | sí | 3 / 3 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 5 | 3420 | 6062 | 2762 (0) | 12244 | 0.0025 | 11.4 |
| P03 | La aerolínea perdió mi maleta en el vuelo, ¿qué me pagan? | con límites | sí | 5 / 5 | +2 remisiones | — | 5 | 3310 | 7351 | 1333 (0) | 11994 | 0.0019 | 5.6 |
| P04 | Tengo diabetes desde hace años; si me descompenso durante el viaje, ¿me cubren la atención? | con límites | sí | 4 / 4 | +2 remisiones | — | 7 | 3408 | 7392 | 904 (0) | 11704 | 0.0017 | 3.5 |
| P05 | Me enfermé dos días antes de viajar y no pude subir al avión, ¿me devuelven lo que pagué? | con límites | sí | 4 / 4 | +2 remisiones | — | 6 | 3423 | 7655 | 1308 (0) | 12386 | 0.0019 | 5.4 |
| P06 | Se me rompió un diente comiendo durante el viaje, ¿me cubre el dentista? | con límites | sí | 4 / 4 | +2 remisiones | — | 5 | 3333 | 6204 | 2972 (0) | 12509 | 0.0026 | 12.4 |
| P07 | Quiero aprovechar el viaje para operarme la nariz por estética, ¿lo cubre el seguro? | no | sí | 2 / 2 | +2 remisiones | — | 5 | 3323 | 7124 | 354 (0) | 10801 | 0.0014 | 2.8 |
| P08 | Choqué el auto que alquilé durante el viaje, ¿el seguro paga la reparación? | no encontrado | sí | 0 / 0 | +2 remisiones | — | 7 | 3411 | 7281 | 188 (0) | 10880 | 0.0013 | 2.2 |
| P09 | Me fracturé la pierna esquiando en una pista autorizada en Bariloche, ¿Pacífico me cubre? | no encontrado | sí | 6 / 6 | +2 remisiones | cláusulas adicionales | 6 | 3597 | 6801 | 3558 (0) | 13956 | 0.0030 | 15.3 |
| P10 | Si durante el viaje el médico me pide una radiografía, ¿Rimac la cubre? | con límites | sí | 2 / 2 | — | — | 5 | 3636 | 5705 | 580 (0) | 9921 | 0.0014 | 3.4 |

- **Veredictos aceptables al primer intento: 10 de 10.** Es el número que cuenta: la app no reintenta, así que es lo que vive el usuario.
- Con un reintento del script (solo para avanzar la corrida): 10 de 10.
- Sin texto generado al primer intento: 0 de 10.
- Citas propuestas por el modelo: 32; aceptadas tras verificar contra el pasaje y el PDF: 32.
- Tokens por respuesta (normalización desde la caché, una llamada): promedio 8376, mínimo 6285, máximo 10359.
- Tokens por consulta completa (pregunta nueva): promedio 11800, máximo 13956.
- De la salida, razonamiento: 0%.
- Costo por consulta completa (pregunta nueva): promedio USD 0.0020, máximo USD 0.0030.
- Tiempo por respuesta (sin la normalización): promedio 7.2 s, máximo 15.3 s.
- Respuestas que abren con «Sí» o «No» contra el veredicto (ahora se marcan; las salidas generadas antes de ese cambio las tienen recortadas): 0 de 10.

# Resultados de las 10 preguntas

Proveedor: claude · modelo: `claude-haiku-5-5` · esfuerzo de razonamiento de la respuesta: medium · precio USD 0.1 por millón de tokens de entrada y 0.5 de salida.
Generado por `pruebas/correr_pruebas.py`. Cada salida completa (variantes de la normalización,
pasajes, respuesta cruda del modelo, citas verificadas y descartes) está en `pruebas/salidas_medium/`.

Tokens: entrada + salida (la salida incluye el razonamiento del modelo, que Claude no informa
por separado: sale 0). *Normalización* es lo que costó generar la entrada
de la caché: una pregunta nueva en vivo lo gasta además de la respuesta.

*Mencionadas pero ausentes* es el bloque que calcula el código (ai/referencias.py), sin el modelo;
*No incluido* es lo que el modelo señaló y sobrevivió a la validación.

| # | Pregunta | Veredicto | ¿Aceptable? | Citas válidas / propuestas | Mencionadas pero ausentes (código) | No incluido (modelo) | Pasajes | Normalización | Respuesta: entrada | salida (razonamiento) | Consulta completa | USD consulta completa | Segundos |
|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| P01 | Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos? | con límites | sí | 5 / 5 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 5 | 3380 | 6832 | 4646 (0) | 14858 | 0.0035 | 19.7 |
| P02 | Me dijeron que me saque una radiografía al llegar a Lima porque allá no tenían la especialidad, ¿eso también me cubre? | con límites | sí | 6 / 6 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 6 | 3420 | 6545 | 3733 (0) | 13698 | 0.0030 | 18.9 |
| P03 | La aerolínea perdió mi maleta en el vuelo, ¿qué me pagan? | con límites | sí | 5 / 5 | +2 remisiones | — | 5 | 3310 | 7232 | 4869 (0) | 15411 | 0.0036 | 19.4 |
| P04 | Tengo diabetes desde hace años; si me descompenso durante el viaje, ¿me cubren la atención? | con límites | sí | 5 / 5 | +2 remisiones | — | 5 | 3408 | 6478 | 3661 (0) | 13547 | 0.0030 | 14.9 |
| P05 | Me enfermé dos días antes de viajar y no pude subir al avión, ¿me devuelven lo que pagué? | con límites | sí | 5 / 6 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 5 | 3423 | 7072 | 4710 (0) | 15205 | 0.0036 | 19.0 |
| P06 | Se me rompió un diente comiendo durante el viaje, ¿me cubre el dentista? | con límites | sí | 8 / 8 | +2 remisiones | — | 5 | 3333 | 6523 | 5389 (0) | 15245 | 0.0038 | 21.8 |
| P07 | Quiero aprovechar el viaje para operarme la nariz por estética, ¿lo cubre el seguro? | no | sí | 3 / 3 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 5 | 3323 | 6071 | 2712 (0) | 12106 | 0.0024 | 15.7 |
| P08 | Choqué el auto que alquilé durante el viaje, ¿el seguro paga la reparación? | no encontrado | sí | 0 / 0 | +4 remisiones | — | 6 | 3411 | 7137 | 1167 (0) | 11715 | 0.0018 | 6.7 |
| P09 | Me fracturé la pierna esquiando en una pista autorizada en Bariloche, ¿Pacífico me cubre? | no encontrado | sí | 2 / 2 | +2 remisiones | — | 6 | 3597 | 6925 | 1442 (0) | 11964 | 0.0020 | 6.6 |
| P10 | Si durante el viaje el médico me pide una radiografía, ¿Rimac la cubre? | no encontrado | **no** | 3 / 3 | +2 remisiones | — | 7 | 3636 | 6575 | 1856 (0) | 12067 | 0.0021 | 8.9 |

- **Veredictos aceptables al primer intento: 9 de 10.** Es el número que cuenta: la app no reintenta, así que es lo que vive el usuario.
- Con un reintento del script (solo para avanzar la corrida): 9 de 10.
- Sin texto generado al primer intento: 0 de 10.
- Citas propuestas por el modelo: 43; aceptadas tras verificar contra el pasaje y el PDF: 42.
- Tokens por respuesta (normalización desde la caché, una llamada): promedio 10158, mínimo 8304, máximo 12101.
- Tokens por consulta completa (pregunta nueva, dos llamadas): promedio 13582, máximo 15411.
- De la salida, razonamiento: 0%.
- Costo por consulta completa (pregunta nueva, dos llamadas): promedio USD 0.0029, máximo USD 0.0038.
- Tiempo por respuesta (sin la normalización): promedio 15.2 s, máximo 21.8 s.
- Respuestas que abren con «Sí» o «No» contra el veredicto (ahora se marcan; las salidas generadas antes de ese cambio las tienen recortadas): 0 de 10.

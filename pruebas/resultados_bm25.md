# Resultados de las 10 preguntas

Proveedor: claude · modelo: `claude-haiku-5-5` · esfuerzo de razonamiento de la respuesta: low · precio USD 0.1 por millón de tokens de entrada y 0.5 de salida.
Generado por `pruebas/correr_pruebas.py`. Cada salida completa (variantes de la normalización,
pasajes, respuesta cruda del modelo, citas verificadas y descartes) está en `pruebas/salidas_bm25/`.

Tokens: entrada + salida (la salida incluye el razonamiento del modelo, que Claude no informa
por separado: sale 0). *Normalización* es lo que costó generar la entrada
de la caché: una pregunta nueva en vivo lo gasta además de la respuesta.

*Mencionadas pero ausentes* es el bloque que calcula el código (ai/referencias.py), sin el modelo;
*No incluido* es lo que el modelo señaló y sobrevivió a la validación.

| # | Pregunta | Veredicto | ¿Aceptable? | Citas válidas / propuestas | Mencionadas pero ausentes (código) | No incluido (modelo) | Pasajes | Normalización | Respuesta: entrada | salida (razonamiento) | Consulta completa | USD consulta completa | Segundos |
|---|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| P01 | Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos? | con límites | sí | 5 / 5 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 5 | 3380 | 6836 | 3165 (0) | 13381 | 0.0028 | 12.9 |
| P02 | Me dijeron que me saque una radiografía al llegar a Lima porque allá no tenían la especialidad, ¿eso también me cubre? | con límites | sí | 5 / 5 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 6 | 3420 | 6541 | 3352 (0) | 13313 | 0.0028 | 13.8 |
| P03 | La aerolínea perdió mi maleta en el vuelo, ¿qué me pagan? | con límites | sí | 5 / 5 | +2 remisiones | cláusula G2 - Reembolso de Gastos por demora de Equipaje | 5 | 3310 | 7236 | 1474 (0) | 12020 | 0.0019 | 5.4 |
| P04 | Tengo diabetes desde hace años; si me descompenso durante el viaje, ¿me cubren la atención? | con límites | sí | 4 / 4 | +2 remisiones | — | 5 | 3408 | 6478 | 3098 (0) | 12984 | 0.0027 | 13.9 |
| P05 | Me enfermé dos días antes de viajar y no pude subir al avión, ¿me devuelven lo que pagué? | con límites | sí | 4 / 4 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 5 | 3423 | 7068 | 1440 (0) | 11931 | 0.0020 | 6.0 |
| P06 | Se me rompió un diente comiendo durante el viaje, ¿me cubre el dentista? | con límites | sí | 8 / 8 | +2 remisiones | — | 5 | 3333 | 6523 | 3901 (0) | 13757 | 0.0031 | 15.7 |
| P07 | Quiero aprovechar el viaje para operarme la nariz por estética, ¿lo cubre el seguro? | no | sí | 2 / 2 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 5 | 3323 | 6063 | 1727 (0) | 11113 | 0.0019 | 8.0 |
| P08 | Choqué el auto que alquilé durante el viaje, ¿el seguro paga la reparación? | no encontrado | sí | 1 / 1 | +4 remisiones | — | 6 | 3411 | 7137 | 393 (0) | 10941 | 0.0014 | 2.8 |
| P09 | Me fracturé la pierna esquiando en una pista autorizada en Bariloche, ¿Pacífico me cubre? | no encontrado | sí | 0 / 0 | +2 remisiones | — | 6 | 3597 | 6929 | 193 (0) | 10719 | 0.0013 | 3.4 |
| P10 | Si durante el viaje el médico me pide una radiografía, ¿Rimac la cubre? | no encontrado | **no** | 0 / 0 | +2 remisiones | — | 7 | 3636 | 6567 | 190 (0) | 10393 | 0.0013 | 1.7 |

- **Veredictos aceptables al primer intento: 9 de 10.** Es el número que cuenta: la app no reintenta, así que es lo que vive el usuario.
- Con un reintento del script (solo para avanzar la corrida): 9 de 10.
- Sin texto generado al primer intento: 0 de 10.
- Citas propuestas por el modelo: 34; aceptadas tras verificar contra el pasaje y el PDF: 34.
- Tokens por respuesta (normalización desde la caché, una llamada): promedio 8631, mínimo 6757, máximo 10424.
- Tokens por consulta completa (pregunta nueva, dos llamadas): promedio 12055, máximo 13757.
- De la salida, razonamiento: 0%.
- Costo por consulta completa (pregunta nueva, dos llamadas): promedio USD 0.0021, máximo USD 0.0031.
- Tiempo por respuesta (sin la normalización): promedio 8.4 s, máximo 15.7 s.
- Respuestas que abren con «Sí» o «No» contra el veredicto (ahora se marcan; las salidas generadas antes de ese cambio las tienen recortadas): 0 de 10.

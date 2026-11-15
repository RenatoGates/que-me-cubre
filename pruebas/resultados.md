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
| P01 | Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos? | con límites | sí | 3 / 3 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 5 | — | 5910 | 1034 (0) | 6944 | 0.0011 | 4.1 |
| P02 | Me dijeron que me saque una radiografía al llegar a Lima porque allá no tenían la especialidad, ¿eso también me cubre? | con límites | sí | 3 / 3 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 5 | — | 6005 | 2467 (0) | 8472 | 0.0018 | 11.1 |
| P03 | La aerolínea perdió mi maleta en el vuelo, ¿qué me pagan? | con límites | sí | 8 / 8 | +2 remisiones | cláusula G2 - Reembolso de Gastos por demora de Equipaje | 5 | — | 7329 | 1987 (0) | 9316 | 0.0017 | 7.5 |
| P04 | Tengo diabetes desde hace años; si me descompenso durante el viaje, ¿me cubren la atención? | con límites | sí | 4 / 4 | +2 remisiones | — | 7 | — | 7348 | 3504 (0) | 10852 | 0.0025 | 13.8 |
| P05 | Me enfermé dos días antes de viajar y no pude subir al avión, ¿me devuelven lo que pagué? | con límites | sí | 4 / 4 | +2 remisiones | — | 6 | — | 7608 | 3517 (0) | 11125 | 0.0025 | 14.1 |
| P06 | Se me rompió un diente comiendo durante el viaje, ¿me cubre el dentista? | con límites | sí | 5 / 5 | +2 remisiones | — | 5 | — | 6184 | 1048 (0) | 7232 | 0.0011 | 4.3 |
| P07 | Quiero aprovechar el viaje para operarme la nariz por estética, ¿lo cubre el seguro? | no | sí | 3 / 3 | +2 remisiones | — | 5 | — | 7110 | 1612 (0) | 8722 | 0.0015 | 8.1 |
| P08 | Choqué el auto que alquilé durante el viaje, ¿el seguro paga la reparación? | no encontrado | sí | 0 / 0 | +2 remisiones | — | 7 | — | 7261 | 188 (0) | 7449 | 0.0008 | 1.4 |
| P09 | Me fracturé la pierna esquiando en una pista autorizada en Bariloche, ¿Pacífico me cubre? | no encontrado | sí | 3 / 3 | +2 remisiones | — | 6 | — | 6744 | 2924 (0) | 9668 | 0.0021 | 13.5 |
| P10 | Si durante el viaje el médico me pide una radiografía, ¿Rimac la cubre? | con límites | sí | 2 / 2 | — | — | 5 | — | 5678 | 584 (0) | 6262 | 0.0009 | 2.6 |

- **Veredictos aceptables al primer intento: 10 de 10.** Es el número que cuenta: la app no reintenta, así que es lo que vive el usuario.
- Con un reintento del script (solo para avanzar la corrida): 10 de 10.
- Sin texto generado al primer intento: 0 de 10.
- Citas propuestas por el modelo: 35; aceptadas tras verificar contra el pasaje y el PDF: 35.
- Tokens por respuesta (normalización desde la caché, una llamada): promedio 8604, mínimo 6262, máximo 11125.
- Tokens por consulta completa (pregunta nueva): promedio 8604, máximo 11125.
- De la salida, razonamiento: 0%.
- Costo por consulta completa (pregunta nueva): promedio USD 0.0016, máximo USD 0.0025.
- Tiempo por respuesta (sin la normalización): promedio 8.0 s, máximo 14.1 s.
- Respuestas que abren con «Sí» o «No» contra el veredicto (ahora se marcan; las salidas generadas antes de ese cambio las tienen recortadas): 0 de 10.

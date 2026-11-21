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
| P01 | Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos? | sí | sí | 4 / 4 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 5 | — | 6881 | 1207 (0) | 8088 | 0.0013 | 5.5 |
| P02 | Me dijeron que me saque una radiografía al llegar a Lima porque allá no tenían la especialidad, ¿eso también me cubre? | sí | sí | 2 / 2 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 5 | — | 6992 | 997 (0) | 7989 | 0.0012 | 4.8 |
| P03 | La aerolínea perdió mi maleta en el vuelo, ¿qué me pagan? | sí | sí | 4 / 4 | +2 remisiones | cláusula G2 - Reembolso de Gastos por demora de Equipaje | 5 | — | 8300 | 1400 (0) | 9700 | 0.0015 | 5.7 |
| P04 | Tengo diabetes desde hace años; si me descompenso durante el viaje, ¿me cubren la atención? | sí | sí | 2 / 2 | +2 remisiones | — | 7 | — | 8323 | 3362 (0) | 11685 | 0.0025 | 13.8 |
| P05 | Me enfermé dos días antes de viajar y no pude subir al avión, ¿me devuelven lo que pagué? | sí | sí | 3 / 3 | +2 remisiones | — | 6 | — | 8595 | 3954 (0) | 12549 | 0.0028 | 15.8 |
| P06 | Se me rompió un diente comiendo durante el viaje, ¿me cubre el dentista? | sí | sí | 5 / 5 | +2 remisiones | — | 5 | — | 7155 | 1487 (0) | 8642 | 0.0015 | 6.3 |
| P07 | Quiero aprovechar el viaje para operarme la nariz por estética, ¿lo cubre el seguro? | no | sí | 2 / 2 | +2 remisiones | — | 5 | — | 8077 | 513 (0) | 8590 | 0.0011 | 3.1 |
| P08 | Choqué el auto que alquilé durante el viaje, ¿el seguro paga la reparación? | no encontrado | sí | 1 / 1 | +2 remisiones | — | 7 | — | 8232 | 417 (0) | 8649 | 0.0010 | 2.8 |
| P09 | Me fracturé la pierna esquiando en una pista autorizada en Bariloche, ¿Pacífico me cubre? | no encontrado | sí | 2 / 2 | +2 remisiones | — | 6 | — | 7727 | 691 (0) | 8418 | 0.0011 | 3.7 |
| P10 | Si durante el viaje el médico me pide una radiografía, ¿Rimac la cubre? | sí | sí | 2 / 2 | — | — | 5 | — | 6669 | 685 (0) | 7354 | 0.0010 | 3.7 |

- **Veredictos aceptables al primer intento: 10 de 10.** Es el número que cuenta: la app no reintenta, así que es lo que vive el usuario.
- Con un reintento del script (solo para avanzar la corrida): 10 de 10.
- Sin texto generado al primer intento: 0 de 10.
- Citas propuestas por el modelo: 27; aceptadas tras verificar contra el pasaje y el PDF: 27.
- Tokens por respuesta (normalización desde la caché, una llamada): promedio 9166, mínimo 7354, máximo 12549.
- Tokens por consulta completa (pregunta nueva): promedio 9166, máximo 12549.
- De la salida, razonamiento: 0%.
- Costo por consulta completa (pregunta nueva): promedio USD 0.0015, máximo USD 0.0028.
- Tiempo por respuesta (sin la normalización): promedio 6.5 s, máximo 15.8 s.
- Respuestas que abren con «Sí» o «No» contra el veredicto (ahora se marcan; las salidas generadas antes de ese cambio las tienen recortadas): 0 de 10.

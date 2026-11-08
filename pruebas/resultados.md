# Resultados de las 10 preguntas

Proveedor: groq · modelo: `openai/gpt-oss-120b` (plan gratuito: costo USD 0 por consulta).
Generado por `pruebas/correr_pruebas.py`. Cada salida completa (variantes de la normalización,
pasajes, respuesta cruda del modelo, citas verificadas y descartes) está en `pruebas/salidas/`.

Tokens: lo que cuenta el límite de tokens por minuto del plan gratuito (entrada + salida; la
salida incluye el razonamiento del modelo). *Normalización* es lo que costó generar la entrada
de la caché: una pregunta nueva en vivo lo gasta además de la respuesta.

| # | Pregunta | Veredicto | ¿Aceptable? | Citas válidas / propuestas | No incluido en el documento | Pasajes | Normalización | Respuesta: entrada | salida (razonamiento) | Consulta completa | Segundos |
|---|---|---|---|---|---|---:|---:|---:|---:|---:|---:|
| P01 | Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos? | no encontrado | **no** | 2 / 2 | Condiciones Particulares y/o Certificado de Seguro | 11 | 919 | 5076 | 1733 (1388) | 7728 | 4.5 |
| P02 | Me dijeron que me saque una radiografía al llegar a Lima porque allá no tenían la especialidad, ¿eso también me cubre? | con límites | **no** | 2 / 3 | — | 11 | 986 | 4940 | 2125 (1671) | 8051 | 6.0 |
| P03 | La aerolínea perdió mi maleta en el vuelo, ¿qué me pagan? | no encontrado | **no** | 0 / 2 | — | 10 | 985 | 4779 | 1925 (1167) | 7689 | 4.7 |
| P04 | Tengo diabetes desde hace años; si me descompenso durante el viaje, ¿me cubren la atención? | con límites | sí | 4 / 4 | Condiciones Particulares y/o Certificado de Seguro | 8 | 1013 | 4031 | 1801 (1098) | 6845 | 4.6 |
| P05 | Me enfermé dos días antes de viajar y no pude subir al avión, ¿me devuelven lo que pagué? | con límites | sí | 1 / 2 | — | 12 | 916 | 5194 | 2227 (1381) | 8337 | 5.6 |
| P06 | Se me rompió un diente comiendo durante el viaje, ¿me cubre el dentista? | con límites | sí | 3 / 3 | Condiciones Particulares; Certificado de Seguro | 10 | 931 | 4941 | 2401 (1861) | 8273 | 5.8 |
| P07 | Quiero aprovechar el viaje para operarme la nariz por estética, ¿lo cubre el seguro? | no | sí | 2 / 2 | — | 11 | 921 | 4908 | 1344 (1001) | 7173 | 3.4 |
| P08 | Choqué el auto que alquilé durante el viaje, ¿el seguro paga la reparación? | no encontrado | sí | 0 / 0 | — | 12 | 984 | 5551 | 463 (360) | 6998 | 1.6 |
| P09 | Me fracturé la pierna esquiando en una pista autorizada en Bariloche, ¿Pacífico me cubre? | no | **no** | 2 / 2 | Condiciones Particulares | 11 | 1022 | 4538 | 2218 (1635) | 7778 | 5.5 |
| P10 | Si durante el viaje el médico me pide una radiografía, ¿Rimac la cubre? | con límites | sí | 3 / 3 | — | 9 | 910 | 3738 | 1893 (1331) | 6541 | 4.5 |

- Veredictos aceptables: 6 de 10.
- Citas propuestas por el modelo: 23; aceptadas tras verificar contra el pasaje y el PDF: 19.
- Tokens por respuesta (normalización desde la caché, una llamada): promedio 6583, mínimo 5631, máximo 7421.
- Tokens por consulta completa (pregunta nueva, dos llamadas): promedio 7541, máximo 8337.
- De la salida, razonamiento: 71%.
- Tiempo promedio por respuesta: 4.6 s.

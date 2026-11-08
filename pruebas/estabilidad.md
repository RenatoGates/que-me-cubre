# Estabilidad de la respuesta: la misma pregunta varias veces

Generado por `pruebas/medir_estabilidad.py`. Misma normalización (caché), mismos pasajes
y mismo mensaje al modelo en cada intento; lo que cambia es lo que el modelo genera.
Sin reintentos: cada intento es lo que vería el usuario en la app (que no reintenta).
*Aceptable* es el criterio de `pruebas/preguntas.json`, fijado antes de correr nada. Desde el
bloque determinista, la referencia ausente exigida puede venir del bloque (lo pone el código) o
de "no incluido" (lo pone el modelo); las columnas las separan.

La serie anterior de P02, sin el bloque determinista (0 de 5: el modelo nunca mencionó B4), está
en `pruebas/estabilidad/sin_bloque/`. En esa serie un intento más cayó en la red de seguridad y
el script de entonces abortó sin guardarlo y lo rehízo: al primer intento fueron 6 llamadas, 1 sin
texto (tipo de falla no registrado).

## P02: Me dijeron que me saque una radiografía al llegar a Lima porque allá no tenían la especialidad, ¿eso también me cubre?

- Aceptables: **3 de 5**
- Pasajes enviados al modelo: idénticos en todos los intentos
- Respuestas distintas: 5 de 5
- «B4» en el bloque determinista: **5 de 5**; en "no incluido" del modelo: 0 de 5
- Qué debería pasar: No contestar sí o no a la ligera: citar que los gastos cubiertos son los ocurridos durante el viaje y que la protección termina en la fecha de llegada, y avisar que la póliza menciona 'B4 - Continuación de Tratamiento en País de Residencia' pero el texto de esa cláusula no está en el documento: hay que pedírsela a la aseguradora.

| Intento | Veredicto | ¿Aceptable? | Citas válidas / propuestas | Signo final ignorado | Mencionadas pero ausentes (código) | No incluido (modelo) | Podrían aplicar | Oraciones recortadas | Apertura contra el veredicto | Tokens |
|---:|---|---|---:|---:|---|---|---:|---:|---|---:|
| 1 | no | **no** | 2 / 2 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 1 | 0 | — | 5207 |
| 2 | con límites | sí | 3 / 3 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 1 | 1 | — | 4979 |
| 3 | con límites | sí | 3 / 3 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 0 | 0 | — | 5571 |
| 4 | con límites | sí | 3 / 3 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 1 | 0 | — | 6165 |
| 5 | no | **no** | 3 / 3 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 0 | 0 | — | 5573 |

Respuestas:

1. Tu póliza no cubre la radiografía que te han indicado en Lima porque las radiografías están excluidas cuando son exámenes de rutina sin indicación objetiva. Además, la cobertura solo se aplica a tratamientos de urgencia de cuadros agudos. Por lo tanto, este examen no está incluido en la cobertura.
2. Tu póliza cubre una radiografía si es parte de un tratamiento de urgencia por una enfermedad o accidente súbito que impida continuar el viaje, pero no cubre exámenes de rutina sin una indicación objetiva.
3. Tu póliza cubre una radiografía solo si es parte de un tratamiento de urgencia por una enfermedad o accidente súbito, según lo indicado por un médico. Si la radiografía se considera un examen de rutina sin una indicación objetiva, está excluida. Por lo tanto, la cobertura depende de que la radiografía cumpla con esos requisitos.
4. Tu póliza cubre la radiografía si es parte de un diagnóstico y tratamiento de urgencia por una lesión o enfermedad súbita y aguda que impida continuar el viaje, siempre que no sea por una condición preexistente. El reembolso está limitado al máximo que figure en las Condiciones Particulares o en el Certificado de Seguro, documento que no está incluido aquí.
5. Tu póliza solo cubre exámenes de diagnóstico cuando forman parte de un tratamiento de urgencia para una enfermedad o accidente súbito y agudo que impida la continuación normal del viaje. Las radiografías que se solicitan como rutina, sin una indicación objetiva clara, están excluidas. Por tanto, si la radiografía en Lima no es parte de una urgencia médica, no estaría cubierta.

## P01: Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos?

- Aceptables: **5 de 5**
- Pasajes enviados al modelo: idénticos en todos los intentos
- Respuestas distintas: 5 de 5
- Qué debería pasar: Mostrar la cobertura de gastos médicos por accidente durante el viaje (Art. 3°) y sus límites: monto fijado en las Condiciones Particulares, contingencias a más de 200 km del domicilio, y el trámite de reembolso cuando no se llamó a la Central de Asistencia.

| Intento | Veredicto | ¿Aceptable? | Citas válidas / propuestas | Signo final ignorado | Mencionadas pero ausentes (código) | No incluido (modelo) | Podrían aplicar | Oraciones recortadas | Apertura contra el veredicto | Tokens |
|---:|---|---|---:|---:|---|---|---:|---:|---|---:|
| 1 | con límites | sí | 3 / 3 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 1 | 1 | «Sí» (recortada) | 5608 |
| 2 | con límites | sí | 3 / 3 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 1 | 0 | — | 5572 |
| 3 | con límites | sí | 2 / 2 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 0 | 0 | — | 4761 |
| 4 | con límites | sí | 3 / 3 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 1 | 0 | — | 5249 |
| 5 | con límites | sí | 3 / 3 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 1 | 1 | «Sí» (recortada) | 5323 |

Respuestas:

1. El pago está limitado al monto máximo que figura en tus Condiciones Particulares o en el Certificado de Seguro, documento que deberías consultar. Recuerda que solo se cubre el tratamiento de emergencia; si la lesión fuera una condición preexistente, solo se pagaría la estabilización.
2. Tu póliza cubre los gastos médicos por un accidente como la torcedura del dedo, siempre que el tratamiento sea de urgencia y se realice durante el viaje. El reembolso está limitado al monto máximo que figura en las Condiciones Particulares o en el Certificado de Seguro, que no aparece en este documento. Si la lesión se considerara una condición médica preexistente, solo se cubriría el tratamiento de emergencia y estabilización.
3. Tu póliza cubre los gastos médicos por la torcedura del dedo, siempre que sea un tratamiento de urgencia por una lesión súbita y aguda. El pago está limitado al monto máximo que aparece en las Condiciones Particulares o en el Certificado de Seguro, documentos que debes revisar para conocer el límite exacto.
4. Tu póliza cubre los gastos médicos por el accidente de torcerte el dedo, siempre que sea un tratamiento de urgencia y dentro del límite máximo que figura en las Condiciones Particulares o en el Certificado de Seguro, cuyo monto no aparece en este documento.
5. El monto máximo no está especificado en este documento, así que deberías revisar ese documento para conocer el límite exacto. Además, si la lesión fuera considerada una condición preexistente, la cobertura se limitaría al tratamiento de emergencia y estabilización.


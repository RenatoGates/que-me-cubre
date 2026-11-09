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

La serie anterior con el bloque, con el mismo prompt y el tope de 3000 tokens (P02 en el commit
a80fb90, P01 en 039314c), está en `pruebas/estabilidad/039314c/`: P02 aceptables 3 de 5 y B4 en el
bloque 5 de 5; P01 aceptables 5 de 5. La de abajo es con el tope de 3000 subido a 3800.

## P01: Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos?

- Aceptables: **5 de 5**
- Pasajes enviados al modelo: idénticos en todos los intentos
- Respuestas distintas: 5 de 5
- Qué debería pasar: Mostrar la cobertura de gastos médicos por accidente durante el viaje (Art. 3°) y sus límites: monto fijado en las Condiciones Particulares, contingencias a más de 200 km del domicilio, y el trámite de reembolso cuando no se llamó a la Central de Asistencia.

| Intento | Veredicto | ¿Aceptable? | Citas válidas / propuestas | Signo final ignorado | Mencionadas pero ausentes (código) | No incluido (modelo) | Podrían aplicar | Oraciones recortadas | Apertura contra el veredicto | Tokens |
|---:|---|---|---:|---:|---|---|---:|---:|---|---:|
| 1 | con límites | sí | 4 / 4 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 1 | 0 | — | 6372 |
| 2 | con límites | sí | 3 / 3 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 1 | 0 | — | 5821 |
| 3 | con límites | sí | 3 / 3 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 1 | 0 | — | 5595 |
| 4 | con límites | sí | 3 / 3 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 1 | 0 | — | 4931 |
| 5 | con límites | sí | 3 / 3 | 1 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 1 | 0 | — | 5444 |

Respuestas:

1. Tu póliza cubre los gastos médicos por el dedo torcido, siempre que sea un accidente súbito y se trate como una urgencia, pero el pago está limitado al monto máximo que aparece en tus Condiciones Particulares o en el Certificado de Seguro y a un límite combinado de todas las coberturas médicas. Si la lesión está vinculada a una condición preexistente, solo se cubriría el tratamiento de emergencia. Necesitarás consultar tus Condiciones Particulares o el Certificado de Seguro para conocer el límite exacto.
2. Tu póliza cubre los gastos médicos por la torcedura del dedo, siempre que sea un tratamiento de urgencia por un accidente súbito. El reembolso está limitado al monto máximo que figura en las Condiciones Particulares o en el Certificado de Seguro, que no aparecen en este documento. Si la lesión estuviera relacionada con una condición médica preexistente, solo se cubriría la emergencia y estabilización.
3. Tu póliza cubre los gastos médicos por el accidente que describiste, siempre que sea un tratamiento de urgencia y dentro del límite máximo que figura en las Condiciones Particulares o en el Certificado de Seguro. El monto exacto del límite no está especificado en este documento, por lo que deberías consultarlo en esas piezas.
4. Tu póliza cubre los gastos médicos por el accidente de torcerte el dedo, siempre que el tratamiento sea de urgencia y esté dentro del límite establecido en tus Condiciones Particulares o Certificado de Seguro. El reembolso está limitado al monto que figura en esos documentos, que no se incluye en este resumen. Si la lesión fuera una condición preexistente, solo se cubriría la emergencia y estabilización.
5. Tu póliza cubre los gastos médicos por una torcedura del dedo si se considera un accidente de carácter súbito, siempre que el tratamiento sea de urgencia. El reembolso está limitado al monto máximo que figura en tus Condiciones Particulares o en el Certificado de Seguro, y los gastos de las coberturas B1‑B4 se suman sin superar ese límite. Si la lesión fuera una condición preexistente, sólo se cubrirían los gastos de emergencia y estabilización.

## P02: Me dijeron que me saque una radiografía al llegar a Lima porque allá no tenían la especialidad, ¿eso también me cubre?

- Aceptables: **4 de 5**
- Pasajes enviados al modelo: idénticos en todos los intentos
- Respuestas distintas: 5 de 5
- «B4» en el bloque determinista: **5 de 5**; en "no incluido" del modelo: 0 de 5
- Qué debería pasar: No contestar sí o no a la ligera: citar que los gastos cubiertos son los ocurridos durante el viaje y que la protección termina en la fecha de llegada, y avisar que la póliza menciona 'B4 - Continuación de Tratamiento en País de Residencia' pero el texto de esa cláusula no está en el documento: hay que pedírsela a la aseguradora.

| Intento | Veredicto | ¿Aceptable? | Citas válidas / propuestas | Signo final ignorado | Mencionadas pero ausentes (código) | No incluido (modelo) | Podrían aplicar | Oraciones recortadas | Apertura contra el veredicto | Tokens |
|---:|---|---|---:|---:|---|---|---:|---:|---|---:|
| 1 | con límites | sí | 2 / 3 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 0 | 1 | — | 5114 |
| 2 | no | **no** | 1 / 1 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 0 | 0 | — | 4729 |
| 3 | con límites | sí | 3 / 3 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 0 | 0 | — | 5426 |
| 4 | con límites | sí | 4 / 4 | 1 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 0 | 0 | — | 5667 |
| 5 | con límites | sí | 3 / 3 | 0 | B4 - Continuación de Tratamiento en País de Residencia; +2 remisiones | — | 0 | 1 | — | 5839 |

Respuestas:

1. Tu póliza cubre exámenes diagnósticos como una radiografía si forman parte de un tratamiento de urgencia por una enfermedad o accidente súbito que impida continuar el viaje, pero no cubre radiografías de rutina sin indicación objetiva.
2. Tu póliza excluye las radiografías que se consideren exámenes de rutina sin indicación objetiva. Por eso, el hecho de que te pidan una radiografía al llegar a Lima no está cubierto según lo indicado en la póliza.
3. Tu póliza cubre radiografías cuando forman parte de un tratamiento de urgencia de una condición súbita y están justificadas por un médico. Sin embargo, las radiografías de rutina sin indicación objetiva están excluidas. Por lo tanto, la cobertura depende de que la radiografía sea necesaria para tu diagnóstico y no sea un examen rutinario.
4. Tu póliza cubre exámenes diagnósticos como la radiografía cuando forman parte de un tratamiento de urgencia por una lesión o enfermedad súbita, pero excluye radiografías de rutina sin indicación objetiva. La cobertura está sujeta al límite que figura en las Condiciones Particulares y/o Certificado de Seguro, documento que no está incluido aquí. Podrían existir otras exclusiones según tu caso.
5. Tu póliza cubre la radiografía si es parte de un tratamiento de urgencia para una condición súbita y necesaria para diagnosticar y poder continuar el viaje. Los gastos médicos están limitados a tratamientos de urgencia de cuadros agudos (cita 1) y los exámenes diagnósticos están incluidos (cita 2), pero los exámenes de rutina sin indicación objetiva, incluidas radiografías, están excluidos (cita 3).


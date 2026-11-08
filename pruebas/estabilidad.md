# Estabilidad de la respuesta: la misma pregunta varias veces

Generado por `pruebas/medir_estabilidad.py`. Misma normalización (caché), mismos pasajes
y mismo mensaje al modelo en cada intento; lo que cambia es lo que el modelo genera.
*Aceptable* es el criterio de `pruebas/preguntas.json`, fijado antes de correr nada.

## P02: Me dijeron que me saque una radiografía al llegar a Lima porque allá no tenían la especialidad, ¿eso también me cubre?

- Aceptables: **0 de 5**
- Pasajes enviados al modelo: idénticos en todos los intentos
- Respuestas distintas: 5 de 5
- Qué debería pasar: No contestar sí o no a la ligera: citar que los gastos cubiertos son los ocurridos durante el viaje y que la protección termina en la fecha de llegada, y avisar que la póliza menciona 'B4 - Continuación de Tratamiento en País de Residencia' pero el texto de esa cláusula no está en el documento: hay que pedírsela a la aseguradora.

| Intento | Veredicto | ¿Aceptable? | Citas válidas / propuestas | Signo final ignorado | No incluido | Podrían aplicar | Oraciones recortadas | Tokens |
|---:|---|---|---:|---:|---|---:|---:|---:|
| 1 | con límites | **no** | 4 / 4 | 0 | Condiciones Particulares y/o Certificado de Seguro | 1 | 0 | 5899 |
| 2 | con límites | **no** | 2 / 3 | 0 | — | 0 | 0 | 5809 |
| 3 | con límites | **no** | 3 / 3 | 0 | — | 1 | 0 | 4995 |
| 4 | con límites | **no** | 2 / 3 | 0 | — | 1 | 0 | 5730 |
| 5 | con límites | **no** | 3 / 3 | 0 | — | 1 | 1 | 5698 |

Respuestas:

1. Tu póliza cubre los exámenes diagnósticos, como una radiografía, siempre que formen parte de un tratamiento de urgencia por una enfermedad o accidente súbito que impida continuar el viaje normalmente. El pago está limitado al monto máximo que figura en las Condiciones Particulares o en el Certificado de Seguro, documentos que no aparecen aquí. Además, si la razón de la radiografía fuera una condición preexistente, esa cobertura podría quedar excluida.
2. Tu póliza cubre la radiografía si forma parte de un tratamiento de urgencia por un cuadro súbito que impida continuar el viaje. Los gastos médicos están limitados a tratamientos de urgencia de cuadros agudos y los exámenes de diagnóstico como la radiografía están incluidos. Sin embargo, la radiografía no se cubre si es un examen de rutina sin indicación objetiva.
3. Tu póliza cubre la radiografía como examen diagnóstico, siempre que forme parte de un tratamiento de urgencia por un accidente o enfermedad súbita. La cobertura está limitada a estos casos de cuadro agudo y no se extiende a exámenes de rutina sin indicación objetiva.
4. Tu póliza cubre exámenes diagnósticos como la radiografía siempre que formen parte de un tratamiento de urgencia por una condición súbita y aguda que impida la continuación normal del viaje. La cobertura está limitada a estos casos de urgencia y no a procedimientos de larga duración. Si la radiografía se solicita por una condición que ya tenías antes del viaje, podría quedar excluida.
5. Sí, la radiografía está cubierta siempre que sea parte de un tratamiento de urgencia por una condición súbita y aguda y se realice dentro del territorio de la póliza. Si la radiografía fuera un examen de rutina sin indicación médica, podría quedar excluida.


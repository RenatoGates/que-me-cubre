# Veredictos antes y después

Generado por `pruebas/medir_veredictos.py`. Antes: el prompt anterior. Después: «con límites» exige un límite
concreto escrito en una cita (si el modelo no lo da, el código lo pasa a «cubre»), y cada respuesta trae un
razonamiento corto. Claude Haiku, primer intento.

| Veredicto | Antes | Después, corrida 1 | Después, corrida 2 |
|---|---:|---:|---:|
| Cubre | 0 | 6 | 7 |
| Cubre con límites | 7 | 0 | 0 |
| No cubre | 1 | 1 | 1 |
| No está en tu póliza | 2 | 3 | 2 |

- «Con límites» después: **0 y 0 de 10**.
- Veredictos que el código tuvo que pasar de «con límites» a «cubre» por no traer límite citado: 3.

| # | Antes | Corrida 1 | Corrida 2 | Límite concreto (corrida 2) | Razonamiento (corrida 2) |
|---|---|---|---|---|---|
| P01 | Cubre con límites | Cubre | Cubre | — | Torcerte el dedo en el viaje es un accidente durante el viaje, y la cobertura de gastos médicos por accidente cubre la atención de urgencia que impida continuar el viaje. No encuentro en los pasajes que el esguince de dedo sea específicamente un caso cubierto, así que depende de si la atención recibida fue de urgencia y de si te impidió seguir el viaje; el monto depende de otro documento. |
| P02 | Cubre con límites | Cubre | Cubre | — | Tu radiografía sería un examen de diagnóstico ordenado durante el viaje, y la cobertura de gastos médicos incluye exámenes de diagnóstico, pero solo si se hace por un accidente o enfermedad de carácter súbito. Los pasajes no dicen nada sobre el lugar específico ni sobre si la radiografía fue ordenada por un médico, así que queda incierto; además, el monto depende de otro documento. |
| P03 | Cubre con límites | Cubre | Cubre | — | Tu maleta perdida por la aerolínea entra en la cobertura de extravío de equipaje, que paga según el peso y hasta el monto declarado en el informe de pérdida. La cifra máxima no está en este documento, así que no puedo decir cuánto te pagarían. |
| P04 | Cubre con límites | Cubre | Cubre | — | Tu diabetes desde hace años y una descompensación durante el viaje se podrían tratar como una enfermedad aguda cubierta por gastos médicos durante el viaje, pero los pasajes no mencionan la diabetes ni las descompensaciones. La cobertura solo alcanza tratamientos de urgencia de cuadros agudos que impidan seguir el viaje, y no procedimientos de larga duración, así que el resultado depende de cómo se presente tu caso. |
| P05 | Cubre con límites | No está en tu póliza | Cubre | — | Como una enfermedad súbita te impidió iniciar el viaje, la póliza contempla el reembolso de gastos de viaje por la cobertura de cancelación, siempre que los hayas reservado y pagado o debas antes de enfermarte. La primera frase de esa cobertura menciona solo la muerte del asegurado, lo que la vuelve algo confusa, pero la frase siguiente describe expresamente el caso de impedimento por enfermedad. |
| P06 | Cubre con límites | Cubre | Cubre | — | Como el diente se rompió comiendo durante el viaje, no es claro que sea un accidente de los que describe la cobertura de emergencia odontológica; el pasaje cubre tratamiento de emergencia pero excluye el tratamiento dental salvo lesiones en dientes naturales sanos por accidente, así que depende de si la rotura fue un accidente y de los antecedentes médicos. |
| P07 | No cubre | No cubre | No cubre | — | Una operación de nariz por estética es un tratamiento estético y una cirugía plástica electiva, y ambas están excluidas en la cobertura de gastos médicos durante el viaje. La única excepción que mencionan los pasajes es que la cirugía sea consecuencia de una lesión accidental, lo que no es tu caso según lo que contaste. |
| P08 | No está en tu póliza | No está en tu póliza | No está en tu póliza | — | Revisé si algún pasaje trataba un choque con otras palabras y no encontré ninguno. |
| P09 | No está en tu póliza | No está en tu póliza | No está en tu póliza | — | Esquiar en una pista reglamentaria y autorizada no entra en la exclusión de esquí fuera de pistas, por lo que el caso no queda excluido por esa cláusula. Los pasajes revisados no describen una cobertura específica para fracturas, así que no puedo confirmar el monto ni el procedimiento de atención para tu caso. |
| P10 | Cubre con límites | Cubre | Cubre | — | Una radiografía es un examen de ayuda al diagnóstico que el texto expresamente incluye como gasto cubierto por enfermedad o accidente, siempre que la indique el Departamento Médico de la Central de Asistencia. El pasaje no dice que la cobertura se limite a un monto ni que dependa de si el viaje es fuera del país, pero tampoco aclara si la orden de tu médico del viaje cuenta como indicación del Departamento Médico, por eso conviene confirmarlo con la central. |

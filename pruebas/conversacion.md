# Memoria de la conversación

Generado por `pruebas/medir_conversacion.py` con Claude Haiku. La app manda como máximo 3 turnos
anteriores (pregunta, veredicto y razonamiento de cada uno).

| Consulta | Veredicto | ¿Habla del tobillo? | Tokens de entrada | Costo USD | Razonamiento |
|---|---|---|---:|---:|---|
| Primera pregunta | Cubre | sí | 7962 | 0.00147 | Tu tobillo doblado al caminar en Cusco durante el viaje es un accidente durante el viaje, y la cobertura de gastos médicos por accidente o enfermedad durante el viaje lo cubre si el médico lo trata como urgencia de un cuadro agudo que impida seguir el viaje. El monto exacto no aparece en los pasajes, así que no puedo confirmar cuánto se reembolsa. |
| Segunda, sin conversación previa | Cubre | no | 8019 | 0.00310 | Dices que te accidentaste bajando de un bus turístico; asumiendo que fue durante tu viaje, los pasajes contemplan el reembolso de gastos médicos por un accidente. No dicen cuánto se paga ni confirman las fechas de tu viaje, que están en otro documento. |
| Segunda, con la conversación previa | Cubre | sí | 7664 | 0.00140 | Tu caída al bajar del bus turístico durante el viaje es un accidente durante el viaje, que entra en la cobertura de gastos médicos por accidente o enfermedad durante el viaje, siempre que el médico lo trate como urgencia de un cuadro agudo que impida seguir el viaje. Como antes contaste tu tobillo doblado en Cusco, el accidente del bus se suma a ese hecho y el monto exacto sigue sin aparecer en los pasajes. |

Costo del contexto, aislado (misma consulta y mismos pasajes, tokens contados por Anthropic):

| Turnos previos | Tokens de entrada | Más que sin contexto | USD más por consulta |
|---:|---:|---:|---:|
| 0 | 6241 | — | — |
| 1 | 6460 | 219 | 0.000022 |
| 3 | 6858 | 617 | 0.000062 |

- Con 3 turnos, la consulta cuesta USD 0.000062 más: 4.4% de lo que costó la consulta con conversación (USD 0.00140).

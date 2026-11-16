# Funciones de la Fase 2, medidas

Generado por `pruebas/medir_fase2.py` con `claude-haiku-5-5`. Una corrida por caso.

## Repregunta y varias preguntas (triage)

- Preguntas vagas en las que repregunta en vez de responder: **6 de 6**.
- Preguntas claras que deja pasar sin repreguntar ni partir: **14 de 14**.
- Textos con varias preguntas separados en el número esperado: **5 de 5**.
- Costo del paso: USD 0.00013 en promedio; tiempo: 1.5 s en promedio, 2.5 s el más largo.

| Grupo | Texto | ¿Repregunta? | Preguntas | ¿Como se esperaba? |
|---|---|---|---:|---|
| vaga | Me lesioné, ¿qué puedo hacer? | sí | 1 | sí |
| vaga | Tuve un problema en el viaje, ¿me cubre? | sí | 1 | sí |
| vaga | ¿Me cubre? | sí | 1 | sí |
| vaga | Me pasó algo ayer y no sé si el seguro responde. | sí | 1 | sí |
| vaga | Necesito usar mi seguro, ¿cómo hago? | sí | 1 | sí |
| vaga | Tuve un accidente. | sí | 1 | sí |
| clara | Me caí de la moto en Cusco y me fracturé la muñeca, ¿me cubre la operación? | no | 1 | sí |
| clara | ¿Qué exclusiones tiene mi póliza? | no | 1 | sí |
| clara | Me robaron el celular en el aeropuerto de Lima, ¿lo cubre? | no | 1 | sí |
| clara | ¿A qué número llamo si necesito un médico durante el viaje? | no | 1 | sí |
| clara | Me torcí el dedo en Tarapoto y fui a un centro médico, ¿me cubre los gastos? | no | 1 | sí |
| clara | Me dijeron que me saque una radiografía al llegar a Lima porque allá no tenían la especialidad, ¿eso también me cubre? | no | 1 | sí |
| clara | La aerolínea perdió mi maleta en el vuelo, ¿qué me pagan? | no | 1 | sí |
| clara | Tengo diabetes desde hace años; si me descompenso durante el viaje, ¿me cubren la atención? | no | 1 | sí |
| clara | Me enfermé dos días antes de viajar y no pude subir al avión, ¿me devuelven lo que pagué? | no | 1 | sí |
| clara | Se me rompió un diente comiendo durante el viaje, ¿me cubre el dentista? | no | 1 | sí |
| clara | Quiero aprovechar el viaje para operarme la nariz por estética, ¿lo cubre el seguro? | no | 1 | sí |
| clara | Choqué el auto que alquilé durante el viaje, ¿el seguro paga la reparación? | no | 1 | sí |
| clara | Me fracturé la pierna esquiando en una pista autorizada en Bariloche, ¿Pacífico me cubre? | no | 1 | sí |
| clara | Si durante el viaje el médico me pide una radiografía, ¿Rimac la cubre? | no | 1 | sí |
| varias | Perdí mi maleta en el vuelo, ¿me pagan algo? Y además, ¿cuántos días tengo para avisar? | no | 2 | sí |
| varias | Me torcí el tobillo en Arequipa y fui a una clínica. ¿Me cubren la consulta? ¿Y las medicinas que compré? ¿Qué documentos tengo que presentar? | no | 3 | sí |
| varias | ¿Me cubre si me cancelan el vuelo? ¿Y si me enfermo antes de viajar? | no | 2 | sí |
| varias | Quiero saber si cubre dentista y también cuánto tiempo dura la cobertura. | no | 2 | sí |
| varias | Se me rompió un diente comiendo, ¿me cubre el dentista? ¿Tenía que llamar antes a la central? | no | 2 | sí |

## Qué hacer ahora: pasos y plazo

Situación: «Tuve un accidente durante el viaje», con fecha del hecho 2026-11-10. Un plazo se acepta solo si su número está escrito en su cita, y cada elemento, solo si su cita está en su página del PDF.

| Póliza | Plazos aceptados | Fecha límite del primero | A quién avisar | Documentos | Pasos | Citas | Descartes | USD | Segundos |
|---|---|---|---:|---:|---:|---:|---:|---:|---:|
| chubb_viajes_jetsmart | 30 dias (avisar del siniestro a la COMPAÑÍA), pág. 18 | 2026-12-10 | 2 | 3 | 8 | 10 | 0 | 0.0034 | 19.4 |
| pacifico_viajes | 7 dias (avisar del siniestro), pág. 1 | 2026-11-17 | 2 | 6 | 5 | 10 | 0 | 0.0027 | 17.4 |
| rimac_viajes | 48 horas (dar aviso a la COMPAÑÍA cuando se recurre a una clínica o médico que no está en la red de proveedores), pág. 12; 24 horas (comunicar el evento a la Central de Asistencia cuando la emergencia de salud impidió llamar antes), pág. 12 | 2026-11-12 | 3 | 5 | 5 | 7 | 0 | 0.0025 | 13.9 |
| mapfre_viajes | 7 dias (avisar del siniestro o comunicar la emergencia y la asistencia recibida), pág. 14; 7 dias (comunicarse con LA COMPAÑÍA por asistencia médica por accidente), pág. 13 | 2026-11-17 | 2 | 2 | 7 | 10 | 0 | 0.0019 | 8.3 |
| interseguro_viajes | 24 horas (avisar a la central de asistencia del evento médico o emergencia), pág. 9 | 2026-11-11 | 1 | 2 | 4 | 8 | 1 | 0.0015 | 6.4 |

## Radiografía de cada condicionado

Las versionadas en `data/cache/radiografias/` (`python -m ai.radiografia`). Cada punto lleva citas verificadas contra el PDF; es un resumen de los pasajes revisados, no la póliza entera.

| Póliza | Coberturas | Con monto escrito | Exclusiones | Deducibles | Carencias | Citas | Mencionado pero ausente | USD | Segundos |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| chubb_viajes_jetsmart | 8 | 0 | 7 | 1 | 1 | 22 | 5 | 0.0030 | 11.8 |
| pacifico_viajes | 7 | 2 | 7 | 2 | 2 | 30 | 3 | 0.0028 | 11.2 |
| rimac_viajes | 4 | 3 | 9 | 0 | 2 | 22 | 4 | 0.0024 | 10.5 |
| mapfre_viajes | 3 | 2 | 8 | 0 | 1 | 13 | 1 | 0.0033 | 14.9 |
| interseguro_viajes | 5 | 3 | 11 | 0 | 2 | 22 | 3 | 0.0028 | 12.1 |

## ¿Estás pagando doble?

Comparando las radiografías de Chubb, Pacífico y Rimac (los tres son seguros de viaje): **8 posibles superposiciones**, USD 0.0004, 3.4 s. Cada lado es una cobertura de la radiografía, con sus citas verificadas; el porqué lo redacta el modelo y no está verificado.

| Póliza A | Cobertura | Póliza B | Cobertura | Por qué (modelo) |
|---|---|---|---|---|
| Chubb Seguros Perú | Muerte Accidental | Pacífico Seguros | Muerte Accidental | Ambas cubren el pago de beneficios por muerte accidental del asegurado durante el viaje o la vigencia. |
| Chubb Seguros Perú | Muerte Accidental | Rimac Seguros | Muerte accidental | Ambas pagan beneficios a los beneficiarios si el asegurado fallece por un accidente durante el viaje. |
| Chubb Seguros Perú | Muerte accidental al salvar vidas humanas | Rimac Seguros | Muerte accidental | Ambas cubren la muerte del asegurado causada por un accidente ocurrido durante el viaje. |
| Chubb Seguros Perú | Gastos Médicos por Accidente y/o Enfermedad durante el Viaje | Pacífico Seguros | Gastos y asistencias médicos por accidente y/o enfermedad no preexistente | Ambas cubren gastos médicos por accidente o enfermedad durante el viaje. |
| Chubb Seguros Perú | Cancelación de viaje | Pacífico Seguros | Cancelación de viaje | Ambas reembolsan servicios de viaje no utilizados o cargos por cancelación del viaje. |
| Chubb Seguros Perú | Gastos Farmacéuticos durante el Viaje | Pacífico Seguros | Gastos y asistencias médicos por accidente y/o enfermedad no preexistente | Ambas cubren gastos farmacéuticos o médicos derivados de accidente o enfermedad durante el viaje. |
| Chubb Seguros Perú | Repatriación en Vida – Traslado Médico por Emergencia | Pacífico Seguros | Repatriación o traslados funerarios | Ambas cubren el traslado o repatriación del asegurado tras un evento médico o de emergencia. |
| Chubb Seguros Perú | Desmembramiento Accidental | Rimac Seguros | Invalidez permanente por accidente | Ambas pagan indemnizaciones por lesiones permanentes o invalidez causadas por un accidente. |

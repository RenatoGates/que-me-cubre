# Verificación de citas contra el PDF

Generado por `pruebas/verificar_citas.py`: abre cada PDF y busca cada cita en la página que dice.
Se comparan los caracteres en orden, ignorando solo espacios, saltos de línea y guiones (como siempre).
La cita que se audita es la que muestra la app: si el flujo le quitó un signo final (. : ; ,) para
encontrarla, la columna lo dice y lo auditado es el texto sin ese signo.

- Citas que propuso el modelo: 35
- Citas que el flujo aceptó y mostró: 35
- De esas, encontradas textualmente en su página: 35 de 35
- Con un signo final ignorado: 0

| Prueba | Cita | Sección › artículo | Página | pdfplumber | pypdf | ¿En su página? | Signo final ignorado |
|---|---|---|---|---|---|---|---|
| P01 | 1 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí | — |
| P01 | 2 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 4° Condiciones de Cobertura (parte 2 de 2) | 17 | ✓ | ✓ | sí | — |
| P01 | 3 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Texto inicial de la sección | 15 | ✓ | ✓ | sí | — |
| P02 | 1 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí | — |
| P02 | 2 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí | — |
| P02 | 3 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí | — |
| P03 | 1 | Cláusula Adicional: Pérdida de Equipaje › Artículo 3° Cobertura | 46 | ✓ | ✓ | sí | — |
| P03 | 2 | Cláusula Adicional: Pérdida de Equipaje › Artículo 3° Cobertura | 46 | ✓ | ✓ | sí | — |
| P03 | 3 | Cláusula Adicional: Pérdida de Equipaje › Artículo 3° Cobertura | 46 | ✓ | ✓ | sí | — |
| P03 | 4 | Cláusula Adicional: Pérdida de Equipaje › Artículo 5° Aviso del Siniestro y Procedimiento para Solicitar la Cobertura (parte 2 de 3) | 47 | ✓ | ✓ | sí | — |
| P03 | 5 | Cláusula Adicional: Pérdida de Equipaje › Artículo 1° Descripción de la Cobertura | 45 | ✓ | ✓ | sí | — |
| P03 | 6 | Cláusula Adicional: Pérdida de Equipaje › Artículo 1° Descripción de la Cobertura | 45 | ✓ | ✓ | sí | — |
| P03 | 7 | Cláusula Adicional: Reembolso de Gastos por Demora de Equipaje › Artículo 3° Cobertura | 49 | ✓ | ✓ | sí | — |
| P03 | 8 | Cláusula Adicional: Reembolso de Gastos por Demora de Equipaje › Artículo 3° Cobertura | 49 | ✓ | ✓ | sí | — |
| P04 | 1 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 4° Condiciones de Cobertura (parte 2 de 2) | 17 | ✓ | ✓ | sí | — |
| P04 | 2 | Cláusula Adicional: Asistencia de Viajes Adicionales – Recuperación en Hotel durante el Viaje / Acompañante en caso de hospitalización prolongada durante el viaje / Alojamiento del acompañante en caso de hospitalización prolongada durante el viaje / Interrupción de viaje y regreso anticipado / Retorno de menores › Artículo 3° Asistencias (parte 5 de 7) | 31 | ✓ | ✓ | sí | — |
| P04 | 3 | Cláusula Adicional: Asistencia de Viajes Adicionales – Recuperación en Hotel durante el Viaje / Acompañante en caso de hospitalización prolongada durante el viaje / Alojamiento del acompañante en caso de hospitalización prolongada durante el viaje / Interrupción de viaje y regreso anticipado / Retorno de menores › Artículo 3° Asistencias (parte 5 de 7) | 31 | ✓ | ✓ | sí | — |
| P04 | 4 | Cláusula Adicional: Asistencia de Viajes Adicionales – Recuperación en Hotel durante el Viaje / Acompañante en caso de hospitalización prolongada durante el viaje / Alojamiento del acompañante en caso de hospitalización prolongada durante el viaje / Interrupción de viaje y regreso anticipado / Retorno de menores › Artículo 3° Asistencias (parte 4 de 7) | 31 | ✓ | ✓ | sí | — |
| P05 | 1 | Cláusula Adicional: Cancelación del Viaje › Artículo 3° Cobertura | 41 | ✓ | ✓ | sí | — |
| P05 | 2 | Cláusula Adicional: Cancelación del Viaje › Artículo 3° Cobertura | 41 | ✓ | ✓ | sí | — |
| P05 | 3 | Cláusula Adicional: Asistencia de Viajes Adicionales – Recuperación en Hotel durante el Viaje / Acompañante en caso de hospitalización prolongada durante el viaje / Alojamiento del acompañante en caso de hospitalización prolongada durante el viaje / Interrupción de viaje y regreso anticipado / Retorno de menores › Artículo 3° Asistencias (parte 4 de 7) | 31 | ✓ | ✓ | sí | — |
| P05 | 4 | Cláusula Adicional: Cancelación del Viaje › Artículo 6° Aviso de Siniestro y Procedimiento para Solicitar la Cobertura (parte 2 de 5) | 43 | ✓ | ✓ | sí | — |
| P06 | 1 | Cláusula Adicional: Gastos Odontológicos de Emergencia durante el Viaje › Artículo 3° Cobertura | 21 | ✓ | ✓ | sí | — |
| P06 | 2 | Cláusula Adicional: Gastos Odontológicos de Emergencia durante el Viaje › Artículo 3° Cobertura | 21 | ✓ | ✓ | sí | — |
| P06 | 3 | Cláusula Adicional: Gastos Odontológicos de Emergencia durante el Viaje › Artículo 3° Cobertura | 21 | ✓ | ✓ | sí | — |
| P06 | 4 | Cláusula Adicional: Gastos Odontológicos de Emergencia durante el Viaje › Artículo 5° Exclusiones (parte 4 de 5) | 22 | ✓ | ✓ | sí | — |
| P06 | 5 | Cláusula Adicional: Gastos Odontológicos de Emergencia durante el Viaje › Artículo 3° Cobertura | 21 | ✓ | ✓ | sí | — |
| P07 | 1 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 5° Exclusiones (parte 5 de 5) | 18 | ✓ | ✓ | sí | — |
| P07 | 2 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 5° Exclusiones (parte 5 de 5) | 18 | ✓ | ✓ | sí | — |
| P07 | 3 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 5° Exclusiones (parte 5 de 5) | 18 | ✓ | ✓ | sí | — |
| P09 | 1 | PARTE C. EXCLUSIONES › 1. EXCLUSIONES GENERALES (parte 4 de 8) | 14 | ✓ | ✓ | sí | — |
| P09 | 2 | PARTE G. CONDICIONES LEGALES › 6. Coberturas y Exclusiones | 29 | ✓ | ✓ | sí | — |
| P09 | 3 | RESUMEN DE LA PÓLIZA › B. INFORMACIÓN DE LA PÓLIZA DE SEGURO › 2. Principales exclusiones (parte 3 de 3) | 4 | ✓ | ✓ | sí | — |
| P10 | 1 | Condicionado General de la Póliza › ARTÍCULO 9º.- GASTOS CUBIERTOS BAJO EL MONTO MÁXIMO GARANTIZADO › 9.5. Exámenes de ayuda al diagnóstico | 6 | ✓ | ✓ | sí | — |
| P10 | 2 | Condicionado General de la Póliza › ARTÍCULO 9º.- GASTOS CUBIERTOS BAJO EL MONTO MÁXIMO GARANTIZADO › 9.1. Asistencia médica por accidente y por Enfermedad (parte 1 de 2) | 5 | ✓ | ✓ | sí | — |

## Bloque "mencionadas pero ausentes"

Lo calcula el código, no el modelo (ai/referencias.py). Se audita igual: la mención literal
tiene que estar en la página que se muestra.

- Menciones mostradas: 20; encontradas textualmente en su página: 20 de 20

| Prueba | Referencia | Sección › artículo | Página | pdfplumber | pypdf | ¿En su página? |
|---|---|---|---|---|---|---|
| P01 | B4 - Continuación de Tratamiento en País de Residencia | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí |
| P01 | Condiciones Particulares | Cláusula Adicional: Repatriación en Vida – Traslado Médico por Emergencia › Artículo 3° Cobertura | 36 | ✓ | ✓ | sí |
| P01 | Certificado de Seguro | Cláusula Adicional: Repatriación en Vida – Traslado Médico por Emergencia › Artículo 3° Cobertura | 36 | ✓ | ✓ | sí |
| P02 | B4 - Continuación de Tratamiento en País de Residencia | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí |
| P02 | Condiciones Particulares | Cláusula Adicional: Gastos Farmacéuticos durante el Viaje › Artículo 3° Cobertura | 25 | ✓ | ✓ | sí |
| P02 | Certificado de Seguro | Cláusula Adicional: Gastos Farmacéuticos durante el Viaje › Artículo 3° Cobertura | 25 | ✓ | ✓ | sí |
| P03 | Condiciones Particulares | Cláusula Adicional: Pérdida de Equipaje › Artículo 3° Cobertura | 46 | ✓ | ✓ | sí |
| P03 | Certificado de Seguro | Cláusula Adicional: Pérdida de Equipaje › Artículo 3° Cobertura | 46 | ✓ | ✓ | sí |
| P04 | Condiciones Particulares | Cláusula Adicional: Asistencia de Viajes Adicionales – Recuperación en Hotel durante el Viaje / Acompañante en caso de hospitalización prolongada durante el viaje / Alojamiento del acompañante en caso de hospitalización prolongada durante el viaje / Interrupción de viaje y regreso anticipado / Retorno de menores › Artículo 3° Asistencias (parte 4 de 7) | 31 | ✓ | ✓ | sí |
| P04 | Certificado de Seguro | Cláusula Adicional: Asistencia de Viajes Adicionales – Recuperación en Hotel durante el Viaje / Acompañante en caso de hospitalización prolongada durante el viaje / Alojamiento del acompañante en caso de hospitalización prolongada durante el viaje / Interrupción de viaje y regreso anticipado / Retorno de menores › Artículo 3° Asistencias (parte 4 de 7) | 31 | ✓ | ✓ | sí |
| P05 | Condiciones Particulares | Cláusula Adicional: Cancelación del Viaje › Artículo 3° Cobertura | 41 | ✓ | ✓ | sí |
| P05 | Certificado de Seguro | Cláusula Adicional: Cancelación del Viaje › Artículo 3° Cobertura | 41 | ✓ | ✓ | sí |
| P06 | Condiciones Particulares | Cláusula Adicional: Gastos Odontológicos de Emergencia durante el Viaje › Artículo 3° Cobertura | 21 | ✓ | ✓ | sí |
| P06 | Certificado de Seguro | Cláusula Adicional: Gastos Odontológicos de Emergencia durante el Viaje › Artículo 3° Cobertura | 21 | ✓ | ✓ | sí |
| P07 | Condiciones Particulares | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 5° Exclusiones (parte 3 de 5) | 18 | ✓ | ✓ | sí |
| P07 | Certificado de Seguro | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 5° Exclusiones (parte 3 de 5) | 18 | ✓ | ✓ | sí |
| P08 | Condiciones Particulares | Cláusula Adicional: Asistencia de Viajes Adicionales – Recuperación en Hotel durante el Viaje / Acompañante en caso de hospitalización prolongada durante el viaje / Alojamiento del acompañante en caso de hospitalización prolongada durante el viaje / Interrupción de viaje y regreso anticipado / Retorno de menores › Artículo 3° Asistencias (parte 4 de 7) | 31 | ✓ | ✓ | sí |
| P08 | Certificado de Seguro | Cláusula Adicional: Asistencia de Viajes Adicionales – Recuperación en Hotel durante el Viaje / Acompañante en caso de hospitalización prolongada durante el viaje / Alojamiento del acompañante en caso de hospitalización prolongada durante el viaje / Interrupción de viaje y regreso anticipado / Retorno de menores › Artículo 3° Asistencias (parte 4 de 7) | 31 | ✓ | ✓ | sí |
| P09 | Condiciones Particulares | PARTE G. CONDICIONES LEGALES › 6. Coberturas y Exclusiones | 29 | ✓ | ✓ | sí |
| P09 | Condiciones Especiales | PARTE G. CONDICIONES LEGALES › 6. Coberturas y Exclusiones | 29 | ✓ | ✓ | sí |

## Respuestas que abren contra el veredicto

El veredicto es el campo estructurado; la interfaz lo muestra arriba como etiqueta. Si el texto del
modelo abre con «Sí» o «No» y el veredicto dice otra cosa, no se borra: se marca y se lista aquí.

- Casos: 0 (las salidas generadas antes del cambio a marcar las tenían recortadas)


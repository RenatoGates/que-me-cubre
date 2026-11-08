# Verificación de citas contra el PDF

Generado por `pruebas/verificar_citas.py`: abre cada PDF y busca cada cita en la página que dice.
Se comparan los caracteres en orden, ignorando solo espacios, saltos de línea y guiones.

- Citas que propuso el modelo: 23
- Citas que el flujo aceptó y mostró: 19
- De esas, encontradas textualmente en su página: 19 de 19

| Prueba | Cita | Sección › artículo | Página | pdfplumber | pypdf | ¿En su página? |
|---|---|---|---|---|---|---|
| P01 | 1 | Resumen Informativo › INFORMACIÓN DE LA PÓLIZA DE SEGURO › 1. Riesgos Cubiertos | 2 | ✓ | ✓ | sí |
| P01 | 2 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 5° Exclusiones (parte 3 de 5) | 18 | ✓ | ✓ | sí |
| P02 | 1 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí |
| P02 | 2 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 5° Exclusiones (parte 3 de 5) | 17 | ✓ | ✓ | sí |
| P02 | (descartada) | no está literal en ningún pasaje | — | — | — | descartada por el flujo |
| P03 | (descartada) | no está literal en ningún pasaje | — | — | — | descartada por el flujo |
| P03 | (descartada) | no está literal en ningún pasaje | — | — | — | descartada por el flujo |
| P04 | 1 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 4° Condiciones de Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí |
| P04 | 2 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 4° Condiciones de Cobertura (parte 1 de 2) | 17 | ✓ | ✓ | sí |
| P04 | 3 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 6° Aviso del Siniestro y Procedimiento para Solicitar la Cobertura (parte 2 de 4) | 18 | ✓ | ✓ | sí |
| P04 | 4 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 5° Exclusiones (parte 3 de 5) | 17 | ✓ | ✓ | sí |
| P05 | 1 | Cláusula Adicional: Cancelación del Viaje › Artículo 6° Aviso de Siniestro y Procedimiento para Solicitar la Cobertura (parte 2 de 5) | 43 | ✓ | ✓ | sí |
| P05 | (descartada) | no está literal en ningún pasaje | — | — | — | descartada por el flujo |
| P06 | 1 | Cláusula Adicional: Gastos Odontológicos de Emergencia durante el Viaje › Artículo 3° Cobertura | 21 | ✓ | ✓ | sí |
| P06 | 2 | Cláusula Adicional: Gastos Odontológicos de Emergencia durante el Viaje › Artículo 3° Cobertura | 21 | ✓ | ✓ | sí |
| P06 | 3 | Cláusula Adicional: Gastos Odontológicos de Emergencia durante el Viaje › Artículo 5° Exclusiones (parte 4 de 5) | 22 | ✓ | ✓ | sí |
| P07 | 1 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 5° Exclusiones (parte 5 de 5) | 18 | ✓ | ✓ | sí |
| P07 | 2 | Cláusula Adicional: Desmembramiento Accidental › Artículo 4° Exclusiones (parte 3 de 4) | 13 | ✓ | ✓ | sí |
| P09 | 1 | RESUMEN DE LA PÓLIZA › B. INFORMACIÓN DE LA PÓLIZA DE SEGURO › 1. Coberturas Básicas | 2 | ✓ | ✓ | sí |
| P09 | 2 | PARTE C. EXCLUSIONES › 1. EXCLUSIONES GENERALES (parte 4 de 8) | 14 | ✓ | ✓ | sí |
| P10 | 1 | Condicionado General de la Póliza › ARTÍCULO 9º.- GASTOS CUBIERTOS BAJO EL MONTO MÁXIMO GARANTIZADO › 9.5. Exámenes de ayuda al diagnóstico | 6 | ✓ | ✓ | sí |
| P10 | 2 | Condicionado General de la Póliza › ARTÍCULO 25°.- PROCEDIMIENTO EN CASO DE SINIESTRO › 25.4. Reembolso: | 12 | ✓ | ✓ | sí |
| P10 | 3 | Condicionado General de la Póliza › ARTÍCULO 25°.- PROCEDIMIENTO EN CASO DE SINIESTRO › 25.2. En caso de gastos médicos y hospitalarios, gastos | 12 | ✓ | ✓ | sí |

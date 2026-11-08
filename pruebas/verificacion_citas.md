# Verificación de citas contra el PDF

Generado por `pruebas/verificar_citas.py`: abre cada PDF y busca cada cita en la página que dice.
Se comparan los caracteres en orden, ignorando solo espacios, saltos de línea y guiones (como siempre).
La cita que se audita es la que muestra la app: si el flujo le quitó un signo final (. : ; ,) para
encontrarla, la columna lo dice y lo auditado es el texto sin ese signo.

- Citas que propuso el modelo: 21
- Citas que el flujo aceptó y mostró: 20
- De esas, encontradas textualmente en su página: 20 de 20
- Con un signo final ignorado: 1

| Prueba | Cita | Sección › artículo | Página | pdfplumber | pypdf | ¿En su página? | Signo final ignorado |
|---|---|---|---|---|---|---|---|
| P01 | 1 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 4° Condiciones de Cobertura (parte 2 de 2) | 17 | ✓ | ✓ | sí | — |
| P01 | 2 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí | — |
| P01 | 3 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 4° Condiciones de Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí | — |
| P02 | 1 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí | — |
| P02 | 2 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 4° Condiciones de Cobertura (parte 2 de 2) | 17 | ✓ | ✓ | sí | '.' |
| P03 | 1 | Cláusula Adicional: Pérdida de Equipaje › Artículo 3° Cobertura | 46 | ✓ | ✓ | sí | — |
| P03 | 2 | Cláusula Adicional: Pérdida de Equipaje › Artículo 3° Cobertura | 46 | ✓ | ✓ | sí | — |
| P03 | 3 | Cláusula Adicional: Pérdida de Equipaje › Artículo 4° Exclusiones (parte 2 de 2) | 46 | ✓ | ✓ | sí | — |
| P04 | 1 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 4° Condiciones de Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí | — |
| P04 | 2 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 4° Condiciones de Cobertura (parte 2 de 2) | 17 | ✓ | ✓ | sí | — |
| P04 | 3 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 6° Aviso del Siniestro y Procedimiento para Solicitar la Cobertura (parte 2 de 4) | 18–19 | ✓ | ✓ | sí | — |
| P04 | 4 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí | — |
| P05 | 1 | Cláusula Adicional: Cancelación del Viaje › Artículo 3° Cobertura | 41 | ✓ | ✓ | sí | — |
| P05 | 2 | Cláusula Adicional: Cancelación del Viaje › Artículo 4° Condiciones de Cobertura | 41 | ✓ | ✓ | sí | — |
| P05 | 3 | Cláusula Adicional: Cancelación del Viaje › Artículo 6° Aviso de Siniestro y Procedimiento para Solicitar la Cobertura (parte 2 de 5) | 43 | ✓ | ✓ | sí | — |
| P06 | 1 | Cláusula Adicional: Gastos Odontológicos de Emergencia durante el Viaje › Artículo 6° Aviso del Siniestro y Procedimiento para Solicitar la Cobertura (parte 1 de 3) | 23 | ✓ | ✓ | sí | — |
| P06 | 2 | Cláusula Adicional: Gastos Odontológicos de Emergencia durante el Viaje › Artículo 4° Condiciones de Cobertura | 21 | ✓ | ✓ | sí | — |
| P06 | (descartada) | no está literal en ningún pasaje | — | — | — | descartada por el flujo | — |
| P07 | 1 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 5° Exclusiones (parte 5 de 5) | 18 | ✓ | ✓ | sí | — |
| P07 | 2 | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 5° Exclusiones (parte 3 de 5) | 17 | ✓ | ✓ | sí | — |
| P09 | 1 | PARTE B. COBERTURAS › 2. COBERTURAS BÁSICAS | 10 | ✓ | ✓ | sí | — |

## Bloque "mencionadas pero ausentes"

Lo calcula el código, no el modelo (ai/referencias.py). Se audita igual: la mención literal
tiene que estar en la página que se muestra.

- Menciones mostradas: 23; encontradas textualmente en su página: 23 de 23

| Prueba | Referencia | Sección › artículo | Página | pdfplumber | pypdf | ¿En su página? |
|---|---|---|---|---|---|---|
| P01 | B4 - Continuación de Tratamiento en País de Residencia | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí |
| P01 | Condiciones Particulares | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 4° Condiciones de Cobertura (parte 1 de 2) | 17 | ✓ | ✓ | sí |
| P01 | Certificado de Seguro | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 4° Condiciones de Cobertura (parte 1 de 2) | 17 | ✓ | ✓ | sí |
| P02 | B4 - Continuación de Tratamiento en País de Residencia | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí |
| P02 | Condiciones Particulares | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 2° Vigencia Individual y Territorio (parte 1 de 2) | 15 | ✓ | ✓ | sí |
| P02 | Certificado de Seguro | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 2° Vigencia Individual y Territorio (parte 1 de 2) | 15 | ✓ | ✓ | sí |
| P03 | Condiciones Particulares | Cláusula Adicional: Pérdida de Equipaje › Artículo 3° Cobertura | 46 | ✓ | ✓ | sí |
| P03 | Certificado de Seguro | Cláusula Adicional: Pérdida de Equipaje › Artículo 3° Cobertura | 46 | ✓ | ✓ | sí |
| P04 | B4 - Continuación de Tratamiento en País de Residencia | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí |
| P04 | Condiciones Particulares | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 4° Condiciones de Cobertura (parte 1 de 2) | 17 | ✓ | ✓ | sí |
| P04 | Certificado de Seguro | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 4° Condiciones de Cobertura (parte 1 de 2) | 17 | ✓ | ✓ | sí |
| P05 | Condiciones Particulares | Cláusula Adicional: Cancelación del Viaje › Artículo 3° Cobertura | 41 | ✓ | ✓ | sí |
| P05 | Certificado de Seguro | Cláusula Adicional: Cancelación del Viaje › Artículo 3° Cobertura | 41 | ✓ | ✓ | sí |
| P06 | Condiciones Particulares | Cláusula Adicional: Gastos Odontológicos de Emergencia durante el Viaje › Artículo 3° Cobertura | 21 | ✓ | ✓ | sí |
| P06 | Certificado de Seguro | Cláusula Adicional: Gastos Odontológicos de Emergencia durante el Viaje › Artículo 3° Cobertura | 21 | ✓ | ✓ | sí |
| P07 | B4 - Continuación de Tratamiento en País de Residencia | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí |
| P07 | Condiciones Particulares | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí |
| P07 | Certificado de Seguro | Cláusula Adicional: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje › Artículo 3° Cobertura (parte 1 de 2) | 16 | ✓ | ✓ | sí |
| P08 | Condiciones Particulares | Condiciones Generales › Artículo 2°: Cobertura Principal – Muerte Accidental | 6 | ✓ | ✓ | sí |
| P08 | Certificado de Seguro | Condiciones Generales › Artículo 2°: Cobertura Principal – Muerte Accidental | 6 | ✓ | ✓ | sí |
| P09 | Condiciones Particulares | PARTE D. AVISO Y PROCEDIMIENTO PARA SOLICITAR LA COBERTURA EN CASO DE SINIESTRO › 2. COBERTURA DE PÉRDIDA DE EQUIPAJE (parte 1 de 3) | 16 | ✓ | ✓ | sí |
| P09 | Certificado de Seguro | PARTE D. AVISO Y PROCEDIMIENTO PARA SOLICITAR LA COBERTURA EN CASO DE SINIESTRO › 2. COBERTURA DE PÉRDIDA DE EQUIPAJE (parte 1 de 3) | 16 | ✓ | ✓ | sí |
| P10 | Tabla de Beneficios | Cláusula Adicional de Accidentes Personales › 1. COBERTURA (parte 1 de 2) | 14 | ✓ | ✓ | sí |

## Respuestas que abren contra el veredicto

El veredicto es el campo estructurado; la interfaz lo muestra arriba como etiqueta. Si el texto del
modelo abre con «Sí» o «No» y el veredicto dice otra cosa, no se borra: se marca y se lista aquí.

- Casos: 2 (las salidas generadas antes del cambio a marcar las tenían recortadas)

| Prueba | Abre con | Veredicto | Qué se hizo | Primera oración |
|---|---|---|---|---|
| P01 | «Sí» | con_limites | recortada (código anterior) | Sí, tu póliza cubre los gastos médicos por el dedo torcido, siempre que sea un accidente de carácter súbito y el tratamiento sea de urgencia. |
| P09 | «Sí» | con_limites | recortada (código anterior) | Sí, tu póliza cubre la fractura de pierna que sufriste mientras esquiabas en una pista autorizada en Bariloche, siempre que el accidente haya ocurrido dentro del lugar declarado en tu viaje. |

# Normalización anclada al documento y peso a títulos: antes y después

Generado por `pruebas/comparar_normalizacion.py` (sin LLM). Puesto = lugar del artículo
esperado en el ranking, sin repetir textos idénticos; en P02 se piden dos artículos y cuenta
el peor. La app manda al modelo los 5 primeros.

Una sola normalización por pregunta y versión: el modelo no es determinista, así que un
puesto puede cambiar de una corrida a otra.

| Configuración | En los 5 primeros | En los 8 primeros | P01 | P02 |
|---|---:|---:|---:|---:|
| Antes: normalización v1, BM25 solo en el texto | 6 de 9 | 6 de 9 | 9 | 18 y 3 |
| Solo arreglo 2: v1 + peso a títulos | 5 de 9 | 5 de 9 | 12 | 21 y 2 |
| Solo arreglo 1: normalización anclada, BM25 solo en el texto | 4 de 9 | 6 de 9 | 24 | 3 y 14 |
| Después: normalización anclada + peso a títulos | 5 de 9 | 6 de 9 | 8 | 14 y 6 |

## Puesto del artículo esperado por pregunta

| Pregunta | antes | solo_titulos | solo_anclada | despues |
|---|---:|---:|---:|---:|
| P01 | 9 | 12 | 24 | 8 |
| P02 | 18 y 3 | 21 y 2 | 3 y 14 | 14 y 6 |
| P03 | **1** | **1** | 6 | **1** |
| P04 | **2 y 44** | **2 y 14** | **5 y 33** | **3 y 11** |
| P05 | **2** | 11 | 7 | **2** |
| P06 | **4** | **3** | **3** | **1** |
| P07 | **4** | **2** | **1** | **2** |
| P09 | 44 | 25 | — | 47 |
| P10 | **1** | **1** | **3** | 23 |

En negrita: dentro de los 5 pasajes que recibe el modelo.

## Títulos que eligió la normalización anclada

- **P01** cláusulas: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje · Condiciones Generales — artículos: Riesgos Cubiertos · Principales Exclusiones · Vigencia Individual y Territorio · Aviso del Siniestro y Procedimiento para la solicitud de cobertura del seguro · Condiciones de Cobertura
- **P02** cláusulas: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje — artículos: Riesgos Cubiertos · Principales Exclusiones · Vigencia Individual y Territorio · Aviso del Siniestro y Procedimiento para la solicitud de cobertura del seguro · Condiciones de Cobertura
- **P03** cláusulas: Pérdida de Equipaje — artículos: Riesgos Cubiertos · Principales Exclusiones · Condiciones de Cobertura · Aviso del Siniestro y Procedimiento para la solicitud de cobertura del seguro · Vigencia Individual y Territorio
- **P04** cláusulas: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje · Condiciones Generales · Cláusulas Generales de Contratación Comunes a los Seguros de Accidentes Personales — artículos: Riesgos Cubiertos · Principales Exclusiones · Condiciones de Cobertura · Aviso del Siniestro y Procedimiento para la solicitud de cobertura del seguro · Vigencia Individual y Territorio
- **P05** cláusulas: Cancelación del Viaje · Condiciones Generales — artículos: Riesgos Cubiertos · Principales Exclusiones · Vigencia Individual y Territorio · Aviso del Siniestro y Procedimiento para la solicitud de cobertura del seguro · Condiciones de Cobertura
- **P06** cláusulas: Gastos Odontológicos de Emergencia durante el Viaje · Gastos Médicos por Accidente y/o Enfermedad durante el Viaje — artículos: Riesgos Cubiertos · Principales Exclusiones · Aviso del Siniestro y Procedimiento para la solicitud de cobertura del seguro · Vigencia Individual y Territorio · Condiciones de Cobertura
- **P07** cláusulas: Gastos Médicos por Accidente y/o Enfermedad durante el Viaje — artículos: Riesgos Cubiertos · Principales Exclusiones · Condiciones de Cobertura · Aviso del Siniestro y Procedimiento para Solicitar la Cobertura · Vigencia Individual y Territorio
- **P09** cláusulas: COBERTURAS · EXCLUSIONES · AVISO Y PROCEDIMIENTO PARA SOLICITAR LA COBERTURA EN CASO DE SINIESTRO — artículos: Coberturas Básicas · Principales exclusiones · Vigencia del Seguro · VALIDEZ TERRITORIAL DE LA COBERTURA · Medio y plazo establecido para el aviso del siniestro
- **P10** cláusulas: Accidentes Personales — artículos: Asistencia médica por accidente y por Enfermedad · ENFERMEDADES, TRATAMIENTOS Y OTROS GASTOS NO CUBIERTOS · EXCLUSIONES · PROCEDIMIENTO EN CASO DE SINIESTRO · COBERTURA

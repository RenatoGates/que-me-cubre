# Portero de documento: ¿parece un condicionado de seguro?

Generado por `pruebas/medir_portero.py`. Sin modelo: `ai/portero.py` cuenta en el texto extraído 16 marcadores de vocabulario de póliza. Un documento *parece póliza* si tiene al menos 16 apariciones por cada mil palabras **y** al menos 5 marcadores distintos. Bajo el umbral no se bloquea: se avisa y se deja continuar.

| | Dice «parece póliza» | Dice «no parece» (aviso) |
|---|---:|---:|
| Es un condicionado (6) | 6 | 0 |
| No lo es (3) | 0 | 3 |

Clasificó bien 6 de 6 condicionados y 3 de 3 documentos que no lo son.

| Documento | ¿Es condicionado? | Marcadores por mil palabras | Marcadores distintos | Palabras | Resultado |
|---|---|---:|---:|---:|---|
| Chubb Seguros Perú · Seguro de Viajes JetSmart | sí | 51.0 | 16 | 34606 | parece póliza |
| Pacífico Seguros · Seguro de Viajes Pacífico | sí | 46.0 | 16 | 16209 | parece póliza |
| Rimac Seguros · Seguro de Viaje | sí | 45.3 | 15 | 13014 | parece póliza |
| Mapfre Perú · Accidentes Personales con Asistencia en Viaje para Turismo | sí | 43.4 | 13 | 11338 | parece póliza |
| Interseguro · Seguro de Viaje Internacional | sí | 24.1 | 9 | 14874 | parece póliza |
| Póliza dental real (privada, sin versionar) | sí | 35.6 | 12 | 8044 | parece póliza |
| Boletín informativo de SUSALUD sobre las EPS (no es un condicionado) | no | 9.2 | 8 | 8804 | aviso |
| Cláusulas generales de un contrato de tarjeta de crédito (Banco de la Nación): un contrato que no es de seguro | no | 6.8 | 7 | 13892 | aviso |
| Constitución Política del Perú de 1993 (publicada en gob.pe) | no | 0.9 | 2 | 21112 | aviso |

Negativos descargados (no se versionan; están en `data/privado/negativos/`):

- Cláusulas generales de un contrato de tarjeta de crédito (Banco de la Nación): un contrato que no es de seguro: <https://www.bn.com.pe/clientes/tarjetas/formatos/TC-clausulas-generales.pdf>, sha256 `8095e64a728bb578…`
- Constitución Política del Perú de 1993 (publicada en gob.pe): <https://cdn.www.gob.pe/uploads/document/file/606704/constitucion_1993.pdf>, sha256 `df08832fce9d007a…`

Límite: son 9 documentos y el umbral se fijó mirándolos, así que estos aciertos no predicen cómo le irá con otros. Un documento que habla de seguros sin ser una póliza (un boletín, un folleto comercial) es el caso difícil. De la póliza dental privada aquí solo hay números: su texto no está en el repositorio.

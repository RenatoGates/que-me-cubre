# ¿Qué me cubre?

> Subes el PDF de tu póliza, preguntas en español normal y te responde citando la
> cláusula exacta, con artículo y página.

Proyecto final de la Diplomatura de Ciencia de Datos (Q-Lab PUCP), curso de Ciencia de
Datos con Python. Enunciado: [d2cml-ai/Data-Science-Python#204](https://github.com/d2cml-ai/Data-Science-Python/issues/204).

> **Aviso.** Esta herramienta es informativa. La decisión final sobre la cobertura la
> toma la aseguradora.
>
> **Privacidad.** El PDF que subes se procesa en memoria: no se guarda en disco, ni en
> logs, ni en ningún estado persistente. Las consultas no se registran: si una llamada al
> modelo falla, los logs de la app guardan solo el código y el mensaje de error del
> proveedor, nunca la pregunta ni el texto de la póliza. Para redactar la
> respuesta, tu pregunta y los fragmentos de la póliza que encontré (no el PDF entero) se
> envían al proveedor del modelo: Groq, con retención cero de datos activada.

---

## 1. One-liner

Hacemos que cualquier asegurado sepa qué le cubre su póliza, para viajeros y familias en el
Perú, mediante una IA que responde solo con las cláusulas de su propio PDF y cita artículo y
página.

## 2. Founder

Renato Christian Gates Rojas, economista por la PUCP. Trabajo con datos del sistema
financiero peruano en la Asociación de Bancos del Perú, y antes fui analista de
investigación en Innovations for Poverty Action. Soy el usuario del problema: tengo un
seguro de salud por el trabajo y no sé qué cubre. Construí esto solo, con Claude Code como
socio técnico: yo decidí qué construir y qué no, y verifiqué los resultados contra los PDF
originales.

## 3. Problema

**Quién lo sufre:** personas con seguro de salud o de viaje en el Perú que, en el momento de
necesitarlo, no saben qué les cubre. El documento existe, tiene 62 páginas y nadie lo lee.

**Cuánto cuesta:** terminas pagando de tu bolsillo algo que tu póliza cubría, o dejas de
atenderte por no saber si te cubre.

**Cómo se resuelve hoy:** no se resuelve. Se llama a la aseguradora en horario de oficina,
se pregunta a un conocido, o se asume lo peor.

**Evidencia**, tres conversaciones en [`docs/research/`](docs/research/):

- [Entrevistado 1](docs/research/entrevista_1.md), seguro de salud del trabajo: "No, tendría
  que ponerme a descargar la póliza del seguro, investigar, ponerme a leer". Pagaría menos
  de 10 soles al mes.
- [Entrevistada 2](docs/research/entrevista_2.md), EPS: "La verdad no, solo las consultas,
  creo yo". Valora sobre todo "entender con facilidad y saber qué hacer".
- [Entrevistado 3](docs/research/entrevista_3.md), seguro de viaje: se accidentó en
  Tarapoto, fue a un centro médico de noche y pagó de su bolsillo sin saber si le
  reembolsaban. Después le indicaron una radiografía en Lima y tampoco sabía si eso entraba.

**Advertencia metodológica:** las dos primeras entrevistas incluyeron preguntas dirigidas
sobre la app, así que la disposición a pagar que reportan no es evidencia fuerte. La tercera
sí es un episodio real con gasto real.

## 4. Solución e insight

**Solución.** Subes el PDF de tu póliza (o eliges un condicionado precargado) y preguntas
como hablas: "me torcí el dedo en Tarapoto, ¿me cubre?". La app busca en tu propio documento
los pasajes que responden, el modelo redacta la respuesta en JSON con citas, y el código
verifica cada cita letra por letra contra la página del PDF antes de mostrarla. Arriba va el
veredicto ("Cubre con límites"), debajo la explicación, lo que la póliza menciona pero no
trae, y las citas con su artículo y página. Si el modelo falla, se ven igual las cláusulas
encontradas.

**Insight:** el modelo redacta, pero lo que el asegurado puede comprobar lo pone el código.
Cada cita está literal en su página, y lo que la póliza menciona sin incluir su texto (en
Chubb, la cobertura "B4 - Continuación de Tratamiento en País de Residencia") aparece
siempre, con su página, aunque el modelo no lo diga: en las 10 corridas de P02 con el bloque
lo mostró el código, mientras que el modelo solo no lo nombró en ninguna de 5.

## 5. Why now

Hace tres años esto no se podía hacer solo y gratis. Hoy sí, por tres cosas: los modelos de
lenguaje con salidas estructuradas permiten convertir una pregunta coloquial al vocabulario
técnico de una póliza; hay proveedores con plan gratuito que lo hacen viable sin
presupuesto; y un agente de programación permite que una persona construya y despliegue el
flujo completo en días. Nada de esto reemplaza lo importante, que es que el producto no
invente: eso se resolvió con código, verificando cada cita contra su página del PDF.

## 6. Demo

- **URL pública:** [queqbre.streamlit.app](https://queqbre.streamlit.app/) (Streamlit
  Community Cloud). Dos pestañas: "Pregunta a tu póliza" y "Dónde atenderte".
- **Video de respaldo:** **[PENDIENTE: link al video]**, por si en la demo falla la conexión
  o la cuota.
- **Casos de la demo:** las dos preguntas reales de Tarapoto, como botones, sobre el
  condicionado de Chubb · JetSmart: la torcedura (P01) y la radiografía al llegar a Lima
  (P02).
- **Resultados, al primer intento y sin reintento (lo que vive el usuario):** 8 de 10
  preguntas de prueba con veredicto aceptable (9 de 10 si el script reintenta una vez). Las
  dos preguntas de la demo, cinco veces cada una con el tope de 3800 tokens: las 10
  respuestas salieron completas al primer intento; P01 fue aceptable en 5 de 5 y P02 en 4 de
  5 (una corrida respondió "no"), y B4 apareció en el bloque las 10 veces
  ([`pruebas/estabilidad.md`](pruebas/estabilidad.md)). Detalle y límites en Limitaciones.
- **Capturas:** en [`docs/arquitectura.md`](docs/arquitectura.md#capturas): la pantalla
  inicial, la radiografía al llegar a Lima (P02), la torcedura en Tarapoto (P01) con una
  cita desplegada y "Dónde atenderte" en Tarapoto, tomadas de la app desplegada con
  respuestas en vivo de Groq.
- **Diagrama de arquitectura:** [`docs/arquitectura.md`](docs/arquitectura.md) (Mermaid) y
  [`docs/arquitectura.png`](docs/arquitectura.png), incluida la pestaña del mapa.
- **Modelos y por qué:** ver abajo.

### Modelos y por qué

| Paso | Qué usa | Por qué |
|---|---|---|
| Extraer texto, página y artículo | pdfplumber (sin modelo) | Los condicionados tienen capa de texto; no hace falta OCR |
| Normalizar la pregunta | `openai/gpt-oss-120b` en Groq | Elige del índice del PDF la cláusula que la respondería ("Gastos Médicos por Accidente y/o Enfermedad durante el Viaje" para "me torcí el dedo") y escribe 3-5 variantes con las palabras de ese documento; el código descarta títulos que no existan en él |
| Buscar los pasajes | BM25 sobre las variantes y la cláusula elegida, cuyos pasajes valen el doble (sin modelo) | Ver la decisión de memoria y [`pruebas/normalizacion.md`](pruebas/normalizacion.md) |
| Redactar la respuesta JSON con citas | `openai/gpt-oss-120b` en Groq | Salida con esquema JSON estricto; las citas se verifican después contra el PDF y el texto libre se recorta si nombra algo que no está citado. El veredicto es el campo estructurado `cubre`, no el texto: ver "Cómo se muestra una respuesta" |
| Avisar lo que la póliza menciona pero no trae | Código ([`ai/referencias.py`](ai/referencias.py)), sin modelo | Si un pasaje recuperado nombra una cobertura, un anexo o un documento cuyo texto no está en el PDF ("B4 - Continuación de Tratamiento en País de Residencia"), la respuesta lo muestra siempre, con la mención literal y su página: "Tu póliza menciona … pero no incluye su texto en este documento. Pídeselo a tu aseguradora." Las coberturas con nombre propio van arriba y resaltadas; las remisiones genéricas (Condiciones Particulares, Certificado de Seguro), debajo y plegadas |

**Proveedor: Groq, plan gratuito, con Zero Data Retention.** La app promete que la póliza
no se guarda ni se reutiliza, y ese discurso solo se sostiene sobre un proveedor que no
retiene lo que se le envía. La documentación de Groq dice: "By default, Groq does not
retain customer data for inference requests", y cualquier cuenta puede activar la
retención cero ([Your Data](https://console.groq.com/docs/your-data)). `gpt-oss-120b`
admite salidas estructuradas en modo estricto ([Structured Outputs](https://console.groq.com/docs/structured-outputs)).

**Gemini queda como alternativa manual** (`QMC_PROVEEDOR=gemini`, con `gemini-3.8-flash`)
detrás de la misma interfaz ([`ai/llm.py`](ai/llm.py)), pero no es el proveedor por
defecto: en su plan gratuito "Google uses the content you submit to the Services and any
generated responses to provide, improve, and develop" sus productos, "human reviewers may
read, annotate, and process your API input and output", y piden "Do not submit sensitive,
confidential, or personal information" ([términos](https://aistudio.google.com/docs/terms)).
Si se elige, la interfaz advierte que ese proveedor puede revisar y reutilizar lo enviado.

No hay respaldo automático: si el proveedor llega al límite de su plan gratuito o no
responde, la app no cambia de modelo; muestra las cláusulas encontradas, resaltadas y sin
texto generado, con un aviso de por qué.

**Por qué BM25 y no embeddings en la app.** El modelo de embeddings de la sesión 08
(`intfloat/multilingual-e5-small`) con torch ocupa unos 1,2 GB de RAM medidos en Windows
(pico de 1,4 GB). Streamlit Community Cloud documenta hoy un mínimo de 690 MB y un máximo
de 2,7 GB por app ([Manage your app](https://docs.streamlit.io/deploy/streamlit-community-cloud/manage-your-app));
la cifra de 1 GB con la que se planificó era la de documentación anterior. Aun con el
máximo actual, el modelo quedaría por encima del mínimo garantizado y se arriesgaría la
demo en vivo, así que la app usa BM25. Como BM25 busca por palabras, la normalización no
devuelve una frase sino de 3 a 5 variantes, y los rankings se combinan. Medido en las 9
preguntas de prueba con artículo esperado ([`pruebas/recuperacion.md`](pruebas/recuperacion.md),
con la normalización v1): con los 5 primeros pasajes, BM25 con variantes encuentra el
artículo en 6 de 9, embeddings con la pregunta original en 5 de 9 y BM25 con la pregunta
original en 2 de 9. Los embeddings no ganan en conjunto, pero sí encuentran el caso de la
torcedura en Tarapoto (P01), que BM25 dejaba en el puesto 9.

**Normalización anclada al documento.** La primera versión escribía las variantes con
vocabulario genérico de seguros ("lesión accidental") y BM25 no las encontraba en una
póliza que dice "Accidentes". Ahora el modelo recibe los títulos de cláusula y de artículo
del PDF y elige de ellos; la cláusula elegida es una consulta más y sus pasajes valen el
doble (filtro suave: no excluye el resto). Se probaron también un índice aparte solo de
títulos y usar los artículos elegidos: los dos empeoraron la búsqueda y quedaron apagados.
Resultados, con sus límites, en [`pruebas/normalizacion.md`](pruebas/normalizacion.md) y en
Limitaciones.

### Cómo se muestra una respuesta

Contrato para la interfaz (los campos salen de `responder` en [`ai/respuesta.py`](ai/respuesta.py)):

1. **Arriba, como etiqueta bien visible, el veredicto**, sacado del campo estructurado
   `cubre` (`etiqueta_veredicto`: "Cubre", "Cubre con límites", "No cubre", "No está en tu
   póliza"). Es la fuente de verdad: el texto del modelo nunca la reemplaza.
2. **Debajo, el texto del modelo como explicación** de las condiciones y los límites. Si
   abre contradiciendo el veredicto ("Sí, está cubierta…" con "con límites"), no se borra
   nada: queda marcado en `apertura_contradictoria`, se lista en la auditoría y la etiqueta
   de arriba sigue mandando. (Pedirle en el prompt que no abriera con "Sí" ni "No" se probó
   y se revirtió: ver "Plan gratuito del modelo" en Limitaciones.)
3. Las condiciones y las exclusiones que aplican, cada una con sus citas, y aparte "exclusiones
   que podrían aplicar según tu caso" (`podrian_aplicar`): útil, pero no afirmado.
4. **Lo que la póliza menciona pero no trae** (`mencionadas_ausentes`), que calcula el
   código: arriba y resaltadas las cláusulas con nombre propio (`nivel: clausula_ausente`,
   como B4), con su mención literal y su página; debajo y plegadas las remisiones genéricas
   a Condiciones Particulares o Certificado de Seguro (`nivel: remision`).
5. Las citas, con documento, sección, artículo y página.

En la red de seguridad (`modo: solo_clausulas`) la etiqueta dice "Sin veredicto", el aviso
explica por qué y se muestran los pasajes resaltados y el bloque de lo mencionado pero ausente.

### Cómo correrlo en local

App (Python 3.11), con `GROQ_API_KEY=...` en un `.env` en la raíz:

```bash
uv pip install -r app/requirements.txt
streamlit run app/app.py
```

Para maquetar sin gastar cuota, `QMC_PROVEEDOR=grabado streamlit run app/app.py`: la
respuesta del modelo es la que ya dio para esa pregunta en `pruebas/salidas/` y todo lo
demás corre de verdad (las preguntas sin grabación caen en la red de seguridad). La
interfaz se prueba sin navegador con `python pruebas/probar_app.py`; cómo se clasifican y
registran las fallas de Groq (sin red), con `python pruebas/probar_llm.py`; y las capturas
salen de `python pruebas/capturas.py --url ...` (Playwright, solo en local).

Desplegar en Streamlit Community Cloud: *Create app* desde este repositorio, rama `main`,
archivo `app/app.py`; en *Advanced settings*, Python 3.11 y en *Secrets*
`GROQ_API_KEY = "..."`. La clave nunca va al repositorio. Las dependencias salen de
[`app/requirements.txt`](app/requirements.txt), sin torch (ver "Por qué BM25").

Reconstruir los índices de los condicionados precargados (Python 3.11):

```bash
uv venv --python 3.11 .venv
uv pip install torch --index-url https://download.pytorch.org/whl/cpu
uv pip install -r requirements-dev.txt
python -m ai.ingesta --ejemplos 3        # --descargar baja los PDF que falten
```

Las fuentes de cada condicionado (URL, fecha y sha256) están en
[`data/polizas/fuentes.json`](data/polizas/fuentes.json). Precargados: Chubb (Seguro de
Viajes JetSmart, 62 págs.), Pacífico (Seguro de Viajes, 40 págs.) y Rimac (Seguro de
Viaje, 20 págs. a dos columnas).

## 7. Modelo de negocio

**Quién paga.** El usuario final no es el que paga. Las entrevistas dan menos de 10 soles al
mes de disposición a pagar, que no sostiene el producto ni justifica la adquisición.

Quien paga es la aseguradora, el corredor o la agencia de viajes. Su incentivo es directo:
un asegurado que no sabe qué cubre su póliza no la usa, se atiende particular, y después
reclama o no renueva. Modelo: licencia mensual por cartera, con tres planes según número de
asegurados.

**Costo por usuario, medido:** 4998 tokens por consulta ensayada y 6998 por consulta nueva.
A precio pagado de Groq para `gpt-oss-120b`, 100 usuarios con 10 consultas al mes cuestan
alrededor de USD 1,94 mensuales en modelo. El costo dominante no es el modelo, es el
servidor. El detalle de las cifras, abajo.

**Costo por consulta hoy: USD 0.** El modelo corre en el plan gratuito de Groq y la app en
el plan gratuito de Streamlit Community Cloud; ninguno cobra por token ni por hora. Lo que
se cede a cambio es capacidad: el plan gratuito limita peticiones y tokens por minuto y por
día. Cada consulta hace dos llamadas al modelo (normalizar y responder); las preguntas
ensayadas tienen la normalización en una caché versionada y gastan una sola.

**Tokens por consulta**, promedio de la corrida de las 10 preguntas con la configuración
actual (5 pasajes, [`pruebas/resultados.md`](pruebas/resultados.md)):

| Llamada | Entrada | Salida (incluye razonamiento) | Total |
|---|---:|---:|---:|
| Normalizar la pregunta | 1590 | 410 | 2000 |
| Responder | 3428 | 1570 | 4998 |
| **Pregunta nueva (las dos)** | **5018** | **1980** | **6998** |

Una pregunta ensayada, con la normalización en la caché, gasta solo la respuesta: 4998. La
cifra de 6583 tokens que se citaba antes era la respuesta con la configuración anterior, de
unos 10 pasajes ([`pruebas/opciones.md`](pruebas/opciones.md)). Con el tope de la respuesta
subido a 3800, una respuesta larga puede gastar algo más que el promedio: el primer intento
de P01 en la medición nueva usó 6372.

**Con 100 usuarios haciendo 10 consultas al mes** (1000 consultas, todas preguntas nuevas):
5,02 millones de tokens de entrada y 1,98 millones de salida. Al precio de pago de Groq para
`gpt-oss-120b`, USD 0,15 por millón de entrada y 0,60 por millón de salida ([página del
modelo](https://console.groq.com/docs/model/openai/gpt-oss-120b), consultada el 2026-11-08):
5,02 × 0,15 + 1,98 × 0,60 = 0,75 + 1,19 ≈ **USD 1,94 al mes**, unos 0,2 centavos por
consulta. A ese volumen el plan gratuito ya no alcanza, aunque cueste cero: 1000 consultas
al mes son unas 33 al día y unos 233 000 tokens diarios, por encima de los 200 000 por día
del plan. Habría que pasar al plan de pago por token de Groq. El límite por minuto no es el
que pesa: con 5 pasajes entra una pregunta nueva cada ~36 s.

**Cómo funciona el límite por minuto (8000 tokens).** Medido con las cabeceras de Groq: es
un balde que se rellena a 133 tokens por segundo; para `gpt-oss-120b`, una llamada entra si
quedan libres más o menos los tokens de su entrada (Groq pidió 5428 para una entrada de
5040, sin contar el máximo de salida) y después se descuenta lo que gastó de verdad. Con
unos 10 pasajes, 5 consultas seguidas necesitaban una cada 46 s si estaban en la caché y una
cada 54 s si eran nuevas; por eso la app manda 5 pasajes (opción A de
[`pruebas/opciones.md`](pruebas/opciones.md)): 5 consultas en la caché entran una cada 28 a
34 s, y una nueva cada 36 s. Se midieron también respuestas más cortas (menos razonamiento:
más barato, pero dos veredictos de diez empeoran) y `gpt-oss-20b` (mismo tope de 8000 por
minuto, y Groq le suma el máximo de salida a lo pedido, así que algunas consultas se
rechazan aun con el balde lleno). Scripts:
[`pruebas/medir_cuota.py`](pruebas/medir_cuota.py) (tokens y cabeceras de una consulta),
[`pruebas/simular_cuota.py`](pruebas/simular_cuota.py) (el límite por minuto) y
[`pruebas/comparar_opciones.py`](pruebas/comparar_opciones.py) (las opciones de recorte).

## 8. Herramientas del curso

| Herramienta | Sesión | Dónde está en el código |
|---|---|---|
| Document AI: extraer el texto del PDF conservando página y artículo | 10 | [`ai/extraccion.py`](ai/extraccion.py): texto por página con pdfplumber, detección de dos columnas, limpieza de membretes, secciones y artículos; troceado por artículo en [`ai/troceado.py`](ai/troceado.py) |
| LLM con salidas estructuradas y RAG | 08 | Índice en [`ai/indice.py`](ai/indice.py); prompts y esquemas JSON estrictos en [`ai/prompts.py`](ai/prompts.py); proveedor del LLM detrás de una interfaz en [`ai/llm.py`](ai/llm.py); recuperación BM25 multiconsulta en [`ai/recuperacion.py`](ai/recuperacion.py); flujo y validación de citas en [`ai/respuesta.py`](ai/respuesta.py) y [`ai/verificacion.py`](ai/verificacion.py) |
| Mapas con datos abiertos | 06 | Pestaña "Dónde atenderte" (`pantalla_mapa` en [`app/app.py`](app/app.py)): la persona elige departamento y distrito y ve los establecimientos activos de RENIPRESS (SUSALUD, [datosabiertos.gob.pe](https://www.datosabiertos.gob.pe/dataset/registro-nacional-de-entidades-prestadoras-de-servicios-de-salud-renipress)) en un mapa y una lista; preparación y filtros en [`ai/renipress.py`](ai/renipress.py). No usa el modelo, así que funciona sin cuota |

## 9. Qué hizo el agente

El código, las pruebas y las mediciones los escribió un agente de programación (Claude Code,
de Anthropic) bajo la dirección del founder. Las decisiones fueron del founder, a partir de
opciones y mediciones que el agente presentó: Groq con retención cero como proveedor, BM25
en vez de embeddings en la app, el bloque determinista para lo mencionado pero ausente,
marcar la apertura contradictoria en vez de recortarla, aceptar la variación del veredicto
de P02, no reintentar en la app y revertir la regla del "Sí"/"No".

Lo que hizo el agente:

- Extracción con página y artículo, troceado, índice BM25, normalización anclada al
  documento, verificación de citas contra el PDF con dos lectores, bloque de lo mencionado
  pero ausente, red de seguridad, la app de Streamlit y la pestaña del mapa.
- Pruebas sin red ni cuota:
  [`pruebas/probar_verificacion.py`](pruebas/probar_verificacion.py) (42 casos),
  [`pruebas/probar_llm.py`](pruebas/probar_llm.py) (36) y
  [`pruebas/probar_app.py`](pruebas/probar_app.py) (23, la interfaz con respuestas
  grabadas).
- Mediciones con cuota real: las 10 preguntas, la estabilidad de P01 y P02, la auditoría de
  citas, la cuota por minuto y por día, y las opciones de recorte (todo en `pruebas/`).
- El despliegue verificado en la nube con un navegador sin interfaz (Playwright), sin llamar
  al modelo, y las capturas.

Errores del agente, documentados: desplegó sin medir una regla de prompt que hizo cortar las
respuestas en el tope de tokens (3 de 3); sus scripts de prueba reintentaban en silencio y
el "9 de 10" era 8 de 10 al primer intento; y en un commit afirmó una regla de admisión por
minuto de Groq que era la de otro modelo, corregida en el siguiente.

---

## Estructura del repositorio

```
que-me-cubre/
├── app/            app de Streamlit (y su requirements.txt)
├── ai/             extracción, troceado, índice, recuperación, prompts, respuesta y RENIPRESS
├── data/
│   ├── polizas/    condicionados públicos de prueba (se versionan)
│   ├── indices/    índices ya construidos de esos condicionados
│   ├── cache/      normalizaciones de las preguntas de ensayo y de prueba
│   ├── demo/       preguntas de ensayo de la demo
│   ├── renipress/  establecimientos activos de RENIPRESS para el mapa
│   └── privado/    pólizas personales para pruebas locales (ignorado por git)
├── docs/           arquitectura, capturas y research/ con las 3 conversaciones
└── pruebas/        preguntas, corridas medidas con sus salidas y pruebas sin red
```

## Limitaciones

- **PDF escaneados:** la extracción necesita capa de texto. Si la mayoría de páginas no la
  tiene, la ingesta lo rechaza (haría falta OCR).
- **Tablas:** las filas de tablas (por ejemplo, porcentajes de indemnización) se leen fila
  por fila con pdfplumber, pero otro extractor (pypdf) las ordena distinto. En las tres
  pólizas precargadas, 41 de 5427 líneas no se pudieron confirmar con pypdf y todas son
  filas de tablas. El texto corrido coincide con su página.
- **Embeddings fuera de la app:** ver "Por qué BM25 y no embeddings" en la sección 6. Los
  embeddings se calculan en la ingesta solo para la comparación de `pruebas/`.
- **Plan gratuito del modelo:** tiene límites de peticiones y tokens por minuto. Si se
  alcanzan, la app muestra las cláusulas encontradas sin texto generado. Lo mismo pasa si el
  modelo no logra un JSON válido, y la app no reintenta (un reintento duplica la espera y la
  cuota). Groq lo rechaza con `json_validate_failed`, y ese código incluye el caso más
  común: la respuesta se cortó al llegar al tope de tokens de salida, que cuenta también el
  razonamiento del modelo. Con el prompt actual y el tope de 3000, en las corridas medidas 2
  de 27 llamadas salieron sin texto al primer intento: P05 en la corrida de las 10 preguntas
  y un intento de la primera serie de P02, que el script de entonces rehízo sin guardarlo.
  Ninguno registró el tipo de falla; la salida más larga que sí entró usó 2550 de los 3000.
  Por eso el tope de la respuesta subió a 3800, y con él, en las 10 corridas siguientes de P01 y P02,
  ninguna se quedó sin texto al primer intento; la salida más larga usó 3150 tokens, que con el
  tope de 3000 se habría cortado. Para `gpt-oss-120b`, Groq admite cada
  llamada por la entrada estimada, sin sumar el tope
  ([`pruebas/opciones.md`](pruebas/opciones.md)), así que subirlo no cambia la admisión por
  minuto: solo deja terminar una respuesta larga, y P02, la entrada más grande (3734),
  usaría como mucho 7534 de los 8000 por minuto. Una regla agregada al prompt para que la
  respuesta no abriera con "Sí" ni "No" empeoró los cortes: desplegada sin medir, 3 de 3
  consultas se cortaron (2 en la app desplegada y la reproducción en local, con el mensaje
  de Groq "max completion tokens reached"), y se revirtió al prompt de las corridas medidas.
  Cada falla deja en los logs la tarea, el código y el mensaje de Groq, sin la pregunta ni
  lo generado. Si el límite llega en la normalización de una pregunta nueva, la búsqueda usa
  la pregunta tal cual y es menos precisa (en las pruebas, BM25 con la pregunta original
  acierta 4 de 9 con 8 pasajes).
- **Resultados de las pruebas:** 8 de 10 veredictos aceptables al primer intento, que es lo
  que vive el usuario porque la app no reintenta. El script de pruebas reintenta una vez
  para avanzar la corrida y con ese reintento da 9 de 10: P05 salió sin texto la primera vez
  (el tipo de falla no se registraba entonces) y aceptable la segunda
  ([`pruebas/resultados.md`](pruebas/resultados.md), que da los dos números). Es el código
  de la corrida del 2026-11-08 (commit 039314c), y el prompt de la respuesta es el mismo.
  P10 queda en "no encontrado" porque el filtro suave dejó su artículo en el puesto 11 (ver
  el punto siguiente). Las 20 citas mostradas están literales en su página y las 23
  menciones del bloque de ausentes también
  ([`pruebas/verificacion_citas.md`](pruebas/verificacion_citas.md)). Con 5 pasajes, BM25
  con variantes trae el artículo esperado en 7 de 9
  ([`pruebas/recuperacion.md`](pruebas/recuperacion.md)). En esa corrida y en las cinco de
  P01, el modelo abrió 4 veces con "Sí" y veredicto "con límites"; el código de entonces
  recortaba esa oración (P01 perdió su frase principal y P09 quedó sin texto propio), y por
  eso ahora se marca en vez de recortar. La corrida anterior (8 pasajes, normalización v1)
  había dado 6 de 10.
- **El filtro suave por cláusula está ajustado a las preguntas de la demo.** Subió P01 del
  puesto 9 al 4 y P02 de 18 y 3 a 3 y 4, y bajó P10 del puesto 1 al 11 (el modelo eligió la
  cláusula de Accidentes Personales en vez del Condicionado General, y el doble de puntaje
  bastó para enterrar el artículo correcto). En total quedan 7 de 9 preguntas con el artículo
  en los 5 primeros pasajes, contra 6 de 9 antes: casi un empate, y la mejora cayó justo en
  las dos preguntas de la demo. Eso es ajuste al caso de prueba. El factor (×2) no está
  calibrado: ×2, ×3, ×5 y el filtro duro dan exactamente el mismo resultado en estas 9
  preguntas, así que ellas no permiten elegir entre ellos. Nueve preguntas no alcanzan para
  calibrar nada; haría falta un conjunto de preguntas bastante más grande, escrito sin mirar
  los resultados ([`pruebas/normalizacion.md`](pruebas/normalizacion.md)).
- **Verificación de citas:** la cita tiene que estar en el pasaje y en su página del PDF,
  carácter por carácter. Se ignoran los espacios, los saltos de línea y los guiones de fin de
  línea (el PDF corta las palabras), las comillas tipográficas y un único signo de puntuación
  al final de la cita (. : ; ,), porque el modelo suele cerrar con punto una cita que en el
  PDF termina en dos puntos. En ese caso se muestra la cita sin el signo. Nada más se relaja:
  una tilde, una palabra o una coma interna distinta la invalidan
  ([`pruebas/probar_verificacion.py`](pruebas/probar_verificacion.py)).
- **Texto libre de la respuesta:** no puede nombrar artículos, numerales, códigos de
  cobertura (B4), documentos (Condiciones Particulares, Certificado de Seguro, endosos…) ni
  títulos de cláusula que no estén en las citas verificadas; la oración que lo hace se
  recorta y el recorte queda registrado. Un título de cláusula se detecta solo si se nombra
  completo: una paráfrasis ("la cláusula dental") pasa sin control.
- **Las citas verificadas no garantizan la conclusión.** La verificación garantiza que cada
  cita existe literalmente en su página. No garantiza que la conclusión se siga de ellas, y
  eso puede fallar en las dos direcciones. En P02 el modelo respondió "Sí, la radiografía
  está cubierta…" con tres citas reales (los exámenes de diagnóstico del Art. 3°, las
  urgencias del Art. 4° y el ámbito territorial del Art. 2°) e ignoró la oración del mismo
  pasaje que dice que la protección termina en la fecha de llegada; en otras dos corridas
  respondió "no" apoyado en la exclusión de exámenes de rutina sin indicación objetiva, para
  una radiografía que indicó un médico. Las tres citas de cada caso eran literales y estaban
  en su página. Lo único que el código revisa de la conclusión es la apertura: el veredicto
  que se muestra es el campo estructurado, como etiqueta arriba; si el texto abre con "Sí" o
  "No" contra él, el caso se marca en la auditoría y no se borra nada. No hay una segunda
  llamada al modelo para revisar la conclusión: encadenar modelos no es una garantía. La
  conclusión es del modelo; las citas, que sí están verificadas, son lo que hay que leer.
- **La respuesta no es determinista:** con la normalización en la caché, la búsqueda sí lo
  es (mismos pasajes y mismo mensaje al modelo en cada corrida), pero el modelo puede
  responder distinto a la misma entrada. Estas series no reintentan: cada corrida es un
  primer intento, como en la app (salvo un intento de la primera serie de P02 que cayó en la
  red de seguridad y el script de entonces rehízo; ver "Plan gratuito del modelo"). En P02,
  el veredicto del modelo es estable en 12 de 15 corridas sobre la misma entrada ("con
  límites"; las otras 3, "no"): 8 de 10 en las dos series con el tope de 3000 y 4 de 5 en la
  de 3800. El bloque determinista no depende de eso: B4 salió en las 10 corridas en que
  estaba activo. P01 dio "con límites" en 10 de 10, con la preexistencia en "podrían
  aplicar" y nunca como exclusión que aplica. Ninguna de las 10 corridas con el tope de 3800
  abrió con "Sí" o "No" contra el veredicto. Medido en
  [`pruebas/estabilidad.md`](pruebas/estabilidad.md); las series anteriores, en
  `pruebas/estabilidad/039314c/` y `pruebas/estabilidad/sin_bloque/`.
- **Mencionadas pero ausentes:** se detectan las coberturas con código ("B4 - Nombre"), los
  anexos con letra o número ("Anexo A - Nombre") y las remisiones a Condiciones Particulares,
  Certificado de Seguro, Condiciones Especiales, Condiciones Generales y Tabla o Plan de
  Beneficios; cada una se compara con los títulos de cláusula y de artículo del PDF (un anexo
  cuenta también si una línea empieza con su encabezado, como "ANEXO A:" en Rimac). No se
  detecta una cobertura nombrada sin código, "endosos" o "anexos" sin nombre, ni una mención
  partida entre dos trozos. Revisado a mano en las tres pólizas: en Chubb solo B4 queda
  ausente entre las coberturas con código. Las remisiones a Condiciones Particulares y al
  Certificado salen en casi todas las respuestas de Chubb y Pacífico; por eso van plegadas
  debajo de las cláusulas con nombre propio.
- **Dónde atenderte:** son los establecimientos registrados en SUSALUD (RENIPRESS), no la
  red de ninguna aseguradora, y la app lo dice debajo del mapa. Corte del 30-10-2026, solo
  los 27 017 establecimientos en estado activo; 6977 de ellos (26 %) no tienen coordenadas
  válidas en el registro y salen en la lista pero no en el mapa (en Tarapoto, 26 de 148).
  No se usa la ubicación de la persona: elige departamento y distrito. Para actualizarlo,
  bajar el CSV del mes y correr `python -m ai.renipress --csv ... --corte ... --url ...`
  (la procedencia queda en [`data/renipress/fuente.json`](data/renipress/fuente.json)).
- **Cuota diaria del plan gratuito:** 200 000 tokens por día para `gpt-oss-120b`, que se
  reponen de a poco (unos 8300 por hora; Groq no lo informa en las cabeceras, solo en el
  mensaje del 429). Desde el balde lleno alcanzan para unas 28 preguntas nuevas o 40
  ensayadas, y cuando se agota la app muestra la red de seguridad. Pasó durante el
  desarrollo: tras un día de pruebas quedaban 1907 tokens y la medición de P01 y P02 tuvo
  que esperar la reposición entre intento e intento. Para la demo: llegar con la cuota
  descansada y dejar unos 35 s entre P01 y P02 (el límite por minuto; la app espera como
  mucho 8 s y si no, muestra la red de seguridad).
- **Caché de normalizaciones:** solo contiene preguntas públicas de ensayo y de prueba
  (`data/demo/`, `pruebas/`), generadas en local con `python -m ai.preparar_demo`. La app
  la lee, nunca escribe en ella.
- **Estructura heurística:** secciones y artículos se reconocen con patrones de los
  condicionados peruanos ("Cláusula Adicional", "Artículo N°", "PARTE B", numerales). Una
  póliza con otro formato puede quedar con trozos por página sin artículo.

## Próximos pasos

Tres cosas que hoy no se pueden hacer:

- **Red de la aseguradora:** hoy el mapa usa RENIPRESS, que es el registro de todos los
  establecimientos del país. Saber en cuáles te atienden con tu póliza requiere un convenio
  con cada compañía; esa lista no es dato público.
- **Entrada por voz:** preguntar con una nota de audio desde el celular, con Whisper. Es el
  caso de uso natural, porque el momento de la duda es cuando ya estás enfermo y fuera de
  casa.
- **API de embeddings:** hoy uso BM25 porque el modelo de embeddings no entra en la memoria
  del plan gratuito de Streamlit. Con una API de embeddings se resuelve por centavos.

## Licencia

[MIT](LICENSE).

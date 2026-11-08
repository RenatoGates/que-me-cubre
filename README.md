# ¿Qué me cubre?

> Subes el PDF de tu póliza, preguntas en español normal y te responde citando la
> cláusula exacta, con artículo y página.

Proyecto final de la Diplomatura de Ciencia de Datos (Q-Lab PUCP), curso de Ciencia de
Datos con Python. Enunciado: [d2cml-ai/Data-Science-Python#204](https://github.com/d2cml-ai/Data-Science-Python/issues/204).

> **Aviso.** Esta herramienta es informativa. La decisión final sobre la cobertura la
> toma la aseguradora.
>
> **Privacidad.** El PDF que subes se procesa en memoria: no se guarda en disco, ni en
> logs, ni en ningún estado persistente. Las consultas no se registran. Para redactar la
> respuesta, tu pregunta y los fragmentos de la póliza que encontré (no el PDF entero) se
> envían al proveedor del modelo: Groq, con retención cero de datos activada.

---

## 1. One-liner

*Borrador, por confirmar:* Hacemos que cualquier asegurado sepa qué le cubre su póliza,
para viajeros y familias en el Perú, mediante una IA que responde solo con las cláusulas
de su propio PDF y cita artículo y página.

## 2. Founder

Pendiente.

## 3. Problema

Pendiente: quién lo sufre, cuánto le cuesta y cómo lo resuelve hoy.

Evidencia: notas de 3 conversaciones con usuarios potenciales en [`docs/research/`](docs/research/).

## 4. Solución e insight

Pendiente.

## 5. Why now

Pendiente.

## 6. Demo

- **URL pública:** pendiente (Streamlit Community Cloud).
- **Capturas:** pendiente (`docs/`).
- **Diagrama de arquitectura:** pendiente (`docs/`).
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
2. **Debajo, el texto del modelo como explicación** de las condiciones y los límites. El
   prompt le pide no empezar con "Sí" ni con "No". Si aun así abre contradiciendo el
   veredicto, no se borra nada: queda marcado en `apertura_contradictoria`, se lista en la
   auditoría y la etiqueta de arriba sigue mandando.
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

App: pendiente.

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

Pendiente: quién paga y precio concreto.

**Costo por consulta hoy: USD 0.** El modelo corre en el plan gratuito de Groq y la app en
el plan gratuito de Streamlit Community Cloud, ninguno de los dos cobra por token ni por
hora. Lo que se cede a cambio es capacidad: el plan gratuito limita peticiones y tokens por
minuto y por día. Cada consulta hace dos llamadas al modelo (normalizar y responder); las
preguntas ensayadas tienen la normalización en una caché versionada y gastan una sola.

Tokens por consulta medidos en las 10 preguntas ([`pruebas/resultados.md`](pruebas/resultados.md)):
la respuesta gasta en promedio 6583 (entre 5631 y 7421: unos 4770 de entrada, casi todo
pasajes, y 1813 de salida, de la que el 71 % es razonamiento del modelo); la normalización,
unos 950 más. Una pregunta nueva gasta en promedio 7541. La normalización anclada cuesta
más, entre 1925 y 2095 tokens, porque lleva en la entrada la lista de títulos del documento.

El límite que pesa es el de **8000 tokens por minuto**. Medido con las cabeceras de Groq:
funciona como un balde que se rellena a 133 tokens por segundo; una llamada entra si quedan
libres más o menos los tokens de su entrada (Groq pidió 5428 para una entrada de 5040, sin
contar el máximo de salida) y después se descuenta lo que gastó de verdad. Con estas cifras,
5 consultas seguidas necesitan una cada 46 s si están en la caché y una cada 54 s si son
nuevas.

Por eso la app manda 5 pasajes al modelo en vez de unos 10 (opción A de
[`pruebas/opciones.md`](pruebas/opciones.md)): 5 consultas en la caché entran una cada 28 a
34 s. Medido después en la corrida completa con 5 pasajes: la respuesta gasta en promedio
4998 tokens (entre 3693 y 5849) y una pregunta nueva, con la normalización anclada, 6998. Se midieron también respuestas más cortas
(menos razonamiento: más barato, pero dos veredictos de diez empeoran) y `gpt-oss-20b`
(mismo tope de 8000 por minuto, y Groq le cuenta el máximo de salida dentro de lo pedido,
así que algunas consultas se rechazan aun con el balde lleno). Scripts:
[`pruebas/medir_cuota.py`](pruebas/medir_cuota.py) (tokens y cabeceras de una consulta),
[`pruebas/simular_cuota.py`](pruebas/simular_cuota.py) (el límite por minuto) y
[`pruebas/comparar_opciones.py`](pruebas/comparar_opciones.py) (las opciones de recorte).

## 8. Herramientas del curso

| Herramienta | Sesión | Dónde está en el código |
|---|---|---|
| Document AI: extraer el texto del PDF conservando página y artículo | 10 | [`ai/extraccion.py`](ai/extraccion.py): texto por página con pdfplumber, detección de dos columnas, limpieza de membretes, secciones y artículos |
| LLM con salidas estructuradas y RAG | 08 | Troceado por artículo en [`ai/troceado.py`](ai/troceado.py); índice en [`ai/indice.py`](ai/indice.py); prompts y esquemas JSON en [`ai/prompts.py`](ai/prompts.py); proveedor del LLM detrás de una interfaz en [`ai/llm.py`](ai/llm.py); recuperación BM25 multiconsulta en [`ai/recuperacion.py`](ai/recuperacion.py); flujo y validación de citas en [`ai/respuesta.py`](ai/respuesta.py) y [`ai/verificacion.py`](ai/verificacion.py) |

## 9. Qué hizo el agente

Pendiente.

---

## Estructura del repositorio

```
que-me-cubre/
├── app/          app de Streamlit (y su requirements.txt)
├── ai/           normalización, troceado, recuperación, prompts y respuesta estructurada
├── data/
│   ├── polizas/  condicionados públicos de prueba (se versionan)
│   └── privado/  pólizas personales para pruebas locales (ignorado por git)
├── docs/         arquitectura, capturas y research/ con las 3 conversaciones
└── notebooks/    exploración
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
  modelo no logra un JSON que cumpla el esquema (Groq lo rechaza con `json_validate_failed`;
  ocurrió en 1 de unas 30 llamadas con `gpt-oss-120b`). Si el límite llega en la
  normalización de una pregunta nueva, la búsqueda usa la pregunta tal cual y es menos
  precisa (en las pruebas, BM25 con la pregunta original acierta 4 de 9 con 8 pasajes).
- **Resultados de las pruebas:** 9 de 10 veredictos aceptables
  ([`pruebas/resultados.md`](pruebas/resultados.md)), con el código de la corrida del
  2026-11-08 (commit 039314c). Después se cambió el prompt para que la respuesta no escriba
  el veredicto, y eso no se volvió a medir. P10 queda en "no encontrado" porque el filtro
  suave dejó su artículo en el puesto 11 (ver el punto siguiente). Las 20 citas mostradas
  están literales en su página y las 23 menciones del bloque de ausentes también
  ([`pruebas/verificacion_citas.md`](pruebas/verificacion_citas.md)). Con 5 pasajes, BM25
  con variantes trae el artículo esperado en 7 de 9
  ([`pruebas/recuperacion.md`](pruebas/recuperacion.md)). Una llamada cayó en la red de
  seguridad y salió al reintentar. En esa corrida y en las cinco de P01, el modelo abrió 4
  veces con "Sí" y veredicto "con límites"; el código de entonces recortaba esa oración
  (P01 perdió su frase principal y P09 quedó sin texto propio), y por eso ahora se marca en
  vez de recortar. La corrida anterior (8 pasajes, normalización v1) había dado 6 de 10.
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
  responder distinto a la misma entrada. En P02, el veredicto del modelo es estable en 8 de
  10 corridas sobre la misma entrada ("con límites"; las otras 2, "no"); el bloque
  determinista no depende de eso: B4 salió en las 5 corridas en que estaba activo. P01 dio
  "con límites" en 5 de 5, con la preexistencia en "podrían aplicar" y nunca afirmada. Medido en
  [`pruebas/estabilidad.md`](pruebas/estabilidad.md) (la primera serie de P02, sin el bloque,
  en `pruebas/estabilidad/sin_bloque/`).
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
- **Caché de normalizaciones:** solo contiene preguntas públicas de ensayo y de prueba
  (`data/demo/`, `pruebas/`), generadas en local con `python -m ai.preparar_demo`. La app
  la lee, nunca escribe en ella.
- **Estructura heurística:** secciones y artículos se reconocen con patrones de los
  condicionados peruanos ("Cláusula Adicional", "Artículo N°", "PARTE B", numerales). Una
  póliza con otro formato puede quedar con trozos por página sin artículo.

## Licencia

[MIT](LICENSE).

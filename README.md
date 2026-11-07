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
| Normalizar la pregunta en 3-5 variantes | `openai/gpt-oss-120b` en Groq | Traduce "me torcí el dedo" a "accidente, lesión, gastos médicos, atención de urgencia" |
| Buscar los pasajes | BM25 sobre las variantes (sin modelo) | Ver la decisión de memoria abajo |
| Redactar la respuesta JSON con citas | `openai/gpt-oss-120b` en Groq | Salida con esquema JSON estricto; las citas se verifican después contra el PDF |

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
devuelve una frase sino de 3 a 5 variantes con los sinónimos del seguro, y los rankings se
combinan. Comparación medida en las 10 preguntas de prueba: pendiente
(`pruebas/evaluar_recuperacion.py`).

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
Tokens por consulta medidos: pendiente (`pruebas/resultados.md`).

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
  alcanzan, la app muestra las cláusulas encontradas sin texto generado. Si el límite llega
  en la normalización de una pregunta nueva, la búsqueda usa la pregunta tal cual y es
  menos precisa (en las pruebas, BM25 con la pregunta original acierta 4 de 9).
- **Caché de normalizaciones:** solo contiene preguntas públicas de ensayo y de prueba
  (`data/demo/`, `pruebas/`), generadas en local con `python -m ai.preparar_demo`. La app
  la lee, nunca escribe en ella.
- **Estructura heurística:** secciones y artículos se reconocen con patrones de los
  condicionados peruanos ("Cláusula Adicional", "Artículo N°", "PARTE B", numerales). Una
  póliza con otro formato puede quedar con trozos por página sin artículo.

## Licencia

[MIT](LICENSE).

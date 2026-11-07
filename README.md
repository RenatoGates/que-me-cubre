# ¿Qué me cubre?

> Subes el PDF de tu póliza, preguntas en español normal y te responde citando la
> cláusula exacta, con artículo y página.

Proyecto final de la Diplomatura de Ciencia de Datos (Q-Lab PUCP), curso de Ciencia de
Datos con Python. Enunciado: [d2cml-ai/Data-Science-Python#204](https://github.com/d2cml-ai/Data-Science-Python/issues/204).

> **Aviso.** Esta herramienta es informativa. La decisión final sobre la cobertura la
> toma la aseguradora.
>
> **Privacidad.** El PDF que subes se procesa en memoria: no se guarda en disco, ni en
> logs, ni en ningún estado persistente. Las consultas no se registran.

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
- **Modelos y por qué:** pendiente.

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

Pendiente: quién paga, precio concreto y costo por consulta en tokens y servidor.

## 8. Herramientas del curso

| Herramienta | Sesión | Dónde está en el código |
|---|---|---|
| Document AI: extraer el texto del PDF conservando página y artículo | 10 | [`ai/extraccion.py`](ai/extraccion.py): texto por página con pdfplumber, detección de dos columnas, limpieza de membretes, secciones y artículos |
| LLM con salidas estructuradas y RAG | 08 | Troceado por artículo en [`ai/troceado.py`](ai/troceado.py); índice BM25 y embeddings en [`ai/indice.py`](ai/indice.py); normalización, recuperación y respuesta JSON: pendiente |

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
- **Embeddings fuera de la app:** e5-small con torch ocupa unos 1,2 GB de RAM (medido en
  Windows, pico de 1,4 GB), por encima del presupuesto de 1 GB. La app recupera con BM25
  sobre la pregunta normalizada. Los embeddings se calculan en la ingesta.
- **Estructura heurística:** secciones y artículos se reconocen con patrones de los
  condicionados peruanos ("Cláusula Adicional", "Artículo N°", "PARTE B", numerales). Una
  póliza con otro formato puede quedar con trozos por página sin artículo.

## Licencia

[MIT](LICENSE).

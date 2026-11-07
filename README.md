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

Pendiente.

## 7. Modelo de negocio

Pendiente: quién paga, precio concreto y costo por consulta en tokens y servidor.

## 8. Herramientas del curso

| Herramienta | Sesión | Dónde está en el código |
|---|---|---|
| Document AI: extraer el texto del PDF conservando página y artículo | 10 | pendiente |
| LLM con salidas estructuradas y RAG | 08 | pendiente |

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

Pendiente.

## Licencia

[MIT](LICENSE).

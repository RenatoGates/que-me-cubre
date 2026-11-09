# Arquitectura

Una consulta, de la pregunta a la pantalla, y la pestaña del mapa. Lo que hace el modelo
está en naranja; todo lo demás es código, incluida la verificación de cada cita contra el
PDF. La app corre en Streamlit Community Cloud ([queqbre.streamlit.app](https://queqbre.streamlit.app/)).
Versión en imagen: [`arquitectura.png`](arquitectura.png).

```mermaid
flowchart TD
    subgraph Antes["Antes, en local"]
        ING["python -m ai.ingesta<br/>condicionados públicos → data/indices/"]
        PREP["python -m ai.preparar_demo<br/>normalización de las preguntas de ensayo → data/cache/"]
    end

    subgraph App["App: app/app.py, pestaña «Pregunta a tu póliza»"]
        PDF["PDF de la póliza: de ejemplo, o subido en uno o varios archivos<br/>(ai/subida.py: un solo documento, solo en memoria;<br/>cada cita dice de qué archivo sale)"]
        EXT["Extracción (ai/extraccion.py, pdfplumber)<br/>texto, página, sección y artículo"]
        TRO["Troceado por artículo (ai/troceado.py)<br/>con la posición de cada página"]
        IDX["Índice (ai/indice.py)<br/>BM25, títulos del documento"]
        AUS["Referencias ausentes (ai/referencias.py)<br/>B4, Condiciones Particulares…: se calcula una vez"]
        PREG["Pregunta en lenguaje común"]
        CACHE{"¿Normalización<br/>en la caché?"}
        NORM["Normalizar: elige cláusulas del índice<br/>y escribe 3-5 variantes<br/>(tope 1200 tokens, razonamiento bajo)"]
        REC["Búsqueda (ai/recuperacion.py)<br/>BM25 multiconsulta + RRF, filtro suave por cláusula → 5 pasajes"]
        RESP["Responder: JSON con esquema estricto<br/>veredicto, citas, condiciones, podrían aplicar<br/>(tope 3800 tokens, razonamiento medio)"]
        VER["Validación (ai/respuesta.py, ai/verificacion.py)<br/>cada cita literal en su pasaje y en su página del PDF (2 lectores)<br/>texto libre sin referencias que no estén citadas<br/>apertura contra el veredicto: se marca"]
        BLO["Bloque determinista<br/>lo mencionado pero ausente en los 5 pasajes, con página"]
        RED["Red de seguridad, sin reintento<br/>cláusulas encontradas, resaltadas, «Sin veredicto»"]
        LOG["Logs de la app (stderr, Manage app)<br/>tarea, código y mensaje de Groq;<br/>nunca la pregunta ni la póliza"]
        UI["Pantalla<br/>1 veredicto: campo estructurado<br/>2 explicación del modelo<br/>3 ausentes: B4 resaltado, remisiones plegadas<br/>4 citas desplegables<br/>5 podrían aplicar"]
    end

    subgraph Tab2["Pestaña «Dónde atenderte»"]
        MAPA["ai/renipress.py<br/>departamento y distrito → establecimientos activos<br/>en mapa y lista; sin modelo ni ubicación"]
    end

    RENI["RENIPRESS de SUSALUD<br/>datosabiertos.gob.pe → data/renipress/"]

    ING -.-> IDX
    PREP -.-> CACHE
    PDF --> EXT --> TRO --> IDX
    IDX --> AUS
    PREG --> CACHE
    CACHE -- sí --> REC
    CACHE -- no --> NORM --> REC
    IDX --> REC
    REC --> RESP --> VER --> UI
    REC --> BLO
    AUS --> BLO --> UI
    RESP -. "límite, error o JSON inválido" .-> RED --> UI
    NORM -. "límite o error" .-> RED
    RED -.-> LOG
    RENI -.-> MAPA

    classDef modelo fill:#ffe3c2,stroke:#d9822b,color:#3b2405
    class NORM,RESP modelo
```

**Qué sale de la app.** Solo la pregunta y los 5 pasajes recuperados (no el PDF entero),
hacia Groq (`openai/gpt-oss-120b`, retención cero de datos activada en la cuenta). Una
pregunta de ensayo hace una llamada (la normalización está en la caché); una nueva, dos.
Si una llamada falla, la app no reintenta: muestra la red de seguridad y deja en sus logs
una línea con la tarea, el código y el mensaje de Groq, sin la pregunta ni la póliza.

**La pestaña del mapa** no toca el modelo ni la ubicación de la persona: filtra por
departamento y distrito el registro de establecimientos activos de RENIPRESS (SUSALUD,
datos abiertos), preparado una vez con `python -m ai.renipress` y versionado en
`data/renipress/`.

**Qué no depende del modelo.** La extracción con página y artículo, la búsqueda, la
verificación de cada cita contra el PDF, el bloque de lo mencionado pero ausente y el
veredicto que se muestra (es el campo estructurado, no el texto). Lo que sí es del modelo:
elegir las cláusulas y las variantes de búsqueda, y redactar la respuesta y su conclusión,
que la verificación no garantiza (ver Limitaciones en el README).

## Capturas

Tomadas el 2026-11-09 de la app desplegada ([queqbre.streamlit.app](https://queqbre.streamlit.app/)),
con respuestas en vivo de Groq (`openai/gpt-oss-120b`), con
`python pruebas/capturas.py --url https://queqbre.streamlit.app --espera 45`. El script deja pasar
el límite por minuto entre las dos preguntas y se detiene sin guardar si una respuesta sale sin
veredicto o sin el bloque de B4: el primer intento de P02 cayó en la red de seguridad (respuesta
sin el formato esperado) y se descartó; estas son del segundo.

1. Inicio: los tres pasos de cómo funciona; arriba, subir el PDF de la póliza (uno o varios
   archivos); debajo, en letra chica, los condicionados de ejemplo; la pregunta con "Una
   pregunta a la vez." y los dos ejemplos de Tarapoto, que solo aparecen con la póliza de Chubb.

   ![Inicio](capturas/1_inicio.png)

2. La radiografía al llegar a Lima (P02): "Cubre con límites" arriba, B4 resaltado con su
   página, las remisiones plegadas y tres citas. Esta vez la explicación salió corta y el
   modelo puso la exclusión de exámenes de rutina entre las que aplican, aunque la radiografía
   la indicó un médico: es el hueco de la conclusión que se describe en Limitaciones.

   ![Respuesta a la radiografía](capturas/2_respuesta_radiografia.png)

3. La torcedura en Tarapoto (P01): "Cubre con límites", B4 y una cita desplegada con su texto
   literal, su página y la verificación contra el PDF.

   ![Respuesta a la torcedura con citas](capturas/3_respuesta_torcedura_citas.png)

4. Dónde atenderte, en Tarapoto: los establecimientos activos de RENIPRESS en el mapa y en
   la lista, con el aviso de que no son la red de la aseguradora. No usa el modelo.

   ![Dónde atenderte en Tarapoto](capturas/4_donde_atenderte.png)

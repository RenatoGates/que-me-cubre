# Arquitectura

Una consulta, de la pregunta a la pantalla. Lo que hace el modelo está en naranja; todo lo
demás es código, incluida la verificación de cada cita contra el PDF. La app corre en
Streamlit Community Cloud. Versión en imagen: [`arquitectura.png`](arquitectura.png).

```mermaid
flowchart TD
    subgraph Antes["Antes, en local"]
        ING["python -m ai.ingesta<br/>condicionados públicos → data/indices/"]
        PREP["python -m ai.preparar_demo<br/>normalización de las preguntas de ensayo → data/cache/"]
    end

    subgraph App["App: app/app.py"]
        PDF["PDF de la póliza<br/>precargado, o subido: solo en la memoria de la sesión"]
        EXT["Extracción (ai/extraccion.py, pdfplumber)<br/>texto, página, sección y artículo"]
        TRO["Troceado por artículo (ai/troceado.py)<br/>con la posición de cada página"]
        IDX["Índice (ai/indice.py)<br/>BM25, títulos del documento"]
        AUS["Referencias ausentes (ai/referencias.py)<br/>B4, Condiciones Particulares…: se calcula una vez"]
        PREG["Pregunta en lenguaje común"]
        CACHE{"¿Normalización<br/>en la caché?"}
        NORM["Normalizar: elige cláusulas del índice<br/>y escribe 3-5 variantes"]
        REC["Búsqueda (ai/recuperacion.py)<br/>BM25 multiconsulta + RRF, filtro suave por cláusula → 5 pasajes"]
        RESP["Responder: JSON con esquema estricto<br/>veredicto, citas, condiciones, podrían aplicar"]
        VER["Validación (ai/respuesta.py, ai/verificacion.py)<br/>cada cita literal en su pasaje y en su página del PDF (2 lectores)<br/>texto libre sin referencias que no estén citadas<br/>apertura contra el veredicto: se marca"]
        BLO["Bloque determinista<br/>lo mencionado pero ausente en los 5 pasajes, con página"]
        RED["Red de seguridad<br/>cláusulas encontradas, resaltadas, sin veredicto"]
        UI["Pantalla<br/>1 veredicto: campo estructurado<br/>2 explicación del modelo<br/>3 ausentes: B4 resaltado, remisiones plegadas<br/>4 citas desplegables<br/>5 podrían aplicar"]
        MAPA["Dónde atenderte (ai/renipress.py)<br/>departamento y distrito → establecimientos activos<br/>en mapa y lista; sin modelo ni ubicación"]
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
    RENI -.-> MAPA

    classDef modelo fill:#ffe3c2,stroke:#d9822b,color:#3b2405
    class NORM,RESP modelo
```

**Qué sale de la app.** Solo la pregunta y los 5 pasajes recuperados (no el PDF entero),
hacia Groq (`openai/gpt-oss-120b`, retención cero de datos activada en la cuenta). Una
pregunta de ensayo hace una llamada (la normalización está en la caché); una nueva, dos.

**Qué no depende del modelo.** La extracción con página y artículo, la búsqueda, la
verificación de cada cita contra el PDF, el bloque de lo mencionado pero ausente y el
veredicto que se muestra (es el campo estructurado, no el texto). Lo que sí es del modelo:
elegir las cláusulas y las variantes de búsqueda, y redactar la respuesta y su conclusión,
que la verificación no garantiza (ver Limitaciones en el README).

## Capturas

Tomadas con `python pruebas/capturas.py` sobre la app en local con el proveedor de maqueta
(`QMC_PROVEEDOR=grabado`): la respuesta del modelo es la que ya dio para esa pregunta en
`pruebas/salidas/`, y todo lo demás (búsqueda, verificación de citas, bloque de ausentes,
interfaz) corrió de verdad. Por eso el aviso de arriba dice "Respuesta grabada" en vez de
Groq. Se reemplazan por capturas de la app desplegada cuando se pruebe en vivo.

1. Inicio: póliza, pregunta y los dos casos reales de Tarapoto como botones.

   ![Inicio](capturas/1_inicio.png)

2. La radiografía al llegar a Lima (P02): veredicto arriba, explicación, B4 resaltado con su
   página y las remisiones plegadas.

   ![Respuesta a la radiografía](capturas/2_respuesta_radiografia.png)

3. La torcedura en Tarapoto (P01): una cita desplegada con su texto literal y página, y la
   preexistencia en "exclusiones que podrían aplicar según tu caso". El texto grabado abre
   con "Sí,": quedó marcado y la etiqueta de arriba, "Cubre con límites", es la que manda.

   ![Respuesta a la torcedura con citas](capturas/3_respuesta_torcedura_citas.png)

4. Dónde atenderte, en Tarapoto: los establecimientos activos de RENIPRESS en el mapa y en
   la lista, con el aviso de que no son la red de la aseguradora. No usa el modelo.

   ![Dónde atenderte en Tarapoto](capturas/4_donde_atenderte.png)

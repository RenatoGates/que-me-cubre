# Pruebas de usuario

- Fecha: 9 de noviembre de 2026.
- Qué se probó: la app desplegada ([queqbre.streamlit.app](https://queqbre.streamlit.app/)).
- Quiénes: dos personas, anonimizadas (sin nombres ni datos personales).

## Usuario A, el del caso de Tarapoto

La app respondió correctamente que podía recuperar el dinero y le dio los pasos para
reclamar.

**Problema encontrado:** su póliza venía en dos PDF y solo se podía subir uno.

## Usuaria B

La app resolvió su duda, pero no habría entendido cómo usarla sin que se lo explicaran, y le
pareció lenta.

## Tercer hallazgo

Al hacer dos preguntas en un mismo texto, solo se responde la primera.

## Qué se cambió

| Hallazgo | Cambio en la app |
|---|---|
| La póliza venía en dos PDF | Se pueden subir varios archivos a la vez; se leen como un solo documento y cada cita, pasaje y mención dice de qué archivo sale y en qué página de ese archivo ([`ai/subida.py`](../../ai/subida.py)) |
| Sin explicación no se entiende cómo usarla | Debajo del título, tres pasos de "cómo funciona"; arriba y destacado "Sube el PDF de tu póliza", y debajo, en letra chica, los condicionados de ejemplo para quien no tiene uno a mano |
| Le pareció lenta | Mientras trabaja, un mensaje de avance dice en qué paso va: entender la pregunta, buscar en la póliza, redactar y verificar las citas. Leer un PDF largo avisa que puede tardar medio minuto |
| Dos preguntas juntas, solo se responde la primera | Debajo de la caja de pregunta: "Una pregunta a la vez." Queda en las limitaciones del README |

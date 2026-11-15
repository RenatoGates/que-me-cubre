# Arranque y memoria de la API

Generado por `pruebas/medir_arranque.py` en Windows 10, Python 3.11.9, sin embeddings y sin llamar al modelo. Es esta máquina, no Render: el arranque en frío del servidor desplegado se mide con `--url` cuando esté desplegado.

- Arranque hasta que `/salud` responde: 4.2 s.
- Subir e indexar una póliza de 62 páginas (extracción, troceado e índice, sin embeddings): 16.9 s.

| Momento | Memoria residente |
|---|---:|
| al arrancar | 169 MB |
| con los condicionados precargados en memoria | 183 MB |
| con el registro de RENIPRESS cargado | 199 MB |
| después de subir una póliza de 62 páginas | 214 MB |

El plan gratuito de Render da 512 MB: lo más alto medido al terminar cada paso es 214 MB.

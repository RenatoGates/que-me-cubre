# Contraste de la paleta clara

Generado por `pruebas/medir_contraste.py` con los colores de `movil/lib/tema.dart` (los mismos de la web, `.streamlit/config.toml`).

| Uso | Texto | Fondo | Contraste | Mínimo WCAG | Cumple |
|---|---|---|---:|---:|---|
| Texto principal sobre el fondo crema | #2E2620 | #FBF7F2 | 13.92:1 | 4.5:1 | sí |
| Texto principal sobre tarjetas | #2E2620 | #FFFFFF | 14.85:1 | 4.5:1 | sí |
| Texto citado sobre su bloque de cita | #2E2620 | #F3EDE4 | 12.76:1 | 4.5:1 | sí |
| Texto secundario sobre el fondo crema | #7A6E62 | #FBF7F2 | 4.65:1 | 4.5:1 | sí |
| Texto secundario sobre tarjetas | #7A6E62 | #FFFFFF | 4.96:1 | 4.5:1 | sí |
| Enlaces y botones de texto sobre el fondo crema | #2D6BE5 | #FBF7F2 | 4.53:1 | 4.5:1 | sí |
| Enlaces y botones de texto sobre tarjetas | #2D6BE5 | #FFFFFF | 4.83:1 | 4.5:1 | sí |
| Texto blanco de los botones principales (y la banda de la web) | #FFFFFF | #2D6BE5 | 4.83:1 | 4.5:1 | sí |
| Veredicto «Cubre» sobre el fondo crema | #1E7A4D | #FBF7F2 | 4.99:1 | 4.5:1 | sí |
| Veredicto «Cubre» sobre tarjetas | #1E7A4D | #FFFFFF | 5.32:1 | 4.5:1 | sí |
| Veredicto «Cubre con límites» y su límite sobre el fondo crema | #A36200 | #FBF7F2 | 4.57:1 | 4.5:1 | sí |
| Veredicto «Cubre con límites» y su límite sobre tarjetas | #A36200 | #FFFFFF | 4.88:1 | 4.5:1 | sí |
| Veredicto «No cubre» sobre el fondo crema | #C0392B | #FBF7F2 | 5.10:1 | 4.5:1 | sí |
| Veredicto «No cubre» sobre tarjetas | #C0392B | #FFFFFF | 5.44:1 | 4.5:1 | sí |
| Descargo del martillo (ámbar) y «se borra el…» | #A36200 | #FFFFFF | 4.88:1 | 4.5:1 | sí |
| Avisos (snackbar): blanco sobre texto oscuro | #FFFFFF | #2E2620 | 14.85:1 | 4.5:1 | sí |
| Etiqueta «bloqueado» de la web sobre su fondo | #2E2620 | #F3EDE4 | 12.76:1 | 4.5:1 | sí |
| Atribución de OpenStreetMap sobre su recuadro blanco | #2E2620 | #FFFFFF | 14.85:1 | 4.5:1 | sí |
| Web: texto de los avisos amarillos sobre su fondo | #9A5C00 | #FBF1E1 | 4.81:1 | 4.5:1 | sí |

- **19 de 19 pares cumplen.**

## Colores ajustados

| Par original | Texto | Fondo | Contraste |
|---|---|---|---:|
| «Con límites» pedido #B06A00 sobre tarjetas | #B06A00 | #FFFFFF | 4.28:1 |
| «Con límites» pedido #B06A00 sobre el fondo crema | #B06A00 | #FBF7F2 | 4.01:1 |
| Web: #A36200 en los avisos amarillos (pasó a #9A5C00 solo ahí) | #A36200 | #FBF1E1 | 4.36:1 |

«Con límites» pasó de #B06A00 a #A36200, un ámbar algo más oscuro que llega a 4,5:1 sobre ambos fondos.

## Pares que no llegan y por eso no se usan

| Par | Texto | Fondo | Contraste |
|---|---|---|---:|
| Texto secundario sobre el bloque de cita | #7A6E62 | #F3EDE4 | 4.26:1 |
| Azul de enlaces sobre el bloque de cita | #2D6BE5 | #F3EDE4 | 4.15:1 |

Sobre el bloque de cita (#F3EDE4) va solo el texto citado, en el color principal; la verificación y el botón para abrir el PDF van debajo, sobre blanco.

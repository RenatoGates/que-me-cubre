# ¿Qué Cubre?

> Subes el PDF de tu póliza, preguntas en español normal y te responde citando la
> cláusula exacta, con artículo y página.

Proyecto final de la Diplomatura de Ciencia de Datos (Q-Lab PUCP), curso de Ciencia de
Datos con Python. Enunciado: [d2cml-ai/Data-Science-Python#204](https://github.com/d2cml-ai/Data-Science-Python/issues/204).

> **Aviso.** Esta herramienta es informativa. La decisión final sobre la cobertura la
> toma la aseguradora.
>
> **Privacidad.** Sin cuenta, nada se guarda: el PDF que subes se procesa en la memoria del
> servidor y se borra de ahí a los 60 minutos sin uso, al pedirlo o al reiniciarse el servidor.
> Con cuenta, y solo si eliges guardar la póliza, se guardan cifrados su texto, sus vectores
> y tus últimas 20 consultas; el archivo PDF no se guarda. La llave del cifrado está en el
> servidor de quien administra la app, que por lo tanto podría leer ese contenido. Salen hacia
> terceros el texto de la póliza (a Voyage AI, que calcula los vectores) y tu pregunta con los
> fragmentos encontrados (a Anthropic, que redacta la respuesta y borra lo recibido dentro de
> los 30 días). El detalle está en la [política de privacidad](https://renatogates.github.io/que-me-cubre/privacidad.html)
> (generada de [`docs/privacidad.md`](docs/privacidad.md)).
>
> **Regla de las citas.** Toda cita se verifica contra el texto de la página extraído del PDF con dos extractores independientes al momento de subirlo, o se descarta.

---

## Estado: Fase 1, backend propio

El prototipo era una app de Streamlit que corría todo adentro, con Groq gratuito y BM25. En
la rama `fase-1-backend` el mismo pipeline (extracción, búsqueda, verificación de citas y
detección de cláusulas ausentes: nada de eso se reescribió) quedó detrás de una API propia,
que es la que usará la app móvil. Todas las cifras salen de scripts de [`pruebas/`](pruebas/):

| Qué | Antes (prototipo) | Ahora | De dónde sale |
|---|---|---|---|
| Modelo | `gpt-oss-120b` en Groq gratuito | Claude Haiku 5.5 (Anthropic, de pago) | [`ai/llm.py`](ai/llm.py) |
| Veredictos aceptables al primer intento | 8 de 10 | **10 de 10** | [`pruebas/resultados.md`](pruebas/resultados.md) |
| Búsqueda | BM25 con variantes del modelo | Embeddings por API (Voyage) con la pregunta tal cual | [`pruebas/recuperacion.md`](pruebas/recuperacion.md) |
| Artículo esperado entre los 5 pasajes | 5 de 9 (BM25 con las variantes de Haiku) | **7 de 9** | [`pruebas/recuperacion.md`](pruebas/recuperacion.md) |
| Llamadas al modelo por pregunta nueva | 2 | 1 | [`pruebas/resultados.md`](pruebas/resultados.md) |
| Costo por consulta | USD 0 (con cuota por minuto) | USD 0,0016 en promedio | [`pruebas/resultados.md`](pruebas/resultados.md) |
| Espera por respuesta | sujeta a la cuota: una consulta cada ~36 s | 8,0 s en promedio, 14,1 s la más larga | [`pruebas/resultados.md`](pruebas/resultados.md) |
| Instrucciones escondidas en el PDF | sin defensa específica | no obedeció en 6 de 6 corridas | [`pruebas/inyeccion.md`](pruebas/inyeccion.md) |
| Preguntas fuera de alcance | se respondían | 6 de 6 reconocidas y cortadas | [`pruebas/alcance.md`](pruebas/alcance.md) |
| Condicionados precargados | Chubb, Pacífico, Rimac | más Mapfre e Interseguro | [`data/polizas/fuentes.json`](data/polizas/fuentes.json) |

El "antes" de 8 de 10 es la medición del prototipo con Groq (commit `6570fd9`). Con Haiku y
la búsqueda anterior, BM25, daba 9 de 10 ([`pruebas/resultados_bm25.md`](pruebas/resultados_bm25.md)).
Son 10 preguntas y una corrida por configuración: alcanza para ver la dirección, no para
afirmar una tasa.

Backend desplegado en Render (plan gratuito): <https://que-me-cubre-api.onrender.com>. Arranque en frío medido: 41,6 s ([`pruebas/arranque_render.md`](pruebas/arranque_render.md)); flujo completo contra esa URL en [`pruebas/desplegado.md`](pruebas/desplegado.md). Langfuse sigue apagado.

## Fase 2: las funciones que cambian el producto

En la rama `fase-2-funciones`. Medido con el modelo real en [`pruebas/fase2.md`](pruebas/fase2.md)
(una corrida por caso) y probado sin red en [`pruebas/probar_fase2.py`](pruebas/probar_fase2.py).

| Función | Qué hace | Medido |
|---|---|---|
| Repregunta | Si alguien escribe "me lesioné, ¿qué puedo hacer?", la app no busca ni adivina: pregunta qué pasó, dónde y cuándo. No gasta una consulta del día | Repregunta en 6 de 6 preguntas vagas y deja pasar 15 de 15 claras |
| Varias preguntas | Las separa y responde cada una con su propia búsqueda y sus propias citas (hasta 3; cada una cuenta como una consulta) | 5 de 5 textos separados en el número esperado |
| Qué hacer ahora | Plazo de aviso, a quién avisar, documentos y pasos, cada uno con su cita verificada | En los 5 condicionados encontró un plazo con su cita; entre 7,9 y 18,2 s y entre USD 0,0017 y 0,0033 |
| Alerta de plazo | La fecha límite, calculada por código desde la fecha del hecho | Chubb: 30 días; Pacífico y Mapfre: 7 días; Rimac: 24 y 48 horas, y 30 días para equipaje; Interseguro: 24 horas |
| Radiografía | Qué cubre, hasta cuánto, exclusiones, deducibles y carencias, con citas | Entre 3 y 8 coberturas por condicionado, 13 a 30 citas verificadas, USD 0,0024 a 0,0033 |
| ¿Pagas doble? | Con dos o más pólizas, coberturas que podrían superponerse | 6 posibles superposiciones entre Chubb, Pacífico y Rimac |
| Mapa con ubicación | Reemplaza a la red de clínicas del anexo, que se eliminó del alcance: centros de salud cercanos, con la ubicación de la persona o con su distrito | Ver "Mapa con ubicación", abajo |

**Qué decide el modelo y qué decide el código.** El modelo clasifica el texto (¿falta
información?, ¿cuántas preguntas?), y redacta pasos y resúmenes citando. El código verifica
cada cita contra el texto de su página, descarta lo que no tenga cita válida, acepta un plazo solo
si su número está escrito en su cita (en cifras o en palabras), lee la fecha del hecho del
texto ("ayer", "hace 3 días", "el 12 de noviembre") y calcula la fecha límite. Cuando el
plazo es en días hábiles no cuenta feriados, y lo dice; cuando la póliza no dice el tipo de
día, cuenta días calendario, que da la fecha más temprana, y lo dice.

**Mapa con ubicación** ([`app/mapa_cercano.html`](app/mapa_cercano.html)). Todo corre en el
navegador. El mapa pide la ubicación solo si la persona toca "Usar mi ubicación"; si la
niega, sigue con el distrito elegido. Muestra de inmediato los hospitales y clínicas con
internamiento más cercanos del registro de SUSALUD (1054 con coordenadas en todo el país;
la cercanía se calcula en el navegador con esa lista) y, si OpenStreetMap responde, los
reemplaza por las clínicas y hospitales de OpenStreetMap vía Overpass. Arriba, siempre
visible: "Estos son centros de salud cercanos. NO verificamos si están en la red de tu
póliza." La ubicación no se guarda, no pasa por el servidor de la app ni queda en registros:
solo viaja, como coordenadas, en la consulta a OpenStreetMap (Overpass y las imágenes del
mapa). Si el condicionado nombra clínicas literalmente ([`ai/clinicas.py`](ai/clinicas.py),
sin modelo), se marcan con una estrella y se muestra la cita verificada de donde sale el
nombre; si no nombra ninguna, esa sección no aparece. Probado en
[`pruebas/probar_mapa_portero.py`](pruebas/probar_mapa_portero.py).

**Portero de documento** ([`ai/portero.py`](ai/portero.py)). Al indexar, cuenta 16
marcadores de vocabulario de póliza en el texto, sin modelo. Si hay menos de 16 por cada mil
palabras, la app avisa "Esto no parece un condicionado de seguro. Puedo intentarlo igual,
pero las respuestas pueden no tener sentido." y deja continuar. Calibrado en
[`pruebas/portero.md`](pruebas/portero.md): clasificó bien 6 de 6 condicionados (entre 24,1
y 51,0 marcadores por mil palabras) y 3 de 3 documentos que no lo son (un boletín de SUSALUD
sobre las EPS, un contrato de tarjeta de crédito y la Constitución: entre 0,9 y 9,2).

**Un condicionado de otro ramo.** Además de los cinco de viaje, el pipeline se probó en
local con una póliza dental real de 18 páginas, que no está en el repositorio. Sirvió para
encontrar una falla: su PDF tiene un detalle de formato que el lector principal rechazaba,
así que la app respondía "no pude leer ese PDF". Ahora ese caso se repara reescribiendo el
PDF en memoria (`reparar` en [`ai/subida.py`](ai/subida.py)), y con eso sus preguntas de
prueba salieron con todas las citas verificadas por los dos lectores.

**Costo del paso nuevo.** El triage que detecta preguntas vagas o múltiples es una llamada
corta antes de cada consulta: USD 0,00014 y 1,9 s en promedio (2,4 s la más larga).


## Fase 3: cuentas, pólizas guardadas, historial y plan pagado

En la rama `fase-3-cuentas`. Probado sin red en [`pruebas/probar_cuentas.py`](pruebas/probar_cuentas.py)
y, la pantalla, en [`pruebas/probar_app.py`](pruebas/probar_app.py).

| Función | Resultado | Archivo |
|---|---|---|
| Entrar con Google | El backend verifica el ID token: firma con los certificados de Google, emisor, cliente, vencimiento y correo verificado. Rechaza el token de otro cliente, vencido, de otro emisor, sin correo verificado o con firma falsa. Probado con una llave y un certificado creados en la prueba; contra Google de verdad, todavía no | [`backend/acceso_google.py`](backend/acceso_google.py), [`backend/cuentas.py`](backend/cuentas.py) |
| Entrar con correo y contraseña | Opción secundaria; contraseña con hash scrypt. Sin recuperación ni proveedor de correo: «¿Olvidaste tu contraseña?» lleva a crear una cuenta nueva | [`backend/cuentas.py`](backend/cuentas.py), [`app/app.py`](app/app.py) |
| Consentimiento | Una casilla sin marcar, en una línea, con enlace a la política. Sin ella no se crea la cuenta, con correo ni con Google | [`backend/cuentas.py`](backend/cuentas.py), [`docs/privacidad.md`](docs/privacidad.md) |
| Guardar la póliza sin el PDF | Una póliza cargada de la base no tiene PDF y responde con las mismas citas y páginas que con él, todas verificadas por los dos extractores | [`backend/guardado.py`](backend/guardado.py), [`ai/verificacion.py`](ai/verificacion.py) |
| Cifrado | AES-256-GCM aplicado por la app; en la base no aparece texto de la póliza, de la pregunta ni la contraseña; un contenido no se descifra para otra cuenta | [`backend/guardado.py`](backend/guardado.py) |
| Póliza temporal (plan gratis) | Se borra a los 14 días; la fecha va en un indicador pequeño junto a la póliza. Adelantando el reloj: a los 13 días y 23 horas sigue; a los 14 días no queda ninguna fila suya | [`backend/guardado.py`](backend/guardado.py) (`purgar`) |
| Historial | Últimas 20 consultas por póliza, con su respuesta y sus citas verificadas; se borran una por una | [`backend/guardado.py`](backend/guardado.py) |
| Topes del plan gratis y sin cuenta | Sin cuenta, 3 al día y 10 al mes; cuenta gratis, 3 al día y 20 al mes. Corta el primero que se agote; el del mes dice cuándo se reinicia (el día 1, hora de Lima) | [`backend/main.py`](backend/main.py) (`tomar_una`), [`backend/limites.py`](backend/limites.py) |
| Bolsa del plan pagado | 200 consultas por pago, que no caducan (siguen ahí con el reloj adelantado 300 días). Una consulta descuenta 1; una radiografía nueva, 5, y volver a abrirla no cuesta. Freno de 20 al día aunque quede saldo. El saldo se ve en «Mi cuenta»; sin saldo se ofrece volver a comprar y se consulta con los topes del plan gratis | [`backend/pagos.py`](backend/pagos.py) |
| Radiografía | Del plan pagado. Cada cuenta gratis tiene una completa, igual a la del plan pagado; la base anota de qué póliza fue, así que otra sesión la ve usada. Si el modelo falla, la gratis no se pierde | [`backend/pagos.py`](backend/pagos.py) |
| ¿Pagas doble? | Del plan pagado; en el gratis se muestra bloqueada | [`backend/pagos.py`](backend/pagos.py), [`app/app.py`](app/app.py) |
| Cobro | Un solo punto para conectar Google Play Billing (`verificar_compra`); hoy `POST /cuenta/compra` responde 501. No hay activación a mano. Una misma compra no se acredita dos veces; otra compra suma otras 200 | [`backend/pagos.py`](backend/pagos.py) |
| Borrar la cuenta y todo | Pide la contraseña, o solo la sesión en una cuenta de Google; después no queda ninguna fila en ninguna tabla, ni sus contadores, y la sesión deja de servir | [`backend/guardado.py`](backend/guardado.py) (`borrar_todo`) |

**Qué desbloquea el pago.** Cada pago de S/ 3,99 (Google Play) suma 200 consultas que no
caducan, y la cuenta pasa al plan pagado: guarda hasta 4 pólizas sin borrado automático y
abre ¿Pagas doble? y todas las radiografías (5 consultas cada una). Para poder volver a
comprar, la app consume la compra en Play después de acreditarla. Gratis siguen la repregunta, varias preguntas, qué hacer
ahora, la alerta de plazo y el mapa. La versión web no vende: el plan pagado aparece como
disponible en la app de Android.

**Un solo módulo guarda contenido.** Todo lo que se guarda de una póliza o de una consulta
pasa por [`backend/guardado.py`](backend/guardado.py): si más adelante se guardan archivos,
se toca ese archivo. Las tablas (`usuarios`, `sesiones`, `polizas`, `consultas`) viven en la
misma base que los contadores (`DATABASE_URL`, Neon). La llave del cifrado es
`QMC_CLAVE_DATOS`; sin ella no se crean cuentas y lo demás funciona igual.

**Cómo se verifica sin el PDF.** Al subir una póliza, el texto de cada página se extrae con
pdfplumber y con pypdf y queda guardado junto al índice. Las citas se comparan contra ese
texto. Es lo mismo que antes se hacía reabriendo el PDF, hecho una sola vez.

**El borrado automático no depende de un reloj externo.** El servidor gratuito se duerme, así
que no hay tarea programada: la limpieza corre al arrancar y, como mucho una vez por hora,
al atender. Una póliza vencida no se entrega aunque la limpieza todavía no haya pasado.

**Costo de cada plan** ([`pruebas/planes.md`](pruebas/planes.md), generado por
[`pruebas/medir_planes.py`](pruebas/medir_planes.py) con los costos medidos y los límites del
código). Una consulta cuesta USD 0,00175 con el triage. Un pago deja S/ 3,39 (≈ USD 0,90)
después de la comisión de Google Play. Gastar la bolsa entera en consultas cuesta USD 0,351:
en el peor caso queda un margen de USD 0,55 por pago, y el costo es por pago, no por mes. El
uso realista (4 pólizas, 2 preguntas por póliza al mes) cuesta USD 0,014 al mes y la bolsa
dura 25 meses. Una cuenta gratis en su peor caso cuesta USD 0,035 al mes; 12 testers, USD 0,42.
El tope global se queda en USD 2,00.

### Activar el inicio de sesión con Google

En [Google Cloud Console](https://console.cloud.google.com/), gratis y sin dominio propio:

1. Crea un proyecto.
2. *Google Auth Platform > Branding*: nombre de la app «¿Qué Cubre?», tu correo de soporte y,
   como enlace de la política de privacidad, https://renatogates.github.io/que-me-cubre/privacidad.html
   (la página que GitHub Pages publica desde `docs/`; se genera de [`docs/privacidad.md`](docs/privacidad.md)
   con `python pruebas/generar_privacidad.py`).
3. *Audience*: tipo **External**. Mientras esté en «Testing» solo entran los correos que
   agregues como usuarios de prueba (hasta 100); para abrirla a todos, «Publish app». Con
   solo los alcances básicos no hace falta la verificación de Google.
4. *Data Access*: agrega solo `openid`, `.../auth/userinfo.email` y `.../auth/userinfo.profile`.
5. *Clients > Create client*, tipo **Web application**. En «Authorized redirect URIs» pon
   `https://queqbre.streamlit.app/oauth2callback` (y `http://localhost:8501/oauth2callback`
   para probar en local). Copia el **Client ID** y el **Client secret**.
6. En la Fase 4, otro cliente de tipo **Android** con el nombre del paquete y la huella SHA-1
   del certificado (la de depuración sale en Android Studio con `./gradlew signingReport`; la
   de producción, de Play Console > App signing). La app de Android usa el Client ID web como
   `serverClientId`, así que el backend no cambia.

En **Render** (Environment): `QMC_GOOGLE_CLIENT_IDS` = el Client ID web. El secreto no va en
Render: el backend solo verifica tokens.

En **Streamlit Cloud** (Settings > Secrets), si quieres el botón en la web:

```toml
[auth]
redirect_uri = "https://queqbre.streamlit.app/oauth2callback"
cookie_secret = "<una cadena al azar larga>"
client_id = "<Client ID web>"
client_secret = "<Client secret>"
server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"
expose_tokens = "id"
```

Sin la sección `[auth]` o sin `QMC_GOOGLE_CLIENT_IDS`, el botón no aparece y se entra con
correo.

## Fase 4: app de Android

En la rama `fase-4-android`. La app está en [`movil/`](movil) (Flutter, `com.renatogates.quecubre`) y consume el
backend; no decide coberturas, topes ni planes. Probada en una Samsung Galaxy Tab S7 FE (Android 14) con el APK de
lanzamiento (R8 activado) contra el backend en local.

| Función | Resultado medido | Archivo |
|---|---|---|
| Descargos | Junto a cada respuesta, pasos, radiografía y comparación, en letra normal; el de inicio, arriba de todo | [`movil/lib/textos.dart`](movil/lib/textos.dart), [`docs/ficha_play.md`](docs/ficha_play.md) |
| «Ver esta cláusula en tu póliza» | Abre el PDF dentro de la app, en la página de la cita (y en su archivo, si son varios). Ver las correcciones abajo | [`movil/lib/visor_pdf.dart`](movil/lib/visor_pdf.dart) |
| Regla de lenguaje | Sin consumo, contadores, modelos ni proveedores en pantalla; en la web lo revisa una prueba sobre 25 estados de la pantalla | [`app/app.py`](app/app.py), [`pruebas/probar_app.py`](pruebas/probar_app.py) |
| Dictado por voz | El reconocedor del propio Android (costo cero); el texto queda en el campo, editable, antes de preguntar | [`movil/lib/pantalla_poliza.dart`](movil/lib/pantalla_poliza.dart) |
| Google Play Billing | Verificación contra la Google Play Developer API (simulada en las pruebas): pagada, sin consumir y de esa cuenta; una compra se acredita una vez; sin sesión, 401 | [`backend/pagos.py`](backend/pagos.py), [`movil/lib/compras.dart`](movil/lib/compras.dart) |
| Seguridad entre cuentas | La cuenta B no lee, usa ni borra nada de A en 14 endpoints, ni por id directo; una póliza subida solo la usa el dispositivo que la subió | [`pruebas/probar_fase4.py`](pruebas/probar_fase4.py) |
| Caché | La misma pregunta (aunque cambien mayúsculas, tildes y signos) sobre el mismo documento cuesta USD 0 la segunda vez: las 10 preguntas medidas pasan de USD 0,0175 a 0 | [`pruebas/cache.md`](pruebas/cache.md) |
| Langfuse | Un servidor local hace de Langfuse y recibe lo que el SDK envía de verdad: ningún texto de la póliza, la pregunta, la respuesta ni correos | [`pruebas/probar_fase4.py`](pruebas/probar_fase4.py), [`backend/observabilidad.py`](backend/observabilidad.py) |
| Crashlytics | Recibe el tipo de error y las líneas de pila; probado con errores que traen texto de la póliza, preguntas, respuestas y correos en su mensaje y en la descripción de widgets. En la tableta, un error de prueba llegó a Firebase (respuesta 200). Sin Google Analytics en la app, Crashlytics no registra breadcrumbs | [`movil/test/telemetria_test.dart`](movil/test/telemetria_test.dart), [`movil/test/reglas_test.dart`](movil/test/reglas_test.dart) |
| Entrar con Google | En la tableta: selector de cuentas de Google, el backend verificó el token del cliente Android y abrió la sesión | [`movil/lib/estado.dart`](movil/lib/estado.dart), [`backend/acceso_google.py`](backend/acceso_google.py) |
| Paleta | La clara de las correcciones, exacta salvo «con límites» (#A36200); el rojo solo para «no cubre» (una prueba lo exige) | [`movil/lib/tema.dart`](movil/lib/tema.dart), [`movil/test/reglas_test.dart`](movil/test/reglas_test.dart) |
| Contraste | 19 de 19 pares de la app y la web cumplen WCAG AA (mínimo medido: 4,53:1, azul sobre crema) | [`pruebas/contraste.md`](pruebas/contraste.md) |
| TalkBack | 47 de 47 controles con etiqueta en 6 pantallas del dispositivo (medido antes de las correcciones); las guías de Flutter (etiquetas, 48×48, contraste dibujado) pasan sobre las pantallas de ahora | [`pruebas/accesibilidad.md`](pruebas/accesibilidad.md), [`movil/test/accesibilidad_test.dart`](movil/test/accesibilidad_test.dart) |
| Versión mínima | `GET /v1/app` la da; con el backend pidiendo la 2, la app 1 muestra solo «Actualiza» | [`movil/lib/main.dart`](movil/lib/main.dart) |
| Dependencias | pip-audit: 85 paquetes, ninguna vulnerabilidad conocida. OSV.dev: 143 paquetes de Flutter, ninguna | [`pruebas/auditoria_backend.md`](pruebas/auditoria_backend.md), [`pruebas/auditoria_flutter.md`](pruebas/auditoria_flutter.md) |
| Atribuciones | OpenStreetMap en el mapa (con enlace a su licencia) y SUSALUD (RENIPRESS, ODC-BY) bajo la lista | [`movil/lib/pantalla_mapa.dart`](movil/lib/pantalla_mapa.dart) |

### Correcciones tras probar en la tableta

En la rama `fase-4-correcciones`.

| Cambio | Resultado medido | Archivo |
|---|---|---|
| Veredicto | Sale del campo estructurado. «Cubre con límites» exige un límite concreto escrito en una cita; si el modelo no lo da, el código lo pasa a «Cubre». En las 10 preguntas, «con límites» pasó de 7 a 0 (dos corridas); veredicto aceptable en 10 de 10 en la corrida grabada | [`pruebas/veredictos.md`](pruebas/veredictos.md), [`ai/respuesta.py`](ai/respuesta.py) (`_validar`) |
| Respuesta corta | Arriba, el veredicto y su razonamiento (1 o 2 frases que van de los hechos al veredicto); la explicación, las condiciones y las citas, plegadas | [`movil/lib/resultado.dart`](movil/lib/resultado.dart), [`app/app.py`](app/app.py) |
| Memoria de la conversación | Cada pregunta ve los 3 turnos anteriores de la misma póliza. Con ellos, la segunda respuesta nombra «tu tobillo doblado»; sin ellos, no. Cuesta 617 tokens más con 3 turnos: USD 0,000062 por consulta (4,4 %) | [`pruebas/conversacion.md`](pruebas/conversacion.md), [`ai/prompts.py`](ai/prompts.py) |
| Lo que no cuenta como consulta | «Qué hacer ahora» sobre una respuesta ya dada (firmada por el servidor) y volver a abrir el historial | [`backend/main.py`](backend/main.py), [`pruebas/probar_fase4.py`](pruebas/probar_fase4.py) |
| Cuentas sin límite | `QMC_CORREOS_SIN_LIMITE`: sin tope diario, mensual ni bolsa, todas las funciones; el tope global de gasto sigue | [`backend/cuentas.py`](backend/cuentas.py) |
| PDF en la página de la cita | Se abre dentro de la app desde el archivo del teléfono; nunca se sube. En una póliza guardada se pide elegir el PDF una vez, se comprueba que sea el mismo (huella SHA-256) y queda una copia solo en el teléfono | [`movil/lib/visor_pdf.dart`](movil/lib/visor_pdf.dart), [`movil/lib/estado.dart`](movil/lib/estado.dart) |
| Mapa | Sin lugar por defecto: pide elegir o usar la ubicación. La ubicación llena departamento y distrito (editables); buscador de los 1891 distritos; clínicas como cuadrados con cruz, tú como punto redondo; lista con nombre, distrito y distancia, y cuántas hay en 10 km | [`movil/lib/pantalla_mapa.dart`](movil/lib/pantalla_mapa.dart) |
| Historial | Pestaña propia: las respuestas de la sesión y las de cada póliza guardada, completas y con sus citas, sin costo | [`movil/lib/pantalla_historial.dart`](movil/lib/pantalla_historial.dart) |
| Inicio | Sin «prueba con un ejemplo»; el campo se vacía al enviar; «Mientras más detalles des, mejor te puedo responder.» junto a «Tu pregunta»; el descargo, al final y en letra grande | [`movil/lib/pantalla_poliza.dart`](movil/lib/pantalla_poliza.dart) |
| Tableta | En vertical (800×1280) y horizontal (1280×800): sin desbordes, la columna de texto no pasa de 760 puntos | [`movil/test/diseno_test.dart`](movil/test/diseno_test.dart) |
| Política de privacidad | Página de GitHub Pages con el diseño de la app, generada del .md | [`pruebas/generar_privacidad.py`](pruebas/generar_privacidad.py), [`docs/privacidad.html`](docs/privacidad.html) |

**Versionado.** Todas las rutas viven bajo `/v1`. Dentro de `/v1` solo se agregan campos; un
cambio que rompa clientes va a `/v2` mientras `/v1` sigue respondiendo, hasta que la versión
mínima (`QMC_APP_VERSION_MINIMA`) deje fuera a las apps que la usan. Las rutas sin prefijo
quedan por compatibilidad con la web desplegada y no salen en la documentación.

**Compilar.** `flutter build apk --release` (o `appbundle` para Play). Sin `android/key.properties`
se firma con la llave de depuración; sin `android/app/google-services.json`, Crashlytics no se
activa y la app funciona igual. Ninguno de los dos va al repositorio.

## Instalación

Python 3.11.

```bash
git clone https://github.com/RenatoGates/que-me-cubre.git
cd que-me-cubre
python -m venv .venv
.venv\Scripts\activate            # Windows; en macOS o Linux: source .venv/bin/activate
pip install -r requirements.txt
copy .env.example .env            # en macOS o Linux: cp .env.example .env
```

En `.env` van `ANTHROPIC_API_KEY` (obligatoria para que haya veredictos) y `VOYAGE_API_KEY`
(para la búsqueda por embeddings; sin ella se busca con BM25). El resto de variables tiene
valores por defecto y está explicado en [`.env.example`](.env.example). Ninguna clave va al
repositorio.

Backend y Streamlit, en dos terminales:

```bash
uvicorn backend.main:app --port 8000
streamlit run app/app.py
```

La documentación de la API queda en `http://localhost:8000/docs`. El Streamlit es un cliente
de esa API (`QMC_API_URL`, por defecto `http://localhost:8000`) y solo necesita
[`app/requirements.txt`](app/requirements.txt).

Pruebas que no usan red ni gastan nada:

```bash
cd pruebas
python probar_verificacion.py
python probar_llm.py
python probar_subida.py
python probar_api.py
python probar_fase2.py
python probar_mapa_portero.py
python probar_cuentas.py
python probar_app.py
```

Las que llaman al modelo o a Voyage (centavos): `correr_pruebas.py`, `probar_inyeccion.py`,
`probar_alcance.py`, `evaluar_recuperacion.py`, `medir_subida.py`, `medir_fase2.py` y, contra el
backend desplegado, `probar_desplegado.py --url …` y `medir_arranque.py --url …`.

### Desplegar

- **Backend en Render:** *New > Blueprint* con este repositorio; [`render.yaml`](render.yaml)
  define el servicio y los nombres de las variables, y las claves se escriben en el panel de
  Render. Los contadores de los topes necesitan una base externa (`DATABASE_URL`, Postgres):
  el disco del plan gratuito se borra en cada reinicio.
- **Streamlit Community Cloud:** archivo `app/app.py`, Python 3.11, y en *Secrets*
  `QMC_API_URL = "https://…onrender.com"`.

### La API

| Método y ruta | Qué hace |
|---|---|
| `GET /v1/app` | Versión mínima de la app, cliente de Google del servidor y producto de Play |
| `GET /salud`, `GET /info` | Estado, modelo en uso, límite diario y si el servicio está sin modelo por el tope |
| `GET /polizas` | Condicionados de ejemplo, con preguntas de ejemplo |
| `POST /polizas` | Sube uno o varios PDF (un solo documento); devuelve un identificador que solo conoce quien subió y, si el documento no parece un condicionado, `aviso_documento` |
| `DELETE /polizas/{id}` | Borra de la memoria la póliza subida |
| `POST /preguntar` | Pregunta sobre una póliza: veredicto, explicación, citas verificadas y cláusulas ausentes. Si falta información devuelve `modo: "aclaracion"` con repreguntas (se reenvía con `aclaraciones`); si hay varias preguntas, `modo: "varias"` con una respuesta por cada una |
| `POST /pasos` | Qué hacer ahora: plazos con su fecha límite (`fecha_hecho`, o leída de la situación), a quién avisar, documentos y pasos, con citas |
| `GET /polizas/{id}/radiografia` | Resumen de la póliza con citas; la de una póliza subida se genera una vez y queda en memoria con ella. Del plan pagado, con una gratis por cuenta (403 si no corresponde) |
| `POST /superposiciones` | ¿Pagas doble?: coberturas que podrían superponerse entre 2 a 4 pólizas. Del plan pagado (403 si no) |
| `GET /uso` | Consultas que le quedan hoy y este mes (o su saldo, con plan pagado) a quien pregunta |
| `POST /cuenta/google` | Entrar con el ID token de Google; crea la cuenta si es nueva y se aceptó la política |
| `POST /cuenta/registro`, `POST /cuenta/sesion`, `DELETE /cuenta/sesion` | Crear cuenta con correo (con la casilla de privacidad aceptada), entrar y salir. La sesión va en `Authorization: Bearer …` |
| `GET /cuenta`, `GET /cuenta/avisos` | La cuenta con sus pólizas guardadas, su fecha de borrado y qué funciones tiene; la casilla de consentimiento y el enlace a la política |
| `POST /cuenta/compra` | Un pago (200 consultas) con el token de compra de Google Play. Hoy responde 501: el cobro llega en la Fase 4 |
| `POST /polizas/{id}/guardar` | Guarda en la cuenta la póliza recién subida (su texto, no el PDF) y devuelve la fecha de borrado |
| `GET /polizas/{id}/consultas`, `DELETE /consultas/{id}` | Historial de una póliza guardada; borrar una consulta |
| `DELETE /cuenta` | Borra la cuenta y todo, pidiendo la contraseña (una cuenta de Google, solo la sesión) |
| `GET /mapa/departamentos`, `/mapa/distritos`, `/mapa/establecimientos` | RENIPRESS por zona, con el centro del distrito para centrar el mapa |
| `GET /mapa/con-internamiento` | Hospitales y clínicas con internamiento de todo el país, para calcular lo más cercano en el cliente |
| `GET /polizas/{id}/clinicas` | Clínicas que el condicionado nombra literalmente, cada una con su cita verificada (sin modelo) |

El cliente manda un identificador propio en `X-Dispositivo`. Al cliente va solo lo
verificado: la salida cruda del modelo y los descartes no salen de la API.

**Topes de gasto** ([`backend/limites.py`](backend/limites.py), probados en
[`pruebas/probar_api.py`](pruebas/probar_api.py) y [`pruebas/probar_cuentas.py`](pruebas/probar_cuentas.py)): sin cuenta, 3 al día y 10 al mes
por dispositivo; con cuenta gratis, 3 al día y 20 al mes; con plan pagado, su bolsa de consultas y un freno de 20 al día;
60 por IP como respaldo, y un tope global mensual en dólares
(`QMC_TOPE_GLOBAL_USD`, 2,00). Al llegar al global la API no se cae: responde las cláusulas
encontradas, sin veredicto, que es la red de seguridad que ya existía.

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

**Evidencia**, cuatro conversaciones en [`docs/research/`](docs/research/):

- [Entrevistado 1](docs/research/entrevista_1.md), seguro de salud del trabajo: "No, tendría
  que ponerme a descargar la póliza del seguro, investigar, ponerme a leer". Pagaría menos
  de 10 soles al mes.
- [Entrevistada 2](docs/research/entrevista_2.md), EPS: "La verdad no, solo las consultas,
  creo yo". Valora sobre todo "entender con facilidad y saber qué hacer".
- [Entrevistado 3](docs/research/entrevista_3.md), seguro de viaje: se accidentó en
  Tarapoto, fue a un centro médico de noche y pagó de su bolsillo sin saber si le
  reembolsaban. Después le indicaron una radiografía en Lima y tampoco sabía si eso entraba.
- [Entrevistado 4](docs/research/entrevista_4.md), seguro laboral y de viaje: "Por la
  urgencia o desconocimiento he optado por correr con los gastos médicos por mi cuenta.
  Muchas veces las pólizas son muy extensas, muy técnicas, y no me he dado el tiempo de
  leerlas. Buscar qué cobertura aplica a tu caso es poco práctico." Le parece una
  alternativa interesante para responder concretamente a casos particulares.

**Advertencia metodológica:** las dos primeras entrevistas incluyeron preguntas dirigidas
sobre la app, así que la disposición a pagar que reportan no es evidencia fuerte. La tercera
sí es un episodio real con gasto real.

## 4. Solución e insight

**Solución.** Subes el PDF de tu póliza, aunque venga en varios archivos (o eliges un
condicionado de ejemplo), y preguntas como hablas: "me torcí el dedo en Tarapoto, ¿me
cubre?". La app busca en tu propio documento los pasajes que responden, el modelo redacta la
respuesta en JSON con citas, y el código verifica cada cita letra por letra contra la página
del PDF antes de mostrarla. Arriba va el veredicto ("Cubre con límites"), debajo la
explicación, lo que la póliza menciona pero no trae, y las citas con su artículo y página.
Si el modelo falla, se ven igual las cláusulas encontradas.

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
invente: eso se resolvió con código, verificando cada cita contra el texto de su página.

## 6. Demo

- **URL pública:** [queqbre.streamlit.app](https://queqbre.streamlit.app/) (Streamlit
  Community Cloud). Dos pestañas: "Pregunta a tu póliza" y "Dónde atenderte".
- **Video de respaldo:**
  [drive.google.com/file/d/1BBLOAqQeCcqQB9-K4aNmMfPMfCDSsZDF](https://drive.google.com/file/d/1BBLOAqQeCcqQB9-K4aNmMfPMfCDSsZDF/view?usp=drive_link),
  por si en la demo falla la conexión o la cuota.
- **Casos de la demo:** las dos preguntas reales de Tarapoto, como botones, sobre el
  condicionado de Chubb · JetSmart: la torcedura (P01) y la radiografía al llegar a Lima
  (P02).
- **Resultados, al primer intento y sin reintento (lo que vive el usuario):** 10 de 10
  preguntas de prueba con veredicto aceptable y las 35 citas propuestas, verificadas en su
  página ([`pruebas/resultados.md`](pruebas/resultados.md),
  [`pruebas/verificacion_citas.md`](pruebas/verificacion_citas.md)). La URL pública de arriba
  sigue siendo el prototipo (rama `main`, Groq) hasta que esta rama se despliegue. Las series
  de estabilidad de P01 y P02 ([`pruebas/estabilidad.md`](pruebas/estabilidad.md)) son del
  prototipo y no se repitieron con Haiku.
- **Pruebas de usuario:** dos personas probaron la app desplegada el 9 de noviembre de 2026
  ([`docs/research/pruebas_de_usuario.md`](docs/research/pruebas_de_usuario.md)). De ahí
  salen la subida de una póliza en varios PDF, los pasos de "cómo funciona", el aviso de
  avance y "Una pregunta a la vez".
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
| Buscar los pasajes | Embeddings de `voyage-4-large` por API, con la pregunta tal como se escribió | "Me torcí el dedo" no está en ninguna póliza; "Gastos Médicos por Accidente" sí. Los vectores acercan las dos cosas sin pasar por el modelo. Medido abajo |
| Redactar la respuesta JSON con citas | Claude Haiku 5.5, salida con esquema JSON | Las citas se verifican después contra el texto de su página, extraído del PDF al subirlo, y el texto libre se recorta si nombra algo que no está citado. El veredicto es el campo estructurado `cubre`, no el texto |
| Avisar lo que la póliza menciona pero no trae | Código ([`ai/referencias.py`](ai/referencias.py)), sin modelo | Igual que en el prototipo: B4 y las remisiones salen siempre, con su mención literal y su página |
| Respaldo de la búsqueda | BM25 con 3-5 variantes que escribe el modelo | Si no hay clave de Voyage, la póliza no tiene vectores o Voyage falla, la búsqueda no se cae: vuelve al método del prototipo, que sí necesita la llamada de normalización |

**Por qué Claude Haiku y no Groq gratuito.** El límite por minuto del plan gratuito (8000
tokens: una consulta cada ~36 s) rompía las demos. Haiku cuesta USD 0,10 por millón de
tokens de entrada y 0,50 de salida, y no tiene esa cuota. Lo que se cede: Groq corría con
retención cero y Anthropic borra a los 30 días (ver Privacidad). Groq y Gemini siguen detrás
de la misma interfaz ([`ai/llm.py`](ai/llm.py)) con `QMC_PROVEEDOR`.

**Esfuerzo de razonamiento bajo.** Con BM25 y las mismas 10 preguntas, esfuerzo medio y bajo
dieron los mismos 9 de 10 veredictos aceptables; el bajo tardó 8,4 s por respuesta y el medio
15,2 s ([`pruebas/resultados_bm25.md`](pruebas/resultados_bm25.md),
[`pruebas/resultados_medium.md`](pruebas/resultados_medium.md)). Queda en bajo
(`QMC_ESFUERZO_RESPUESTA`).

**Por qué embeddings con la pregunta tal cual.** Medido en las 9 preguntas con artículo
esperado ([`pruebas/recuperacion.md`](pruebas/recuperacion.md)), con los 5 primeros pasajes:

| Método | Artículo esperado entre los 5 pasajes |
|---|---:|
| BM25, pregunta original | 2 de 9 |
| BM25, variantes del modelo (lo que usaba el prototipo) | 5 de 9 |
| Embeddings, pregunta original (lo que usa la app) | 7 de 9 |
| Embeddings, mismas variantes | 5 de 9 |
| Híbrido de BM25 y embeddings, mismas variantes | 5 de 9 |

Las variantes y el filtro por cláusula, que rescataban a BM25, a los embeddings les estorban:
la pregunta sola encuentra más. Por eso la app ya no normaliza la pregunta cuando busca con
embeddings: una llamada al modelo en vez de dos. Con normalización y sin ella, los veredictos
aceptables fueron 10 de 10 ([`pruebas/resultados_emb_con_normalizacion.md`](pruebas/resultados_emb_con_normalizacion.md),
[`pruebas/resultados.md`](pruebas/resultados.md)). Con las variantes que escribía Groq, BM25
llegaba a 7 de 9 (commit `6570fd9`); con las de Haiku bajó a 5 de 9.

**Guardarraíles.** El prompt de sistema limita el alcance: solo la póliza cargada, sin
recomendar aseguradoras, productos ni aplicaciones, sin consejo legal ni médico. Fuera de
eso el veredicto es `fuera_de_alcance` y lo que se muestra es un texto fijo del código, no
del modelo ([`pruebas/alcance.md`](pruebas/alcance.md)).

**Instrucciones escondidas en el PDF.** Los pasajes y los títulos del documento entran al
modelo dentro de un delimitador que cambia en cada consulta, y el prompt de sistema dice que
lo que va ahí son datos, nunca instrucciones. Probado con una póliza que trae "ignora tus
instrucciones…" y con un intento de cerrar las etiquetas y hablar como el sistema
([`pruebas/inyeccion.md`](pruebas/inyeccion.md)).

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
5. Las citas, con documento, sección, artículo y página; si la póliza se subió en varios PDF,
   también el archivo y la página dentro de ese archivo.

En la red de seguridad (`modo: solo_clausulas`) la etiqueta dice "Sin veredicto", el aviso
explica por qué y se muestran los pasajes resaltados y el bloque de lo mencionado pero ausente.

### Cómo correrlo en local

Ver "Instalación", arriba. Para maquetar sin gastar, `QMC_PROVEEDOR=grabado`: la respuesta
del modelo es la que ya dio para esa pregunta en `pruebas/salidas/` y todo lo demás corre de
verdad.

Reconstruir los índices de los condicionados precargados (texto y vectores):

```bash
python -m ai.ingesta                 # --descargar baja los PDF que falten
python -m ai.embeddings              # vectores de las preguntas públicas de ensayo y de prueba
```

Las fuentes de cada condicionado (URL, fecha y sha256) están en
[`data/polizas/fuentes.json`](data/polizas/fuentes.json). Precargados: Chubb (Seguro de
Viajes JetSmart, 62 págs.), Pacífico (Seguro de Viajes, 40 págs.), Rimac (Seguro de Viaje,
20 págs. a dos columnas), Mapfre (Accidentes Personales con Asistencia en Viaje, 42 págs.) e
Interseguro (Seguro de Viaje Internacional, 36 págs.).

## 7. Modelo de negocio

**Quién paga.** El usuario final no es el que paga. Las entrevistas dan menos de 10 soles al
mes de disposición a pagar, que no sostiene el producto ni justifica la adquisición.

Quien paga es la aseguradora, el corredor o la agencia de viajes. Su incentivo es directo:
un asegurado que no sabe qué cubre su póliza no la usa, se atiende particular, y después
reclama o no renueva. Modelo: licencia mensual por cartera, con tres planes según número de
asegurados.

**Costo por consulta, medido:** USD 0,0016 en promedio y USD 0,0025 la más cara, con 8604
tokens en promedio (entrada más salida) en una sola llamada a Claude Haiku
([`pruebas/resultados.md`](pruebas/resultados.md)). Los embeddings no suman: Voyage da 200
millones de tokens gratis y una póliza de 62 páginas usa 68 973
([`pruebas/subida.md`](pruebas/subida.md)).

**Con 100 usuarios haciendo 10 consultas al mes** (1000 consultas): 1000 × 0,0016 ≈
**USD 1,60 al mes** en modelo. Con el tope global por defecto de USD 2,00 al mes entran unas
1250 consultas (2,00 ÷ 0,0016); después de eso el servicio sigue, sin veredictos. El costo
dominante no es el modelo, es el servidor cuando deje de ser gratuito.

Las mediciones de cuota del prototipo con Groq (el balde de 8000 tokens por minuto, los 200 000
por día y las opciones de recorte) quedan en [`pruebas/opciones.md`](pruebas/opciones.md) y en
el historial de este archivo (commit `6570fd9`).

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
  documento, verificación de citas contra el texto de cada página con dos lectores, bloque de lo mencionado
  pero ausente, red de seguridad, la app de Streamlit y la pestaña del mapa.
- Pruebas sin red ni cuota:
  [`pruebas/probar_verificacion.py`](pruebas/probar_verificacion.py) (42 casos),
  [`pruebas/probar_llm.py`](pruebas/probar_llm.py) (36),
  [`pruebas/probar_subida.py`](pruebas/probar_subida.py) (13),
  [`pruebas/probar_api.py`](pruebas/probar_api.py) (22: la API, los topes y el modo sin
  modelo), [`pruebas/probar_fase2.py`](pruebas/probar_fase2.py) (35: fechas y plazos,
  repregunta, varias preguntas, pasos, radiografías y superposiciones),
  [`pruebas/probar_mapa_portero.py`](pruebas/probar_mapa_portero.py) (21: portero, reparación
  de PDF, clínicas nombradas y lo que el mapa promete sobre la ubicación),
  [`pruebas/probar_cuentas.py`](pruebas/probar_cuentas.py) (46: cuentas, guardado sin PDF, cifrado,
  límites por plan, borrado automático y borrado total) y
  [`pruebas/probar_app.py`](pruebas/probar_app.py) (47: el Streamlit contra la API, incluida la cuenta, con
  respuestas grabadas).
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
├── backend/        API con FastAPI: pólizas en memoria, topes de gasto y observabilidad
├── app/            Streamlit, cliente de la API (y su requirements.txt)
├── ai/             extracción, troceado, índice, embeddings, recuperación, prompts, respuesta y RENIPRESS
├── data/
│   ├── polizas/    condicionados públicos de prueba (se versionan)
│   ├── indices/    índices ya construidos de esos condicionados
│   ├── cache/      normalizaciones y vectores de las preguntas de ensayo y de prueba
│   ├── demo/       preguntas de ensayo de la demo
│   ├── renipress/  establecimientos activos de RENIPRESS para el mapa
│   └── privado/    pólizas personales para pruebas locales (ignorado por git)
├── docs/           arquitectura, capturas y research/ con las 3 conversaciones
└── pruebas/        preguntas, corridas medidas con sus salidas y pruebas sin red
```

## Limitaciones

- **PDF escaneados:** la extracción necesita capa de texto. Si la mayoría de páginas de un
  archivo no la tiene, se rechaza diciendo cuál (haría falta OCR).
- **Tablas:** las filas de tablas (por ejemplo, porcentajes de indemnización) se leen fila
  por fila con pdfplumber, pero otro extractor (pypdf) las ordena distinto. En las tres
  pólizas precargadas, 41 de 5427 líneas no se pudieron confirmar con pypdf y todas son
  filas de tablas. El texto corrido coincide con su página.
- **Los embeddings dependen de Voyage:** al subir una póliza, su texto completo sale hacia
  Voyage AI. Sin medio de pago en la cuenta, Voyage limita a 3 peticiones y 10 000 tokens
  por minuto: una subida en vivo se queda sin vectores y se busca con BM25, e indexar la
  póliza de 62 páginas en lotes con pausas tardó 400 s. Con medio de pago, la subida completa
  tarda 17,4 s, de los que 3,8 s son embeddings ([`pruebas/subida.md`](pruebas/subida.md)).
  Si Voyage falla durante una consulta, se busca con BM25 y la pregunta tal cual, que es el
  método más débil de la tabla (2 de 9).
- **Interseguro: la etiqueta de artículo sale mal.** Ese condicionado se organiza en
  secciones con números romanos (I a XVI), que el extractor no reconoce: el texto citado y su
  página son correctos y están verificados, pero la sección y el artículo que acompañan a la
  cita no corresponden. Arreglarlo es tocar la extracción, que en esta fase no se reescribió.
- **Mapfre: tipografía del PDF.** Su capa de texto trae una I mayúscula donde va una ele
  ("PóIiza", "deI"). Las citas son literales, así que se muestran así, y la búsqueda por
  palabras del respaldo (BM25) no encuentra las palabras escritas así. Además la forma es de 2018 y puede no ser la
  versión vigente.
- **Mapfre e Interseguro no tienen preguntas de prueba.** Se comprobó a mano que responden
  con citas verificadas, pero ninguna de las 10 preguntas medidas es sobre ellos (8 son de
  Chubb).
- **Cuentas:** el correo no se verifica (no hay proveedor de correo), así que alguien puede
  registrarse con un correo ajeno, y quien olvida su contraseña pierde el acceso a lo guardado.
  El cifrado no protege del administrador: la llave está en su servidor. Si esa llave se
  pierde, lo guardado no se puede descifrar. El proveedor de la base puede conservar copias
  de respaldo por un tiempo después de un borrado. El cobro del plan pagado no existe: se
  activa a mano.
- **El tope por dispositivo se puede saltar.** Sin cuentas, el "dispositivo" es un
  identificador que genera el cliente: reinstalar la app o recargar el Streamlit da uno nuevo.
  El tope por IP y el global mensual son los que de verdad acotan el gasto.
- **El Streamlit ya no muestra el avance paso a paso** (buscar, redactar, verificar): ahora
  espera la respuesta entera de la API con un solo aviso.
- **El plan gratuito de Render es lento, no solo dormilón.** Tras 17 minutos sin tráfico la
  primera respuesta tardó 41,6 s ([`pruebas/arranque_render.md`](pruebas/arranque_render.md)).
  Ya despierto, subir e indexar la póliza de 62 páginas tardó 110,4 s (17,4 s en una laptop) y
  cada respuesta entre 20,9 y 25,8 s ([`pruebas/desplegado.md`](pruebas/desplegado.md)): el
  plan gratuito da una fracción de CPU y la extracción del PDF es puro cálculo. Al dormirse
  o reiniciarse el servidor, las pólizas subidas se pierden y hay que subirlas de nuevo. En
  esa prueba las citas salieron verificadas y con su página.
- **Repregunta:** el paso que decide si falta información es del modelo. En las 21 preguntas
  medidas no repreguntó de más ni de menos, pero una pregunta clara puede recibir una
  repregunta; con las respuestas de la persona ya no vuelve a repreguntar.
- **Varias preguntas:** se responden hasta 3; cada una gasta una consulta del día. Con más
  de una, el modelo las reescribe para que se entiendan solas, y esa reescritura no está
  verificada (con una sola pregunta se usa el texto original). Puede partir de más: "¿cuánto
  pago por una consulta o por una endodoncia?" salió como dos preguntas hasta que se ajustó
  el prompt por ese caso.
- **Qué hacer ahora:** el plazo que se muestra es el que está escrito en la cita, pero a qué
  aplica ("avisar del siniestro", "avisar a la central") lo redacta el modelo. La fecha límite
  se cuenta desde la fecha del hecho que dio la persona, aunque la póliza cuente "desde que
  tuvo conocimiento": la condición literal se muestra al lado. No se cuentan feriados. Si la
  póliza fija plazos distintos por cobertura, pueden salir varios y no se elige uno.
- **Radiografía:** resume los pasajes más relevantes (uno por sección y los de cinco temas),
  no la póliza entera: puede faltar una cobertura, y dos corridas pueden no listar las mismas
  (Mapfre dio 10 coberturas en una corrida y 3 en la siguiente, con el prompt apenas cambiado). Los montos casi nunca están en el
  condicionado: 10 de las 27 coberturas resumidas traen un monto escrito.
- **¿Pagas doble?:** cada lado del par son coberturas con citas verificadas, pero que se
  superpongan es un juicio del modelo, no verificado. En una corrida anterior emparejó
  "Repatriación en Vida" con "Repatriación o traslados funerarios", que no son lo mismo; en
  la actual salieron 6 pares sin ese. Por eso se presenta como posible coincidencia para
  revisar, no como recomendación.
- **Mapa:** los servidores públicos y gratuitos de Overpass no siempre responden. Mientras
  se construía esto, de cinco servidores probados cuatro daban error o no contestaban, y el
  único que respondió no acepta consultas desde un navegador; por eso el mapa muestra primero
  el registro de SUSALUD y solo reemplaza si OpenStreetMap contesta. El camino con
  OpenStreetMap está programado pero no se pudo ver funcionando en el navegador. El permiso
  de ubicación tampoco se pudo probar de forma automática: se comprobó que el marco del mapa
  lo tiene habilitado y, simulando unas coordenadas, que la cercanía se calcula bien.
- **Clínicas nombradas:** ninguno de los seis condicionados reales nombra una clínica, así
  que esa parte solo está probada con un PDF de prueba. La detección es por patrón (un tipo
  de establecimiento seguido de un nombre propio) y prefiere no encontrar antes que inventar:
  una clínica escrita toda en mayúsculas o de forma poco usual puede no detectarse.
- **Portero:** son 9 documentos y el umbral se fijó mirándolos. Un folleto comercial de un
  seguro, que usa el mismo vocabulario, probablemente pase como póliza. No bloquea nunca.
- **Si el modelo falla:** sin saldo, sin conexión o con una salida que no cumple el formato,
  la app no reintenta y muestra las cláusulas encontradas, resaltadas y sin veredicto. En las
  corridas medidas con Haiku ninguna de las 10 respuestas salió sin texto. Cada falla deja en
  los logs la tarea, el código y el mensaje del proveedor, sin la pregunta ni lo generado.
- **Resultados de las pruebas:** 10 de 10 veredictos aceptables al primer intento con la
  búsqueda por embeddings, una corrida ([`pruebas/resultados.md`](pruebas/resultados.md)).
  El artículo esperado está entre los 5 pasajes en 7 de 9 preguntas; fallan P02 y P04
  ([`pruebas/recuperacion.md`](pruebas/recuperacion.md)), y aun así sus veredictos salieron
  aceptables: un veredicto aceptable no garantiza que se haya leído el artículo correcto. Las
  35 citas mostradas y las 20 menciones del bloque de ausentes están literales en su página
  ([`pruebas/verificacion_citas.md`](pruebas/verificacion_citas.md)).
- **El filtro suave por cláusula (solo en el respaldo con BM25) está ajustado a las preguntas de la demo.** Subió P01 del
  puesto 9 al 4 y P02 de 18 y 3 a 3 y 4, y bajó P10 del puesto 1 al 11 (el modelo eligió la
  cláusula de Accidentes Personales en vez del Condicionado General, y el doble de puntaje
  bastó para enterrar el artículo correcto). En total quedan 7 de 9 preguntas con el artículo
  en los 5 primeros pasajes, contra 6 de 9 antes: casi un empate, y la mejora cayó justo en
  las dos preguntas de la demo. Eso es ajuste al caso de prueba. El factor (×2) no está
  calibrado: ×2, ×3, ×5 y el filtro duro dan exactamente el mismo resultado en estas 9
  preguntas, así que ellas no permiten elegir entre ellos. Nueve preguntas no alcanzan para
  calibrar nada; haría falta un conjunto de preguntas bastante más grande, escrito sin mirar
  los resultados ([`pruebas/normalizacion.md`](pruebas/normalizacion.md)).
- **Verificación de citas:** toda cita se verifica contra el texto de la página extraído del PDF con dos extractores independientes al momento de subirlo, o se descarta. La cita tiene que estar en el pasaje y en el texto de su página,
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
  La ubicación de la persona se usa solo en su navegador y si la concede (ver "Mapa con
  ubicación"); el servidor solo recibe el departamento y el distrito elegidos. Para actualizarlo,
  bajar el CSV del mes y correr `python -m ai.renipress --csv ... --corte ... --url ...`
  (la procedencia queda en [`data/renipress/fuente.json`](data/renipress/fuente.json)).
- **Cachés de preguntas públicas:** las normalizaciones y los vectores de las preguntas de
  ensayo y de prueba (`data/demo/`, `pruebas/`) se versionan en `data/cache/`, generados en
  local con `python -m ai.preparar_demo` y `python -m ai.embeddings`. La app los lee, nunca
  escribe en ellos: las preguntas de los usuarios no se guardan ahí.
- **Estructura heurística:** secciones y artículos se reconocen con patrones de los
  condicionados peruanos ("Cláusula Adicional", "Artículo N°", "PARTE B", numerales). Una
  póliza con otro formato puede quedar con trozos por página sin artículo.

## Próximos pasos

- **Desplegar la Fase 2** (Render despliega `main`) y activar Langfuse cuando haya testers.
- **Arreglar la estructura de Interseguro** (secciones con números romanos) para que la
  etiqueta de artículo sea la correcta.
- **Fases 3 a 5:** cuentas e historial, app Android con Flutter y publicación.

## Licencia

[MIT](LICENSE).

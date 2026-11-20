# Política de privacidad de ¿Qué Cubre?

Versión del 20 de noviembre de 2026. Describe lo que la app hace hoy. Si algo cambia, cambia
este documento antes.

## En una frase

Sin cuenta, la app no guarda nada tuyo. Con cuenta, guarda el texto de tu póliza y tus
últimas consultas, cifrados, y quien administra la app podría leerlos.

## Si usas la app sin cuenta

- El PDF que subes se procesa en la memoria del servidor. No se escribe en disco ni en
  registros, y se borra de la memoria tras 60 minutos sin uso, cuando lo pides o cuando el
  servidor se reinicia.
- No se guarda tu pregunta ni la respuesta.
- Para contar cuántas consultas haces (3 al día y 10 al mes) se guarda un código derivado del
  identificador de tu dispositivo y otro de tu dirección IP, no los valores originales. El de
  la IP cambia cada día.

## Si creas una cuenta

Se guarda, hasta que lo borres:

- Tu correo.
- Si entras con correo y contraseña: tu contraseña, transformada (hash scrypt), que no se
  puede leer.
- Si entras con Google: el identificador de tu cuenta de Google. La app pide a Google solo tu
  correo, tu nombre y tu foto (alcances openid, email y profile); el nombre y la foto no se
  guardan.
- La fecha en que aceptaste esta política.
- Si ya usaste tu radiografía gratis, de qué póliza fue.
- Si compraste consultas: que la cuenta es de pago, cuántas consultas te quedan, de qué
  pólizas pediste la radiografía y, de cada compra, la fecha, cuántas consultas sumó y un
  código derivado de su comprobante. Google Play procesa el pago; la app no ve ni guarda tus
  datos de pago.
- De cada póliza que elijas guardar: su texto partido en fragmentos, los vectores que
  permiten buscar en ella y el texto de cada página. **No se guarda el archivo PDF.**
- Tus últimas 20 consultas por póliza guardada: la pregunta, la respuesta y sus citas.

El texto de una póliza puede traer tu nombre, tu documento de identidad y datos de tu salud,
y tus preguntas también pueden contarlos. Son datos sensibles según la Ley N.° 29733, Ley de
Protección de Datos Personales del Perú. Por eso el registro te pide aceptarlo de forma
expresa, con una casilla que no viene marcada.

### Dónde está y cómo se protege

- Está en una base de datos Postgres del proveedor Neon.
- Viaja cifrado entre tu dispositivo, el servidor de la app y la base (TLS).
- El contenido de tus pólizas y de tus consultas se cifra con AES-256 antes de guardarse.

**La llave de ese cifrado está en el servidor de quien administra la app. Por lo tanto, quien
administra la app podría leer el contenido de tus pólizas y de tus consultas.** El cifrado
protege tus datos si alguien accede a la base sin la llave; no los protege de quien tiene la
llave. No lee ese contenido como parte del funcionamiento de la app, pero técnicamente puede.

### Cuánto tiempo

- En el plan gratuito, la póliza guardada se borra sola a los 14 días de guardarla, con todas
  sus consultas. La app muestra la fecha junto a la póliza. Desde ese día tienes que volver a
  subir el PDF.
- En el plan de pago, las pólizas guardadas no se borran solas.
- Una cuenta en la que nadie entra durante 12 meses se borra entera.
- La base puede conservar copias de respaldo del proveedor por un tiempo limitado después de
  un borrado.

### Cómo lo borras

- Una consulta: botón "Borrar" junto a ella.
- Una póliza guardada, con todo su historial: botón "Borrar esta póliza".
- Todo: "Borrar mi cuenta y todo". Borra la cuenta, las pólizas, el historial, las sesiones,
  los registros de compra y los contadores, y con ellos las consultas pagadas que te queden.
  Es inmediato y no se puede deshacer.

## Lo que sale hacia terceros, con o sin cuenta

- **Voyage AI:** al subir una póliza recibe su texto para calcular los vectores de búsqueda,
  y al preguntar recibe tu pregunta.
- **Google:** si entras con Google, Google sabe que entraste a esta app. Si compras funciones
  premium, Google Play procesa el pago.
- **Dictado por voz (app de Android):** si preguntas hablando, el audio lo transcribe el
  reconocedor de voz de tu propio Android (normalmente el de Google), según la configuración de
  tu teléfono. La app recibe solo el texto, que ves y puedes corregir antes de enviarlo.
- **Errores técnicos (Firebase Crashlytics, app de Android):** si la app falla, se envía el
  tipo de error y en qué parte del código ocurrió, con datos del dispositivo (modelo y versión
  de Android). Nunca el texto de tu póliza, tus preguntas, las respuestas ni tu correo.
- **Métricas del servicio (Langfuse):** cuánto tarda y cuánto cuesta cada respuesta, qué
  función se usó y si hubo un error. Nunca el texto de tu póliza, tu pregunta ni la respuesta.
- **Anthropic:** recibe tu pregunta y los fragmentos de la póliza encontrados para redactar
  la respuesta. Según su política, borra lo enviado por su API dentro de los 30 días.
- **OpenStreetMap:** si usas el mapa, recibe los pedidos de las imágenes del mapa de la zona
  que miras. En la web, si concedes tu ubicación, recibe también las coordenadas de la consulta
  de centros cercanos. En la app de Android, tu ubicación se usa solo en el teléfono para
  ordenar los centros por distancia. Tu ubicación no pasa por el servidor de la app ni se guarda.

La app no tiene publicidad ni analítica de comportamiento: lo único que mide son los errores
técnicos y las métricas del servicio descritos arriba, sin contenido.

## Tus derechos

Puedes acceder a lo guardado desde "Mi cuenta", y borrarlo ahí mismo. Para cualquier otra
solicitud sobre tus datos (acceso, rectificación, cancelación u oposición), escribe a quien
administra la app por el repositorio del proyecto:
<https://github.com/RenatoGates/que-me-cubre/issues>.

## Lo que esta app no es

Es una herramienta informativa. La decisión final sobre una cobertura la toma tu aseguradora.

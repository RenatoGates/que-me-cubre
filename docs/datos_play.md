# Seguridad de los datos (formulario de Google Play)

Respuestas para Play Console → Política de la app → Seguridad de los datos. Describen lo que la
app hace hoy (ver [`privacidad.md`](privacidad.md)); si algo cambia, se actualizan las dos.

## Preguntas generales

- **¿La app recopila o comparte datos del usuario?** Sí, recopila. No comparte con terceros
  para fines propios de ellos (Anthropic, Voyage AI y Google procesan datos por encargo de la app).
- **¿Los datos se cifran en tránsito?** Sí (HTTPS).
- **¿El usuario puede pedir que se borren?** Sí, dentro de la app: «Mi cuenta → Borrar mi cuenta y todo».
- **Política de privacidad:** https://renatogates.github.io/que-me-cubre/privacidad.html

## Tipos de datos

| Tipo (categoría de Play) | ¿Se recopila? | ¿Obligatorio? | Para qué | Notas |
|---|---|---|---|---|
| Información personal → Dirección de correo electrónico | Sí | Opcional (solo con cuenta) | Administración de la cuenta | Con Google o con correo y contraseña |
| Información personal → ID de usuario | Sí | Opcional (solo con cuenta) | Administración de la cuenta | El identificador de la cuenta de Google y el de la app |
| Salud y actividad física → Información de salud | Sí | Opcional | Funcionalidad de la app | El texto de la póliza y las preguntas pueden traer datos de salud. Sin cuenta se procesa de forma efímera; con cuenta se guarda cifrado |
| Archivos y documentos → Archivos y documentos | Sí | Opcional | Funcionalidad de la app | El PDF se procesa de forma efímera y no se guarda; con cuenta se guarda su texto, no el archivo |
| Actividad en la app → Otro contenido generado por el usuario | Sí | Opcional (solo con cuenta) | Funcionalidad de la app | Las últimas 20 consultas por póliza guardada |
| Información financiera → Historial de compras | Sí | Opcional | Funcionalidad de la app | Fecha y un código derivado del comprobante de cada compra; Google Play procesa el pago |
| Información y rendimiento de la app → Registros de fallas | Sí | Obligatorio | Funcionalidad de la app (estabilidad) | Firebase Crashlytics: tipo de error y líneas de código, sin contenido |
| Información y rendimiento de la app → Diagnóstico | Sí | Obligatorio | Funcionalidad de la app (estabilidad) | Modelo y versión de Android, sesiones de uso para la tasa de sesiones sin fallas |
| Dispositivo u otros identificadores | Sí | Obligatorio | Prevención de fraudes y seguridad; estabilidad | Un identificador que genera la app (se guarda solo su hash) para los topes de uso; el de instalación de Crashlytics |
| Ubicación (aproximada y precisa) | No | — | — | Se usa solo en el teléfono para ordenar los centros por distancia; no sale del dispositivo |
| Audio → Grabaciones de voz | No | — | — | El dictado lo hace el reconocedor de voz de Android; la app recibe solo el texto |
| Actividad en la app → Interacciones con la app | No | — | — | La app no incluye Google Analytics (aunque esté activado en el proyecto de Firebase) |

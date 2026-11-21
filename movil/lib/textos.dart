/// Textos fijos de la app. Regla de lenguaje: nunca nombres de modelos, proveedores ni APIs, y
/// nunca contadores ni palabras de consumo (saldo, créditos, tokens, consultas restantes, bolsa).
class Textos {
  static const nombre = '¿Qué Cubre?';

  /// Junto a cada respuesta, visible.
  static const descargoRespuesta =
      'Esto sale del documento que subiste. Revisa tú mismo la cláusula citada en tu póliza antes de decidir o '
      'reclamar: ese documento, no esta app, es el que vale ante tu aseguradora.';

  /// En la pantalla de inicio y en la ficha de Play.
  static const descargoInicio =
      '¿Qué Cubre? te muestra qué dice tu póliza y en qué cláusula lo dice, para que puedas leerlo y reclamar con ese '
      'texto en la mano. No es asesoría legal ni de seguros, puede equivocarse, y no reemplaza lo que diga tu aseguradora.';

  static const botonPremium = 'Desbloquear funciones premium';
  static const masDetalles = 'Mientras más detalles des, mejor te puedo responder.';
  static const funcionesPremium = [
    'Guarda varias pólizas, sin que se borren',
    'Compara tus pólizas: ¿pagas doble?',
    'La radiografía de cada póliza',
    'Más consultas para tus casos',
  ];
  static const sinConexion = 'No pude conectarme. Vuelve a intentar en un momento.';
  static const consentimiento =
      'Acepto la política de privacidad y que se guarde el texto de mi póliza y mis consultas, que pueden incluir datos de salud.';
  static const privacidadCorta =
      'Tu PDF se procesa en memoria y no se guarda. Con cuenta, guardamos cifrados el texto de tu póliza y tus consultas, nunca '
      'el PDF; puedes borrarlos cuando quieras.';
}

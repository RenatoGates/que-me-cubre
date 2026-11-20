import 'dart:async';

import 'package:firebase_core/firebase_core.dart';
import 'package:firebase_crashlytics/firebase_crashlytics.dart';
import 'package:flutter/foundation.dart';

/// Lo único que sale hacia Crashlytics: el tipo del error y las líneas de la pila (funciones y
/// archivos del código). Nunca el mensaje del error, que puede traer texto de la póliza, de la
/// pregunta, de la respuesta o un correo.
class ErrorTecnico implements Exception {
  ErrorTecnico(this.tipo, this.traza);
  final String tipo;
  final String traza;

  @override
  String toString() => 'ErrorTecnico: $tipo';
}

// Una línea de pila de Dart: "#3      Clase.metodo (package:quecubre/archivo.dart:12:7)".
final _linea = RegExp(r'^#\d+\s+[\w$<>.\[\]& ]+ \((?:package|dart):[\w/.\-]+(?::\d+){0,2}\)$');

ErrorTecnico limpiar(Object error, StackTrace? pila) {
  final lineas = (pila?.toString() ?? '').split('\n').map((l) => l.trim()).where(_linea.hasMatch).take(40);
  final tipo = error.runtimeType.toString().replaceAll(RegExp(r'[^\w<>$.]'), '');
  return ErrorTecnico(tipo.isEmpty ? 'Error' : tipo, lineas.join('\n'));
}

typedef Envio = void Function(ErrorTecnico error, bool fatal);

class Telemetria {
  static bool _activa = false;

  /// A dónde va cada error ya limpio. Las pruebas lo reemplazan para ver qué saldría.
  static Envio enviar = (error, fatal) {
    if (!_activa) return;
    FirebaseCrashlytics.instance.recordError(error, StackTrace.fromString(error.traza), fatal: fatal, printDetails: false);
  };

  static Future<void> iniciar() async {
    try {
      await Firebase.initializeApp(); // sin google-services.json no hay Firebase y no se envía nada
      await FirebaseCrashlytics.instance.setCrashlyticsCollectionEnabled(!kDebugMode);
      _activa = !kDebugMode;
    } catch (_) {
      _activa = false;
    }
  }

  static void registrar(Object error, StackTrace? pila, {bool fatal = false}) => enviar(limpiar(error, pila), fatal);

  /// Los errores de Flutter traen descripciones de widgets (que pueden incluir texto en
  /// pantalla): se envía solo la excepción, limpia.
  static void errorDeFlutter(FlutterErrorDetails detalles) {
    if (kDebugMode) FlutterError.presentError(detalles);
    registrar(detalles.exception, detalles.stack, fatal: true);
  }
}

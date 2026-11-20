import 'package:flutter/foundation.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:quecubre/telemetria.dart';

/// Crashlytics recibe solo el error técnico: el tipo y la pila. Se provocan errores cuyo
/// mensaje trae texto de una póliza, una pregunta, una respuesta y un correo, y se revisa todo
/// lo que saldría hacia Crashlytics.
void main() {
  const poliza = 'Artículo 3° Cobertura: el reembolso de gastos médicos por accidente en Tarapoto';
  const pregunta = 'Me torcí el dedo en Tarapoto, ¿me cubre?';
  const respuesta = 'Cubre con límites: hasta US\$ 30 000 por gastos médicos';
  const correo = 'ana.secreta@ejemplo.pe';
  final prohibidos = [poliza, pregunta, respuesta, correo, 'Tarapoto', 'ana.secreta', '30 000'];

  late List<(ErrorTecnico, bool)> enviados;
  setUp(() {
    enviados = [];
    Telemetria.enviar = (e, fatal) => enviados.add((e, fatal));
  });

  String todo() => enviados.map((e) => '${e.$1}\n${e.$1.tipo}\n${e.$1.traza}').join('\n');

  test('un error con texto de la póliza, la pregunta, la respuesta y un correo en su mensaje no los envía', () {
    for (final mensaje in [poliza, pregunta, respuesta, correo]) {
      try {
        throw FormatException('No pude leer: $mensaje');
      } catch (e, pila) {
        Telemetria.registrar(e, pila);
      }
      try {
        throw StateError(mensaje);
      } catch (e, pila) {
        Telemetria.registrar(e, pila, fatal: true);
      }
    }
    expect(enviados, hasLength(8));
    for (final texto in prohibidos) {
      expect(todo().contains(texto), isFalse, reason: 'salió «$texto»');
    }
    expect(enviados.first.$1.tipo, 'FormatException');
    expect(enviados[1].$1.tipo, 'StateError');
  });

  test('se conserva lo técnico: el tipo y las líneas de la pila', () {
    try {
      throw ArgumentError(correo);
    } catch (e, pila) {
      Telemetria.registrar(e, pila);
    }
    final e = enviados.single.$1;
    expect(e.tipo, 'ArgumentError');
    expect(e.traza, contains('(package:')); // las rutas file: (que pueden traer el usuario del equipo) no salen
    expect(e.traza.contains('file:'), isFalse);
    expect(e.traza.split('\n').every((l) => l.startsWith('#')), isTrue);
  });

  test('una pila manipulada con texto no pasa: solo líneas con forma de línea de pila', () {
    final pila = StackTrace.fromString('#0      main (package:quecubre/main.dart:10:5)\n'
        '$poliza\n'
        '#1      x ($correo)\n'
        'pregunta: $pregunta\n'
        '#2      _Clase.metodo (package:quecubre/estado.dart:42:7)');
    Telemetria.registrar(Exception(respuesta), pila);
    final traza = enviados.single.$1.traza;
    expect(traza.split('\n'), hasLength(2));
    for (final texto in prohibidos) {
      expect(traza.contains(texto), isFalse, reason: 'salió «$texto»');
    }
  });

  test('un error de Flutter (que describe widgets con su texto) se envía sin la descripción', () {
    final detalles = FlutterErrorDetails(
      exception: FlutterError('A RenderFlex overflowed while showing Text("$respuesta")'),
      stack: StackTrace.current,
      context: ErrorDescription('while building Text("$pregunta") for $correo'),
      informationCollector: () => [DiagnosticsNode.message(poliza)],
    );
    Telemetria.errorDeFlutter(detalles);
    expect(enviados.single.$2, isTrue);
    for (final texto in prohibidos) {
      expect(todo().contains(texto), isFalse, reason: 'salió «$texto»');
    }
  });

  testWidgets('un error al construir una pantalla con texto de la póliza tampoco lo envía', (tester) async {
    final anterior = FlutterError.onError;
    FlutterError.onError = Telemetria.errorDeFlutter;
    await tester.pumpWidget(MaterialApp(home: Builder(builder: (context) => throw StateError('Pantalla con: $poliza $correo'))));
    FlutterError.onError = anterior;
    tester.takeException();
    expect(enviados, isNotEmpty);
    for (final texto in prohibidos) {
      expect(todo().contains(texto), isFalse, reason: 'salió «$texto»');
    }
  });
}

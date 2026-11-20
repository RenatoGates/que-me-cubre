import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:quecubre/tema.dart';

String _codigo() => Directory('lib').listSync(recursive: true).whereType<File>().where((f) => f.path.endsWith('.dart'))
    .map((f) => f.readAsStringSync()).join('\n');

void main() {
  test('la paleta es exactamente la acordada', () {
    expect(Paleta.fondo, const Color(0xFF0F1729));
    expect(Paleta.superficie, const Color(0xFF1A2338));
    expect(Paleta.texto, const Color(0xFFE8EDF7));
    expect(Paleta.textoSecundario, const Color(0xFF9AA7BF));
    expect(Paleta.accion, const Color(0xFF3DBFB0));
    expect(Paleta.cubierto, const Color(0xFF35C77A));
    expect(Paleta.noCubierto, const Color(0xFFFF6B5A));
    expect(Paleta.parcial, const Color(0xFFF5B544));
  });

  test('el coral se usa solo para el veredicto «no cubre»', () {
    final usos = RegExp(r'Paleta\.noCubierto').allMatches(_codigo()).length;
    expect(usos, 1, reason: 'el coral queda reservado para «no cubierto»');
    expect(_codigo().contains("'no' => const Veredicto(Paleta.noCubierto"), isTrue);
  });

  test('sin Google Analytics en la app, y Crashlytics sin breadcrumbs, registros ni datos propios', () {
    expect(File('pubspec.yaml').readAsStringSync().contains('firebase_analytics'), isFalse);
    final codigo = _codigo();
    for (final prohibido in ['FirebaseAnalytics', '.log(', 'setCustomKey', 'setUserIdentifier', 'recordFlutterError']) {
      expect(codigo.contains(prohibido), isFalse, reason: 'aparece $prohibido');
    }
  });
}

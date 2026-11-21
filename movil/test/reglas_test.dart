import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:quecubre/tema.dart';

String _codigo() => Directory('lib').listSync(recursive: true).whereType<File>().where((f) => f.path.endsWith('.dart'))
    .map((f) => f.readAsStringSync()).join('\n');

void main() {
  test('la paleta es exactamente la acordada (clara)', () {
    expect(Paleta.fondo, const Color(0xFFFBF7F2));
    expect(Paleta.superficie, const Color(0xFFFFFFFF));
    expect(Paleta.borde, const Color(0xFFE8DFD4));
    expect(Paleta.texto, const Color(0xFF2E2620));
    expect(Paleta.textoSecundario, const Color(0xFF7A6E62));
    expect(Paleta.accion, const Color(0xFF2D6BE5));
    expect(Paleta.sobreAccion, const Color(0xFFFFFFFF));
    expect(Paleta.cubierto, const Color(0xFF1E7A4D));
    expect(Paleta.noCubierto, const Color(0xFFC0392B));
    expect(Paleta.parcial, const Color(0xFFA36200)); // #B06A00 ajustado: no llegaba a 4,5:1 (pruebas/medir_contraste.py)
    expect(Paleta.citaFondo, const Color(0xFFF3EDE4));
    expect(temaQueCubre().brightness, Brightness.light);
  });

  test('no quedan restos de la paleta oscura ni colores sueltos fuera de tema.dart', () {
    final codigo = _codigo().toUpperCase();
    for (final viejo in ['0F1729', '1A2338', 'E8EDF7', '9AA7BF', '3DBFB0', '35C77A', 'FF6B5A', 'F5B544', '16304A']) {
      expect(codigo.contains(viejo), isFalse, reason: 'queda el color #$viejo');
    }
    for (final f in Directory('lib').listSync(recursive: true).whereType<File>().where((f) => !f.path.endsWith('tema.dart'))) {
      final opacos = RegExp(r'Color\(0xFF[0-9A-Fa-f]{6}\)').allMatches(f.readAsStringSync()).map((m) => m[0]).toList();
      expect(opacos, isEmpty, reason: '${f.path} usa colores fuera de la paleta: $opacos');
    }
    expect(_codigo().contains('Brightness.dark'), isFalse);
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

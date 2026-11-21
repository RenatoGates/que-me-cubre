import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:material_ui/material_ui.dart';
import 'package:quecubre/api.dart';
import 'package:quecubre/comun.dart';
import 'package:quecubre/compras.dart';
import 'package:quecubre/estado.dart';
import 'package:quecubre/pantalla_cuenta.dart';
import 'package:quecubre/pantalla_historial.dart';
import 'package:quecubre/pantalla_poliza.dart';
import 'package:quecubre/resultado.dart';
import 'package:quecubre/tema.dart';

/// Guías de accesibilidad de Flutter sobre las pantallas reales: cada control tocable con
/// etiqueta (lo que lee TalkBack), de al menos 48×48, y el contraste del texto tal como se dibuja.
Future<void> revisar(WidgetTester tester, Widget pantalla, Estado estado) async {
  tester.view.physicalSize = const Size(2560, 1600);
  tester.view.devicePixelRatio = 2;
  addTearDown(tester.view.reset);
  final semantica = tester.ensureSemantics();
  await tester.pumpWidget(EstadoScope(estado: estado, child: MaterialApp(theme: temaQueCubre(), home: Scaffold(body: pantalla))));
  await tester.pump(const Duration(milliseconds: 300));
  await expectLater(tester, meetsGuideline(labeledTapTargetGuideline));
  await expectLater(tester, meetsGuideline(androidTapTargetGuideline));
  await expectLater(tester, meetsGuideline(textContrastGuideline));
  semantica.dispose();
}

Estado estadoDePrueba() => Estado()
  ..api = Api('prueba-accesibilidad')
  ..config = {'cuentas_disponibles': true, 'google_server_client_id': 'cliente-web'}
  ..ejemplos = [
    {'poliza_id': 'chubb_viajes_jetsmart', 'aseguradora': 'Chubb Seguros Perú', 'producto': 'Seguro de Viajes JetSmart', 'ejemplos': <String>[]},
    {'poliza_id': 'rimac_viajes', 'aseguradora': 'Rimac Seguros', 'producto': 'Seguro de Viaje', 'ejemplos': <String>[]},
  ];

void main() {
  testWidgets('inicio: el campo de la pregunta y cada botón tienen etiqueta', (tester) async {
    await revisar(tester, const PantallaPoliza(), estadoDePrueba());
    expect(find.bySemanticsLabel(RegExp('Escribe o dicta tu pregunta')), findsOneWidget);
    expect(find.byTooltip('Preguntar hablando'), findsOneWidget);
  });

  testWidgets('con una póliza elegida', (tester) async {
    final e = estadoDePrueba()..poliza = PolizaActual(id: 'chubb_viajes_jetsmart', nombre: 'Chubb', tipo: 'ejemplo');
    await revisar(tester, const PantallaPoliza(), e);
  });

  testWidgets('Mi cuenta sin sesión: correo y contraseña con etiqueta', (tester) async {
    final e = estadoDePrueba();
    await revisar(tester, PantallaCuenta(compras: Compras(e)), e);
    expect(find.bySemanticsLabel('Correo'), findsOneWidget);
    expect(find.bySemanticsLabel('Contraseña'), findsOneWidget);
  });

  testWidgets('una respuesta real: veredicto con texto (no solo color), citas y descargo', (tester) async {
    final r = jsonDecode(File('../pruebas/salidas/P01.json').readAsStringSync()) as Map<String, dynamic>;
    final poliza = PolizaActual(id: 'chubb_viajes_jetsmart', nombre: 'Chubb', tipo: 'ejemplo');
    await revisar(tester, SingleChildScrollView(child: VistaRespuesta(r, poliza, detalleAbierto: true)), estadoDePrueba());
    expect(find.bySemanticsLabel('Veredicto: ${r['etiqueta_veredicto']}'), findsOneWidget);
    expect(find.textContaining('Esto sale del documento que subiste'), findsOneWidget);
    expect(find.textContaining('Ver esta cláusula en tu póliza'), findsWidgets);
  });

  testWidgets('el historial con una respuesta de la sesión', (tester) async {
    final r = jsonDecode(File('../pruebas/salidas/P01.json').readAsStringSync()) as Map<String, dynamic>;
    final poliza = PolizaActual(id: 'chubb_viajes_jetsmart', nombre: 'Chubb', tipo: 'ejemplo');
    final e = estadoDePrueba()..registrarRespuesta(poliza, r);
    await revisar(tester, const PantallaHistorial(), e);
    expect(find.text('${r['pregunta']}'), findsOneWidget);
  });

  test('cada veredicto lleva ícono y texto, además del color', () {
    for (final cubre in ['si', 'con_limites', 'no', 'no_encontrado']) {
      final v = Veredicto.de(cubre);
      expect(v.icono, isNotNull);
    }
    expect({Veredicto.de('si').icono, Veredicto.de('con_limites').icono, Veredicto.de('no').icono}, hasLength(3));
  });
}

import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:material_ui/material_ui.dart';
import 'package:quecubre/api.dart';
import 'package:quecubre/comun.dart';
import 'package:quecubre/estado.dart';
import 'package:quecubre/pantalla_historial.dart';
import 'package:quecubre/pantalla_mapa.dart';
import 'package:quecubre/pantalla_poliza.dart';
import 'package:quecubre/resultado.dart';
import 'package:quecubre/tema.dart';
import 'package:quecubre/textos.dart';

Map<String, dynamic> leer(String id) => jsonDecode(File('../pruebas/salidas/$id.json').readAsStringSync()) as Map<String, dynamic>;

/// Un backend falso para las pantallas que piden datos al abrirse (el mapa).
Api apiFalsa() => Api('prueba-diseno', cliente: MockClient((pedido) async {
      final cuerpo = switch (pedido.url.path) {
        '/v1/mapa/departamentos' => [
            {'id': 'LIMA', 'nombre': 'Lima'},
            {'id': 'SAN MARTIN', 'nombre': 'San Martín'},
          ],
        '/v1/mapa/distritos-todos' => [
            {'departamento': 'SAN MARTIN', 'provincia': 'SAN MARTIN', 'distrito': 'TARAPOTO', 'nombre': 'Tarapoto',
             'nombre_provincia': 'San Martín', 'nombre_departamento': 'San Martín'},
          ],
        _ => <String, dynamic>{},
      };
      return http.Response.bytes(utf8.encode(jsonEncode(cuerpo)), 200, headers: {'content-type': 'application/json'});
    }));

Estado estado() => Estado()
  ..api = apiFalsa()
  ..config = {'cuentas_disponibles': true}
  ..ejemplos = [
    {'poliza_id': 'chubb_viajes_jetsmart', 'aseguradora': 'Chubb Seguros Perú', 'producto': 'Seguro de Viajes JetSmart', 'ejemplos': <String>[]},
  ];

/// Tamaños en puntos de la tableta de prueba (Galaxy Tab S7 FE: 2560×1600 px a densidad 2).
Future<void> montar(WidgetTester tester, Widget pantalla, Estado e, {Size tamano = const Size(1280, 800)}) async {
  tester.view.physicalSize = tamano * 2;
  tester.view.devicePixelRatio = 2;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(EstadoScope(estado: e, child: MaterialApp(theme: temaQueCubre(), home: Scaffold(body: pantalla))));
  await tester.pump(const Duration(milliseconds: 300));
}

void main() {
  testWidgets('la respuesta: veredicto y por qué a la vista; detalle y citas plegados', (tester) async {
    final r = leer('P01');
    await montar(tester, SingleChildScrollView(child: VistaRespuesta(r, null)), estado(), tamano: const Size(800, 1280));
    expect(find.bySemanticsLabel('Veredicto: ${r['etiqueta_veredicto']}'), findsOneWidget);
    expect(find.text('${r['razonamiento']}'), findsOneWidget);
    expect(find.text('Ver el detalle y las citas'), findsOneWidget);
    final cita = '${(r['citas'] as List).first['texto_literal']}';
    expect(find.text(cita), findsNothing, reason: 'las citas van plegadas');
    await tester.tap(find.text('Ver el detalle y las citas'));
    await tester.pumpAndSettle();
    expect(find.text(cita), findsOneWidget);
  });

  testWidgets('«con límites» siempre nombra el límite y su cita', (tester) async {
    final r = {
      ...leer('P01'),
      'cubre': 'con_limites',
      'etiqueta_veredicto': 'Cubre con límites',
      'limite': {'descripcion': 'hasta USD 30 000 por gastos médicos', 'cita': 1},
    };
    await montar(tester, SingleChildScrollView(child: VistaRespuesta(r, null)), estado());
    expect(find.text('Límite: hasta USD 30 000 por gastos médicos (cita 1)'), findsOneWidget);
  });

  for (final (nombre, tamano) in [('vertical', const Size(800, 1280)), ('horizontal', const Size(1280, 800))]) {
    testWidgets('inicio en tableta $nombre: sin desbordes, sin «prueba con un ejemplo», descargo al final', (tester) async {
      final e = estado()..poliza = PolizaActual(id: 'chubb_viajes_jetsmart', nombre: 'Chubb', tipo: 'ejemplo');
      await montar(tester, const PantallaPoliza(), e, tamano: tamano);
      expect(tester.takeException(), isNull);
      expect(find.text('Prueba con un ejemplo:'), findsNothing);
      expect(find.text(Textos.masDetalles), findsOneWidget);
      expect(find.text('Preguntar'), findsOneWidget);
      expect(find.text(Textos.descargoInicio), findsOneWidget);
      // El texto no se estira de borde a borde: la tarjeta de la pregunta tiene un ancho máximo.
      final tarjeta = tester.getRect(find.ancestor(of: find.text(Textos.masDetalles), matching: find.byType(Tarjeta)).first);
      expect(tarjeta.width, lessThanOrEqualTo(760));
      // El descargo queda debajo del botón de preguntar.
      expect(tester.getRect(find.text(Textos.descargoInicio)).top, greaterThan(tester.getRect(find.text('Preguntar')).top));
    });
  }

  testWidgets('el mapa no elige un lugar por su cuenta: pide elegir o usar la ubicación', (tester) async {
    await montar(tester, const PantallaMapa(), estado(), tamano: const Size(800, 1280));
    await tester.pump(const Duration(milliseconds: 300));
    expect(tester.takeException(), isNull);
    expect(find.textContaining('Elige tu departamento y distrito'), findsOneWidget);
    expect(find.text('Usar mi ubicación'), findsOneWidget);
    expect(find.text('Buscar un distrito'), findsOneWidget);
    expect(find.textContaining('Tarapoto'), findsNothing);
  });

  testWidgets('la búsqueda de distritos encuentra sin tildes', (tester) async {
    await montar(tester, const PantallaMapa(), estado(), tamano: const Size(1280, 800));
    await tester.pump(const Duration(milliseconds: 300));
    await tester.enterText(find.byType(TextField).first, 'tarap');
    await tester.pumpAndSettle();
    expect(find.text('Tarapoto'), findsOneWidget);
    expect(sinTildes('San Martín'), 'san martin');
  });

  testWidgets('historial vacío: lo dice con texto', (tester) async {
    await montar(tester, const PantallaHistorial(), estado());
    expect(find.textContaining('Todavía no preguntaste nada'), findsOneWidget);
  });

  test('la conversación guarda como máximo 3 turnos y se puede empezar otra', () {
    final e = estado();
    final p = PolizaActual(id: 'x', nombre: 'X', tipo: 'ejemplo', documento: 'doc');
    for (var i = 0; i < 5; i++) {
      e.registrarRespuesta(p, {'modo': 'completo', 'pregunta': 'p$i', 'etiqueta_veredicto': 'Cubre', 'razonamiento': 'r$i'});
    }
    expect(e.turnos(p).map((t) => t['pregunta']), ['p2', 'p3', 'p4']);
    expect(e.sesion, hasLength(5));
    e.nuevaConversacion(p);
    expect(e.turnos(p), isEmpty);
    expect(e.sesion, hasLength(5), reason: 'el historial no se borra al empezar otra conversación');
  });
}

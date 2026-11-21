import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

import 'textos.dart';

/// El backend manda: la app no decide coberturas, topes ni planes, solo muestra lo que responde.
const apiBase = String.fromEnvironment('QMC_API', defaultValue: 'https://que-me-cubre-api.onrender.com');

class ErrorApi implements Exception {
  ErrorApi(this.mensaje, {this.codigo = '', this.status = 0});
  final String mensaje;
  final String codigo;
  final int status;

  bool get esTope => status == 429 || codigo == 'saldo_insuficiente';

  @override
  String toString() => mensaje;
}

class Api {
  Api(this.dispositivo, {http.Client? cliente}) : _http = cliente ?? http.Client();

  final String dispositivo;
  final http.Client _http;
  String? token;

  /// El servidor gratuito se duerme sin tráfico y tarda en despertar: espera larga.
  static const _espera = Duration(seconds: 150);

  Map<String, String> get _cabeceras => {
        'X-Dispositivo': dispositivo,
        if (token != null) 'Authorization': 'Bearer $token',
      };

  Uri _ruta(String ruta, [Map<String, String>? params]) => Uri.parse('$apiBase/v1$ruta').replace(queryParameters: params);

  Future<dynamic> get(String ruta, {Map<String, String>? params}) =>
      _enviar(() => _http.get(_ruta(ruta, params), headers: _cabeceras));

  /// Un archivo (el PDF de un condicionado de ejemplo).
  Future<Uint8List> getBytes(String ruta) async {
    final http.Response r;
    try {
      r = await _http.get(_ruta(ruta), headers: _cabeceras).timeout(_espera);
    } on Exception {
      throw ErrorApi(Textos.sinConexion);
    }
    if (r.statusCode >= 400) throw ErrorApi('No pude abrir el documento.', status: r.statusCode);
    return r.bodyBytes;
  }

  Future<dynamic> post(String ruta, [Object? cuerpo]) => _enviar(() => _http.post(_ruta(ruta),
      headers: {..._cabeceras, 'Content-Type': 'application/json'}, body: jsonEncode(cuerpo ?? {})));

  Future<dynamic> delete(String ruta, [Object? cuerpo]) => _enviar(() => _http.delete(_ruta(ruta),
      headers: {..._cabeceras, 'Content-Type': 'application/json'}, body: cuerpo == null ? null : jsonEncode(cuerpo)));

  Future<dynamic> subir(List<(String, Uint8List)> archivos) => _enviar(() async {
        final pedido = http.MultipartRequest('POST', _ruta('/polizas'))..headers.addAll(_cabeceras);
        for (final (nombre, datos) in archivos) {
          pedido.files.add(http.MultipartFile.fromBytes('archivos', datos, filename: nombre));
        }
        return http.Response.fromStream(await _http.send(pedido));
      });

  Future<dynamic> _enviar(Future<http.Response> Function() hacer) async {
    final http.Response r;
    try {
      r = await hacer().timeout(_espera);
    } on SocketException {
      throw ErrorApi(Textos.sinConexion);
    } on TimeoutException {
      throw ErrorApi(Textos.sinConexion);
    } on http.ClientException {
      throw ErrorApi(Textos.sinConexion);
    }
    final cuerpo = r.body.isEmpty ? null : jsonDecode(utf8.decode(r.bodyBytes));
    if (r.statusCode >= 400) {
      final detalle = cuerpo is Map ? cuerpo['detail'] : null;
      if (detalle is Map) {
        throw ErrorApi('${detalle['mensaje'] ?? 'Algo falló.'}', codigo: '${detalle['codigo'] ?? ''}', status: r.statusCode);
      }
      throw ErrorApi('Algo falló. Vuelve a intentar.', status: r.statusCode);
    }
    return cuerpo;
  }
}

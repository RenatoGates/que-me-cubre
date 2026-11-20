import 'dart:typed_data';

import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:material_ui/material_ui.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:uuid/uuid.dart';

import 'api.dart';

/// La póliza con la que se está trabajando: un condicionado de ejemplo, una subida (vive en la
/// memoria del servidor) o una guardada en la cuenta.
class PolizaActual {
  PolizaActual({required this.id, required this.nombre, required this.tipo, this.documento, this.paginas,
      this.borradoAutomatico, this.archivos = const [], this.bytes});

  String id;
  final String nombre;
  final String tipo; // ejemplo | subida | guardada
  final String? documento; // id del ejemplo o huella del PDF
  final int? paginas;
  final String? borradoAutomatico;
  final List<Map<String, dynamic>> archivos;
  final List<(String, Uint8List)>? bytes; // para volver a subirla si el servidor la olvidó

  bool get esEjemplo => tipo == 'ejemplo';
}

class Estado extends ChangeNotifier {
  static const _guardado = FlutterSecureStorage();

  late Api api;
  Map<String, dynamic> config = {};
  Map<String, dynamic>? cuenta;
  List<Map<String, dynamic>> ejemplos = [];
  PolizaActual? poliza;
  bool actualizacionObligatoria = false;
  bool _googleListo = false;
  String? _tokenGooglePendiente; // cuenta nueva con Google: espera la casilla de privacidad

  int pestana = 0;

  void irA(int i) {
    pestana = i;
    notifyListeners();
  }

  bool get conCuenta => cuenta != null;
  bool get premium => cuenta?['plan'] == 'pagado';
  bool get cuentasDisponibles => config['cuentas_disponibles'] == true;
  String get politica => '${config['politica_privacidad'] ?? 'https://github.com/RenatoGates/que-me-cubre/blob/main/docs/privacidad.md'}';
  List<Map<String, dynamic>> get guardadas => List<Map<String, dynamic>>.from(cuenta?['polizas'] ?? const []);

  Future<void> iniciar() async {
    var dispositivo = await _guardado.read(key: 'dispositivo');
    if (dispositivo == null) {
      dispositivo = 'android-${const Uuid().v4()}';
      await _guardado.write(key: 'dispositivo', value: dispositivo);
    }
    api = Api(dispositivo)..token = await _guardado.read(key: 'token');
    config = Map<String, dynamic>.from(await api.get('/app'));
    final instalada = int.tryParse((await PackageInfo.fromPlatform()).buildNumber) ?? 0;
    actualizacionObligatoria = instalada < (config['version_minima'] as int? ?? 0);
    if (actualizacionObligatoria) return;
    ejemplos = List<Map<String, dynamic>>.from(await api.get('/polizas'));
    if (api.token != null) await refrescarCuenta();
    notifyListeners();
  }

  Future<void> refrescarCuenta() async {
    try {
      cuenta = Map<String, dynamic>.from(await api.get('/cuenta'));
    } on ErrorApi catch (e) {
      if (e.status == 401) await _olvidarSesion();
    }
    notifyListeners();
  }

  Future<void> _abrirSesion(Map<String, dynamic> r) async {
    api.token = r['token'] as String;
    await _guardado.write(key: 'token', value: api.token);
    cuenta = Map<String, dynamic>.from(r['cuenta']);
    notifyListeners();
  }

  Future<void> _olvidarSesion() async {
    api.token = null;
    cuenta = null;
    await _guardado.delete(key: 'token');
    if (poliza?.tipo == 'guardada') poliza = null;
  }

  Future<void> registrar(String correo, String clave, bool acepto) async =>
      _abrirSesion(Map<String, dynamic>.from(await api.post('/cuenta/registro', {'correo': correo, 'clave': clave, 'acepto_privacidad': acepto})));

  Future<void> entrar(String correo, String clave) async =>
      _abrirSesion(Map<String, dynamic>.from(await api.post('/cuenta/sesion', {'correo': correo, 'clave': clave})));

  /// Devuelve false si la cuenta es nueva y falta aceptar la política (se llama de nuevo con acepto).
  Future<bool> entrarConGoogle({bool acepto = false}) async {
    var idToken = _tokenGooglePendiente;
    if (idToken == null) {
      if (!_googleListo) {
        await GoogleSignIn.instance.initialize(serverClientId: config['google_server_client_id'] as String?);
        _googleListo = true;
      }
      final cuentaGoogle = await GoogleSignIn.instance.authenticate();
      idToken = cuentaGoogle.authentication.idToken;
      if (idToken == null) throw ErrorApi('No pude entrar con Google. Vuelve a intentar.');
    }
    try {
      await _abrirSesion(Map<String, dynamic>.from(await api.post('/cuenta/google', {'id_token': idToken, 'acepto_privacidad': acepto})));
      _tokenGooglePendiente = null;
      return true;
    } on ErrorApi catch (e) {
      if (e.codigo == 'falta_consentimiento') {
        _tokenGooglePendiente = idToken;
        return false;
      }
      _tokenGooglePendiente = null;
      rethrow;
    }
  }

  void cancelarGoogle() => _tokenGooglePendiente = null;

  Future<void> salir() async {
    try {
      await api.delete('/cuenta/sesion');
    } on ErrorApi {
      // la sesión se olvida igual en el teléfono
    }
    if (_googleListo) await GoogleSignIn.instance.signOut();
    await _olvidarSesion();
    notifyListeners();
  }

  Future<void> borrarCuenta(String clave) async {
    await api.delete('/cuenta', {'clave': clave});
    if (_googleListo) await GoogleSignIn.instance.signOut();
    await _olvidarSesion();
    notifyListeners();
  }

  void elegir(PolizaActual? p) {
    poliza = p;
    notifyListeners();
  }

  Future<PolizaActual> subir(List<(String, Uint8List)> archivos) async {
    final r = Map<String, dynamic>.from(await api.subir(archivos));
    final nombres = archivos.map((a) => a.$1).join(' + ');
    final p = PolizaActual(id: r['poliza_id'] as String, nombre: nombres, tipo: 'subida', documento: r['documento_sha256'] as String?,
        paginas: r['paginas'] as int?, archivos: List<Map<String, dynamic>>.from(r['archivos'] ?? const []), bytes: archivos);
    elegir(p);
    return p;
  }

  /// Llama a la API con la póliza; si el servidor la olvidó (se reinició o pasó una hora), la
  /// vuelve a subir y repite.
  Future<dynamic> conPoliza(Future<dynamic> Function(String polizaId) llamar) async {
    final p = poliza!;
    try {
      return await llamar(p.id);
    } on ErrorApi catch (e) {
      if (e.codigo != 'poliza_no_encontrada' || p.bytes == null) rethrow;
      final r = Map<String, dynamic>.from(await api.subir(p.bytes!));
      p.id = r['poliza_id'] as String;
      return llamar(p.id);
    }
  }

  Future<String?> guardarEnCuenta() async {
    final r = Map<String, dynamic>.from(await api.post('/polizas/${poliza!.id}/guardar'));
    await refrescarCuenta();
    return r['borrado_automatico'] as String?;
  }
}

import 'dart:io';
import 'dart:typed_data';

import 'package:crypto/crypto.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:material_ui/material_ui.dart';
import 'package:package_info_plus/package_info_plus.dart';
import 'package:path_provider/path_provider.dart';
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

  /// La conversación es de este documento: si la póliza se vuelve a subir, sigue la misma.
  String get conversacionId => documento ?? id;
}

/// Una póliza guardada en la cuenta, tal como la devuelve /cuenta.
PolizaActual polizaGuardada(Map<String, dynamic> g) => PolizaActual(id: '${g['poliza_id']}', nombre: '${g['nombre']}', tipo: 'guardada',
    documento: g['sha256'] as String?, paginas: g['paginas'] as int?, borradoAutomatico: g['borrado_automatico'] as String?,
    archivos: List<Map<String, dynamic>>.from(g['archivos'] ?? const []));

/// Una respuesta de esta sesión: se puede volver a leer completa sin que cueste una consulta.
class EntradaHistorial {
  EntradaHistorial(this.respuesta, this.poliza, this.hora);
  final Map<String, dynamic> respuesta;
  final PolizaActual poliza;
  final DateTime hora;
}

/// La huella de un conjunto de PDF, igual que la calcula el backend (ai/subida.py, `huella`).
String huellaDe(List<Uint8List> archivos) =>
    sha256.convert([for (final a in archivos) ...sha256.convert(a).bytes]).toString();

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
  static const pestanaPoliza = 0, pestanaHistorial = 1, pestanaMapa = 2, pestanaCuenta = 3;
  static const maxTurnos = 3; // turnos anteriores que ve cada respuesta (el backend también corta en 3)
  final Map<String, List<Map<String, dynamic>>> _conversaciones = {};
  final List<EntradaHistorial> sesion = [];
  final Map<String, List<(String, Uint8List)>> _pdfs = {}; // en memoria; los de pólizas guardadas, también en el teléfono

  void irA(int i) {
    pestana = i;
    notifyListeners();
  }

  bool get conCuenta => cuenta != null;
  bool get premium => cuenta?['plan'] == 'pagado';
  bool get cuentasDisponibles => config['cuentas_disponibles'] == true;
  String get politica => '${config['politica_privacidad'] ?? 'https://renatogates.github.io/que-me-cubre/privacidad.html'}';
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
    await _olvidarLoDeLaCuenta();
    notifyListeners();
  }

  Future<void> borrarCuenta(String clave) async {
    await api.delete('/cuenta', {'clave': clave});
    if (_googleListo) await GoogleSignIn.instance.signOut();
    await _olvidarSesion();
    await _olvidarLoDeLaCuenta();
    notifyListeners();
  }

  /// Al salir o borrar la cuenta: las copias locales de los PDF y lo de esta sesión sobre pólizas guardadas.
  Future<void> _olvidarLoDeLaCuenta() async {
    sesion.removeWhere((h) => h.poliza.tipo == 'guardada');
    _pdfs.clear();
    if (poliza?.tipo == 'guardada') poliza = null;
    try {
      final carpeta = Directory('${(await getApplicationDocumentsDirectory()).path}/polizas');
      if (await carpeta.exists()) await carpeta.delete(recursive: true);
    } on Exception {
      // sin carpeta o sin acceso: no hay nada que borrar
    }
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

  // --- Conversación e historial de la sesión ---

  List<Map<String, dynamic>> conversacion(PolizaActual p) => _conversaciones[p.conversacionId] ?? const [];

  /// Los últimos turnos de la conversación sobre esta póliza, en la forma que pide el backend.
  List<Map<String, String>> turnos(PolizaActual p) => [
        for (final r in conversacion(p).reversed.take(maxTurnos).toList().reversed)
          {'pregunta': '${r['pregunta'] ?? ''}', 'veredicto': '${r['etiqueta_veredicto'] ?? ''}', 'razonamiento': '${r['razonamiento'] ?? ''}'}
      ];

  void registrarRespuesta(PolizaActual p, Map<String, dynamic> r) {
    if (r['modo'] == 'aclaracion') return;
    for (final sub in r['modo'] == 'varias' ? (r['respuestas'] as List) : [r]) {
      _conversaciones.putIfAbsent(p.conversacionId, () => []).add(Map<String, dynamic>.from(sub as Map));
    }
    sesion.insert(0, EntradaHistorial(r, p, DateTime.now()));
    notifyListeners();
  }

  void nuevaConversacion(PolizaActual p) {
    _conversaciones.remove(p.conversacionId);
    notifyListeners();
  }

  // --- El PDF de la póliza, para abrirlo en la página de una cita. Nunca sale del teléfono. ---

  Future<File> _archivoLocal(String polizaId, int i) async =>
      File('${(await getApplicationDocumentsDirectory()).path}/polizas/${polizaId}_$i.pdf');

  /// Los PDF de la póliza si ya están en el teléfono (o, si es un ejemplo, descargados del
  /// servidor: son públicos). null si hace falta que la persona elija su PDF.
  Future<List<(String, Uint8List)>?> pdfDe(PolizaActual p) async {
    if (p.bytes != null) return p.bytes;
    if (_pdfs[p.id] != null) return _pdfs[p.id];
    if (p.esEjemplo) {
      final datos = await api.getBytes('/polizas/${p.id}/pdf');
      return _pdfs[p.id] = [('${p.id}.pdf', datos)];
    }
    final copias = <(String, Uint8List)>[];
    for (var i = 0;; i++) {
      final f = await _archivoLocal(p.id, i);
      if (!await f.exists()) break;
      copias.add(('${p.nombre} ($i)', await f.readAsBytes()));
    }
    if (copias.isNotEmpty && (p.documento == null || huellaDe([for (final c in copias) c.$2]) == p.documento)) {
      return _pdfs[p.id] = copias;
    }
    return null;
  }

  /// La persona eligió su PDF para una póliza guardada: se comprueba que sea el mismo documento y
  /// se guarda una copia solo en el teléfono, para no pedírselo otra vez.
  Future<bool> recordarPdf(PolizaActual p, List<(String, Uint8List)> archivos) async {
    if (p.documento != null && huellaDe([for (final a in archivos) a.$2]) != p.documento) return false;
    for (final (i, a) in archivos.indexed) {
      final f = await _archivoLocal(p.id, i);
      await f.parent.create(recursive: true);
      await f.writeAsBytes(a.$2, flush: true);
    }
    _pdfs[p.id] = archivos;
    return true;
  }

  Future<void> olvidarPdfLocal(String polizaId) async {
    _pdfs.remove(polizaId);
    for (var i = 0;; i++) {
      final f = await _archivoLocal(polizaId, i);
      if (!await f.exists()) break;
      await f.delete();
    }
  }

}

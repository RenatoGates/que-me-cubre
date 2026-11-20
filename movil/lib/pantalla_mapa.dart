import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api.dart';
import 'comun.dart';
import 'resultado.dart';
import 'tema.dart';

/// Clínicas y hospitales cercanos. Los datos son del registro de SUSALUD (RENIPRESS); el mapa,
/// de OpenStreetMap. La ubicación se usa solo en el teléfono: no se envía al servidor.
class PantallaMapa extends StatefulWidget {
  const PantallaMapa({super.key});

  @override
  State<PantallaMapa> createState() => _PantallaMapaState();
}

class _PantallaMapaState extends State<PantallaMapa> {
  final _mapa = MapController();
  List<Mapa> _departamentos = [];
  List<Mapa> _distritos = [];
  String? _departamento;
  Mapa? _distrito;
  bool _soloInternamiento = false;
  Mapa? _datos;
  List<List<dynamic>> _conInternamiento = [];
  List<(String, String, LatLng, double)> _cercanos = [];
  LatLng? _yo;
  bool _cargando = true;
  String? _error;
  List<Mapa> _clinicasDePoliza = [];
  String? _clinicasDe;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_departamentos.isEmpty && _cargando) _iniciar();
    final p = EstadoScope.of(context).poliza;
    if (p != null && p.id != _clinicasDe) _cargarClinicas(p.id);
  }

  Future<void> _cargarClinicas(String polizaId) async {
    _clinicasDe = polizaId;
    try {
      final r = await EstadoScope.of(context).api.get('/polizas/$polizaId/clinicas');
      if (mounted) setState(() => _clinicasDePoliza = List<Mapa>.from((r['clinicas'] as List).map((x) => Map<String, dynamic>.from(x as Map))));
    } catch (_) {
      if (mounted) setState(() => _clinicasDePoliza = []);
    }
  }

  Future<void> _iniciar() async {
    final api = EstadoScope.of(context).api;
    try {
      _departamentos = List<Mapa>.from((await api.get('/mapa/departamentos') as List).map((x) => Map<String, dynamic>.from(x as Map)));
      _departamento = _departamentos.any((d) => d['id'] == 'SAN MARTIN') ? 'SAN MARTIN' : _departamentos.first['id'] as String;
      await _cargarDistritos(preferido: 'TARAPOTO');
    } catch (e) {
      _error = '$e';
    }
    if (mounted) setState(() => _cargando = false);
  }

  Future<void> _cargarDistritos({String? preferido}) async {
    final api = EstadoScope.of(context).api;
    _distritos = List<Mapa>.from((await api.get('/mapa/distritos', params: {'departamento': _departamento!}) as List)
        .map((x) => Map<String, dynamic>.from(x as Map)));
    _distrito = _distritos.firstWhere((d) => d['distrito'] == preferido, orElse: () => _distritos.first);
    await _cargarEstablecimientos();
  }

  Future<void> _cargarEstablecimientos() async {
    final api = EstadoScope.of(context).api;
    setState(() => _cargando = true);
    try {
      _datos = Map<String, dynamic>.from(await api.get('/mapa/establecimientos', params: {
        'departamento': _departamento!,
        'provincia': '${_distrito!['provincia']}',
        'distrito': '${_distrito!['distrito']}',
        'solo_internamiento': '$_soloInternamiento',
      }));
      final c = _datos!['centro'] as Map?;
      if (c != null && _yo == null) _mapa.move(LatLng((c['lat'] as num).toDouble(), (c['lon'] as num).toDouble()), 13);
    } catch (e) {
      if (mounted) mostrarError(context, e);
    }
    if (mounted) setState(() => _cargando = false);
  }

  double _km(LatLng a, LatLng b) => const Distance().as(LengthUnit.Meter, a, b) / 1000;

  Future<void> _usarUbicacion() async {
    final api = EstadoScope.of(context).api;
    var permiso = await Geolocator.checkPermission();
    if (permiso == LocationPermission.denied) permiso = await Geolocator.requestPermission();
    if (permiso == LocationPermission.denied || permiso == LocationPermission.deniedForever) {
      if (mounted) mostrarError(context, ErrorApi('Sin permiso de ubicación: elige tu departamento y distrito.'));
      return;
    }
    setState(() => _cargando = true);
    try {
      final pos = await Geolocator.getCurrentPosition(locationSettings: const LocationSettings(accuracy: LocationAccuracy.medium));
      _yo = LatLng(pos.latitude, pos.longitude);
      if (_conInternamiento.isEmpty) {
        final r = await api.get('/mapa/con-internamiento');
        _conInternamiento = (r['establecimientos'] as List).map((x) => x as List).toList();
      }
      final todos = [
        for (final f in _conInternamiento)
          ('${f[0]}', '${f[1]}', LatLng((f[2] as num).toDouble(), (f[3] as num).toDouble()))
      ];
      _cercanos = [for (final (n, t, p) in todos) (n, t, p, _km(_yo!, p))]..sort((a, b) => a.$4.compareTo(b.$4));
      _cercanos = _cercanos.take(8).toList();
      _mapa.move(_yo!, 13);
    } catch (e) {
      if (mounted) mostrarError(context, e);
    }
    if (mounted) setState(() => _cargando = false);
  }

  @override
  Widget build(BuildContext context) {
    final establecimientos = [for (final x in (_datos?['establecimientos'] as List? ?? [])) Map<String, dynamic>.from(x as Map)];
    final conCoordenadas = establecimientos.where((x) => x['lat'] != null && x['lon'] != null).toList();
    final fuente = Map<String, dynamic>.from(_datos?['fuente'] as Map? ?? {});
    final ancho = MediaQuery.sizeOf(context).width;
    return SafeArea(
      child: _error != null
          ? Center(child: Padding(padding: const EdgeInsets.all(24), child: Aviso(_error!)))
          : ListView(padding: EdgeInsets.symmetric(horizontal: ancho > 900 ? 32 : 16, vertical: 16), children: [
              Semantics(header: true, child: Text('Cerca de ti', style: Theme.of(context).textTheme.headlineMedium)),
              const SizedBox(height: 4),
              const Text('Clínicas y hospitales de tu zona. Tu ubicación no se guarda ni se envía.', style: TextStyle(color: Paleta.textoSecundario)),
              const SizedBox(height: 16),
              Tarjeta(
                padding: const EdgeInsets.all(16),
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  FilledButton.icon(onPressed: _usarUbicacion, icon: const Icon(Icons.my_location_rounded), label: const Text('Usar mi ubicación')),
                  const SizedBox(height: 14),
                  Wrap(spacing: 12, runSpacing: 12, children: [
                    SizedBox(
                      width: ancho > 700 ? 300 : double.infinity,
                      child: DropdownButtonFormField<String>(
                        initialValue: _departamento,
                        isExpanded: true,
                        decoration: const InputDecoration(labelText: 'Departamento'),
                        items: [for (final d in _departamentos) DropdownMenuItem(value: '${d['id']}', child: Text('${d['nombre']}'))],
                        onChanged: (v) async {
                          _departamento = v;
                          await _cargarDistritos();
                          if (mounted) setState(() {});
                        },
                      ),
                    ),
                    SizedBox(
                      width: ancho > 700 ? 300 : double.infinity,
                      child: DropdownButtonFormField<Mapa>(
                        key: ValueKey(_departamento),
                        initialValue: _distrito,
                        isExpanded: true,
                        decoration: const InputDecoration(labelText: 'Distrito'),
                        items: [
                          for (final d in _distritos)
                            DropdownMenuItem(value: d, child: Text('${d['nombre']} (${d['nombre_provincia']})', overflow: TextOverflow.ellipsis))
                        ],
                        onChanged: (v) {
                          _distrito = v;
                          _cargarEstablecimientos();
                        },
                      ),
                    ),
                  ]),
                  SwitchListTile(
                    contentPadding: EdgeInsets.zero,
                    value: _soloInternamiento,
                    activeThumbColor: Paleta.accion,
                    title: const Text('Solo hospitales y clínicas con internamiento'),
                    onChanged: (v) {
                      setState(() => _soloInternamiento = v);
                      _cargarEstablecimientos();
                    },
                  ),
                ]),
              ),
              const SizedBox(height: 16),
              ClipRRect(
                borderRadius: BorderRadius.circular(20),
                child: SizedBox(
                  height: ancho > 900 ? 460 : 360,
                  child: Semantics(
                    label: 'Mapa con ${conCoordenadas.length} establecimientos del distrito',
                    child: FlutterMap(
                      mapController: _mapa,
                      options: const MapOptions(initialCenter: LatLng(-6.4875, -76.3647), initialZoom: 13),
                      children: [
                        TileLayer(urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', userAgentPackageName: 'com.renatogates.quecubre'),
                        MarkerLayer(markers: [
                          for (final x in conCoordenadas)
                            Marker(
                              point: LatLng((x['lat'] as num).toDouble(), (x['lon'] as num).toDouble()),
                              width: 34,
                              height: 34,
                              child: Tooltip(
                                message: '${x['nombre']}',
                                child: Icon(Icons.location_on, size: 34,
                                    color: '${x['tipo']}'.contains('CON INTERNAMIENTO') ? Paleta.noCubierto : Paleta.accion),
                              ),
                            ),
                          if (_yo != null)
                            Marker(point: _yo!, width: 28, height: 28,
                                child: const Tooltip(message: 'Tu ubicación', child: Icon(Icons.radio_button_checked, color: Paleta.parcial, size: 28))),
                        ]),
                        RichAttributionWidget(
                          alignment: AttributionAlignment.bottomLeft,
                          showFlutterMapAttribution: false,
                          attributions: [
                            TextSourceAttribution('Colaboradores de OpenStreetMap',
                                onTap: () => launchUrl(Uri.parse('https://www.openstreetmap.org/copyright'))),
                          ],
                        ),
                        const Align(
                          alignment: Alignment.bottomRight,
                          child: Padding(
                            padding: EdgeInsets.all(6),
                            child: DecoratedBox(
                              decoration: BoxDecoration(color: Color(0xE6FFFFFF), borderRadius: BorderRadius.all(Radius.circular(6))),
                              child: Padding(
                                padding: EdgeInsets.symmetric(horizontal: 6, vertical: 3),
                                child: Text('© OpenStreetMap', style: TextStyle(color: Color(0xFF1A1A1A), fontSize: 12)),
                              ),
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
              const SizedBox(height: 8),
              const Wrap(spacing: 16, children: [
                _Leyenda(Paleta.noCubierto, 'Con internamiento'),
                _Leyenda(Paleta.accion, 'Otros establecimientos'),
                _Leyenda(Paleta.parcial, 'Tú', icono: Icons.radio_button_checked),
              ]),
              if (_cargando) const Cargando('Cargando establecimientos…'),
              if (_cercanos.isNotEmpty) ...[
                const SizedBox(height: 16),
                Tarjeta(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Titulo('Con internamiento más cerca de ti', icono: Icons.near_me_rounded),
                    const SizedBox(height: 10),
                    for (final (n, t, p, km) in _cercanos)
                      ListTile(
                        contentPadding: EdgeInsets.zero,
                        leading: const ExcludeSemantics(child: Icon(Icons.local_hospital_rounded, color: Paleta.noCubierto)),
                        title: Text(n),
                        subtitle: Text('$t · a ${km.toStringAsFixed(km < 10 ? 1 : 0)} km en línea recta',
                            style: const TextStyle(color: Paleta.textoSecundario)),
                        onTap: () => _mapa.move(p, 15),
                      ),
                  ]),
                ),
              ],
              if (_clinicasDePoliza.isNotEmpty) ...[
                const SizedBox(height: 16),
                Tarjeta(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Titulo('Las que nombra tu póliza', icono: Icons.verified_rounded),
                    const SizedBox(height: 6),
                    const Text('Que tu póliza las nombre no dice para qué coberturas están en convenio: lee la cita.',
                        style: TextStyle(color: Paleta.textoSecundario)),
                    const SizedBox(height: 10),
                    for (final c in _clinicasDePoliza)
                      TarjetaCita({...c, 'n': c['nombre'], 'texto_literal': c['cita']}, EstadoScope.of(context).poliza?.archivos ?? const []),
                  ]),
                ),
              ],
              const SizedBox(height: 16),
              Tarjeta(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Titulo('Registro de SUSALUD en ${_distrito?['nombre'] ?? 'tu distrito'}', icono: Icons.list_alt_rounded),
                  const SizedBox(height: 6),
                  Aviso('${_datos?['aviso'] ?? 'Son establecimientos registrados en SUSALUD, no la red de tu aseguradora.'}',
                      icono: Icons.local_hospital_outlined, color: Paleta.parcial),
                  const SizedBox(height: 10),
                  Text('${establecimientos.length} establecimientos activos', style: const TextStyle(color: Paleta.textoSecundario)),
                  for (final x in establecimientos.take(60))
                    ListTile(
                      contentPadding: EdgeInsets.zero,
                      leading: ExcludeSemantics(
                          child: Icon(Icons.local_hospital_outlined,
                              color: '${x['tipo']}'.contains('CON INTERNAMIENTO') ? Paleta.noCubierto : Paleta.accion)),
                      title: Text('${x['nombre']}'),
                      subtitle: Text([x['clasificacion'], x['direccion'], x['telefono']].where((v) => v != null && '$v'.isNotEmpty).join(' · '),
                          style: const TextStyle(color: Paleta.textoSecundario)),
                      onTap: x['lat'] == null ? null : () => _mapa.move(LatLng((x['lat'] as num).toDouble(), (x['lon'] as num).toDouble()), 16),
                    ),
                  const Divider(height: 24),
                  Text(
                    'Fuente: RENIPRESS, Superintendencia Nacional de Salud (SUSALUD), en datosabiertos.gob.pe'
                    '${fuente['corte'] != null ? ', corte del ${fuente['corte']}' : ''}. Licencia ODC-BY. Solo establecimientos activos.',
                    style: const TextStyle(color: Paleta.textoSecundario, fontSize: 13),
                  ),
                ]),
              ),
            ]),
    );
  }
}

class _Leyenda extends StatelessWidget {
  const _Leyenda(this.color, this.texto, {this.icono = Icons.location_on});
  final Color color;
  final String texto;
  final IconData icono;

  @override
  Widget build(BuildContext context) => Row(mainAxisSize: MainAxisSize.min, children: [
        ExcludeSemantics(child: Icon(icono, color: color, size: 18)),
        const SizedBox(width: 4),
        Text(texto, style: const TextStyle(color: Paleta.textoSecundario, fontSize: 13)),
      ]);
}


import 'package:flutter_map/flutter_map.dart';
import 'package:geolocator/geolocator.dart';
import 'package:latlong2/latlong.dart';
import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api.dart';
import 'comun.dart';
import 'resultado.dart';
import 'tema.dart';

/// Radio en el que se buscan hospitales y clínicas con internamiento alrededor de la persona.
const radioKm = 10.0;

/// Un establecimiento para el mapa y la lista de abajo.
class Lugar {
  Lugar(this.nombre, this.tipo, this.punto, {this.distrito, this.internamiento = false, this.km});
  final String nombre;
  final String tipo;
  final LatLng punto;
  final String? distrito;
  final bool internamiento;
  final double? km;
}

String sinTildes(String s) => s
    .toLowerCase()
    .replaceAll(RegExp('[áàä]'), 'a')
    .replaceAll(RegExp('[éèë]'), 'e')
    .replaceAll(RegExp('[íìï]'), 'i')
    .replaceAll(RegExp('[óòö]'), 'o')
    .replaceAll(RegExp('[úùü]'), 'u');

double distanciaKm(LatLng a, LatLng b) => const Distance().as(LengthUnit.Meter, a, b) / 1000;

String textoKm(double km) => '${km.toStringAsFixed(km < 10 ? 1 : 0)} km';

/// Clínicas y hospitales cercanos. Los datos son del registro de SUSALUD (RENIPRESS); el mapa,
/// de OpenStreetMap. La ubicación se usa solo en el teléfono: no se envía al servidor.
/// No hay un lugar por defecto: sin ubicación ni elección, se le pide a la persona que elija.
class PantallaMapa extends StatefulWidget {
  const PantallaMapa({super.key});

  @override
  State<PantallaMapa> createState() => _PantallaMapaState();
}

class _PantallaMapaState extends State<PantallaMapa> {
  final _mapa = MapController();
  bool _mapaListo = false;
  List<Mapa> _departamentos = [];
  List<Mapa> _distritos = [];
  List<Mapa> _todosLosDistritos = [];
  String? _departamento;
  Mapa? _distrito;
  bool _soloInternamiento = false;
  Mapa? _datos;
  List<List<dynamic>> _conInternamiento = [];
  List<Lugar> _cercanos = [];
  LatLng? _yo;
  LatLng? _centro;
  bool _iniciado = false;
  bool _cargando = false;
  bool _ubicando = false;
  String? _error;
  List<Mapa> _clinicasDePoliza = [];
  String? _clinicasDe;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_iniciado) {
      _iniciado = true;
      _iniciar();
    }
    final p = EstadoScope.of(context).poliza;
    if (p != null && p.id != _clinicasDe) _cargarClinicas(p.id);
  }

  Future<void> _cargarClinicas(String polizaId) async {
    _clinicasDe = polizaId;
    try {
      final r = await EstadoScope.of(context).api.get('/polizas/$polizaId/clinicas');
      if (mounted) setState(() => _clinicasDePoliza = lista(r['clinicas']));
    } catch (_) {
      if (mounted) setState(() => _clinicasDePoliza = []);
    }
  }

  Future<void> _iniciar() async {
    final api = EstadoScope.of(context).api;
    try {
      _departamentos = lista(await api.get('/mapa/departamentos'));
      _todosLosDistritos = lista(await api.get('/mapa/distritos-todos'));
    } catch (e) {
      _error = '$e';
    }
    if (mounted) setState(() {});
  }

  String _claveDistrito(Mapa d) => '${d['provincia']}|${d['distrito']}';

  /// Elige un distrito (desde las listas, la búsqueda o la ubicación) y carga sus establecimientos.
  Future<void> _elegir(String departamento, {String? provincia, String? distrito, bool centrar = true}) async {
    final api = EstadoScope.of(context).api;
    setState(() {
      _cargando = true;
      _departamento = departamento;
      _distrito = null;
      _datos = null;
    });
    try {
      _distritos = lista(await api.get('/mapa/distritos', params: {'departamento': departamento}));
      if (distrito != null) {
        _distrito = _distritos.where((d) => d['distrito'] == distrito && (provincia == null || d['provincia'] == provincia)).firstOrNull;
      }
      if (_distrito != null) await _cargarEstablecimientos(centrar: centrar);
    } catch (e) {
      if (mounted) mostrarError(context, e);
    }
    if (mounted) setState(() => _cargando = false);
  }

  Future<void> _cargarEstablecimientos({bool centrar = true}) async {
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
      if (centrar && c != null) _mover(LatLng((c['lat'] as num).toDouble(), (c['lon'] as num).toDouble()), 13);
    } catch (e) {
      if (mounted) mostrarError(context, e);
    }
    if (mounted) setState(() => _cargando = false);
  }

  void _mover(LatLng p, double zoom) {
    _centro ??= p;
    if (_mapaListo) _mapa.move(p, zoom);
  }

  Future<void> _usarUbicacion() async {
    final api = EstadoScope.of(context).api;
    var permiso = await Geolocator.checkPermission();
    if (permiso == LocationPermission.denied) permiso = await Geolocator.requestPermission();
    if (permiso == LocationPermission.denied || permiso == LocationPermission.deniedForever) {
      if (mounted) mostrarError(context, ErrorApi('Sin permiso de ubicación: elige tu departamento y distrito.'));
      return;
    }
    setState(() => _ubicando = true);
    try {
      final pos = await Geolocator.getCurrentPosition(locationSettings: const LocationSettings(accuracy: LocationAccuracy.medium));
      final yo = LatLng(pos.latitude, pos.longitude);
      if (_conInternamiento.isEmpty) {
        final r = await api.get('/mapa/con-internamiento');
        _conInternamiento = (r['establecimientos'] as List).map((x) => x as List).toList();
      }
      final todos = [
        for (final f in _conInternamiento)
          Lugar('${f[0]}', '${f[1]}', LatLng((f[2] as num).toDouble(), (f[3] as num).toDouble()),
              distrito: '${f.length > 6 ? f[6] : ''}', internamiento: true,
              km: distanciaKm(yo, LatLng((f[2] as num).toDouble(), (f[3] as num).toDouble())))
      ]..sort((a, b) => a.km!.compareTo(b.km!));
      _yo = yo;
      _cercanos = todos.where((l) => l.km! <= radioKm).toList();
      if (_cercanos.isEmpty) _cercanos = todos.take(3).toList(); // ninguno en el radio: los más cercanos, con su distancia
      _mover(yo, 13);
      // El distrito: el del hospital con internamiento más cercano. Se ve y se puede cambiar.
      final f = _conInternamiento.isEmpty
          ? null
          : _conInternamiento.reduce((a, b) => distanciaKm(yo, LatLng((a[2] as num).toDouble(), (a[3] as num).toDouble())) <=
                  distanciaKm(yo, LatLng((b[2] as num).toDouble(), (b[3] as num).toDouble()))
              ? a
              : b);
      if (f != null && f.length > 6) await _elegir('${f[4]}', provincia: '${f[5]}', distrito: '${f[6]}', centrar: false);
    } catch (e) {
      if (mounted) mostrarError(context, e);
    }
    if (mounted) setState(() => _ubicando = false);
  }

  @override
  Widget build(BuildContext context) {
    final ancho = MediaQuery.sizeOf(context).width;
    if (_error != null) return SafeArea(child: Center(child: Padding(padding: const EdgeInsets.all(24), child: Aviso(_error!))));
    final establecimientos = lista(_datos?['establecimientos']);
    final lugares = [
      for (final x in establecimientos.where((x) => x['lat'] != null && x['lon'] != null))
        Lugar('${x['nombre']}', '${x['clasificacion'] ?? ''}', LatLng((x['lat'] as num).toDouble(), (x['lon'] as num).toDouble()),
            distrito: '${_distrito?['nombre'] ?? ''}', internamiento: '${x['tipo']}'.contains('CON INTERNAMIENTO'),
            km: _yo == null ? null : distanciaKm(_yo!, LatLng((x['lat'] as num).toDouble(), (x['lon'] as num).toDouble())))
    ];
    if (_yo != null) lugares.sort((a, b) => a.km!.compareTo(b.km!));
    final hayLugar = _distrito != null || _yo != null;
    return SafeArea(
      child: SingleChildScrollView(
        padding: EdgeInsets.symmetric(horizontal: ancho > 900 ? 32 : 16, vertical: 16),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1000),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Semantics(header: true, child: Text('Cerca de ti', style: Theme.of(context).textTheme.headlineMedium)),
              const SizedBox(height: 4),
              const Text('Clínicas y hospitales de tu zona. Tu ubicación no se guarda ni se envía.', style: TextStyle(color: Paleta.textoSecundario)),
              const SizedBox(height: 16),
              _controles(ancho),
              const SizedBox(height: 16),
              if (!hayLugar)
                const Aviso('Elige tu departamento y distrito, búscalo por su nombre o usa tu ubicación para ver las clínicas cercanas.',
                    icono: Icons.travel_explore_rounded)
              else ...[
                _elMapa(ancho, lugares),
                const SizedBox(height: 8),
                const Wrap(spacing: 16, runSpacing: 6, children: [
                  _Leyenda(_PinClinica(internamiento: true, tamano: 22), 'Con internamiento'),
                  _Leyenda(_PinClinica(internamiento: false, tamano: 22), 'Otros establecimientos'),
                  _Leyenda(_PuntoYo(tamano: 18), 'Tú'),
                ]),
                if (_cargando || _ubicando) const Cargando('Cargando establecimientos…'),
                if (_yo != null && _cercanos.isNotEmpty) ...[const SizedBox(height: 16), _tarjetaCercanos()],
                if (_distrito != null && _datos != null) ...[const SizedBox(height: 16), _tarjetaDistrito(establecimientos, lugares)],
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
                      TarjetaCita({...c, 'n': c['nombre'], 'texto_literal': c['cita']}, EstadoScope.of(context).poliza),
                  ]),
                ),
              ],
            ]),
          ),
        ),
      ),
    );
  }

  Widget _controles(double ancho) {
    final anchoCampo = ancho > 700 ? 300.0 : double.infinity;
    return Tarjeta(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Wrap(spacing: 12, runSpacing: 12, crossAxisAlignment: WrapCrossAlignment.center, children: [
          FilledButton.icon(
            onPressed: _ubicando ? null : _usarUbicacion,
            icon: const Icon(Icons.my_location_rounded),
            label: Text(_ubicando ? 'Buscando dónde estás…' : 'Usar mi ubicación'),
          ),
          SizedBox(width: ancho > 700 ? 380 : double.infinity, child: _buscador()),
        ]),
        const SizedBox(height: 14),
        Wrap(spacing: 12, runSpacing: 12, children: [
          SizedBox(
            width: anchoCampo,
            child: DropdownButtonFormField<String>(
              key: ValueKey('dep-$_departamento'),
              initialValue: _departamento,
              isExpanded: true,
              hint: const Text('Elige'),
              decoration: const InputDecoration(labelText: 'Departamento'),
              items: [for (final d in _departamentos) DropdownMenuItem(value: '${d['id']}', child: Text('${d['nombre']}'))],
              onChanged: (v) => v == null ? null : _elegir(v),
            ),
          ),
          SizedBox(
            width: anchoCampo,
            child: DropdownButtonFormField<String>(
              key: ValueKey('dis-$_departamento-${_distrito == null ? '' : _claveDistrito(_distrito!)}'),
              initialValue: _distrito == null ? null : _claveDistrito(_distrito!),
              isExpanded: true,
              hint: Text(_departamento == null ? 'Primero el departamento' : 'Elige'),
              decoration: const InputDecoration(labelText: 'Distrito'),
              items: [
                for (final d in _distritos)
                  DropdownMenuItem(value: _claveDistrito(d), child: Text('${d['nombre']} (${d['nombre_provincia']})', overflow: TextOverflow.ellipsis))
              ],
              onChanged: (v) {
                final d = _distritos.where((d) => _claveDistrito(d) == v).firstOrNull;
                if (d == null) return;
                setState(() => _distrito = d);
                _cargarEstablecimientos();
              },
            ),
          ),
        ]),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          value: _soloInternamiento,
          title: const Text('Solo hospitales y clínicas con internamiento'),
          onChanged: (v) {
            setState(() => _soloInternamiento = v);
            if (_distrito != null) _cargarEstablecimientos();
          },
        ),
      ]),
    );
  }

  Widget _buscador() => Autocomplete<Mapa>(
        displayStringForOption: (d) => '${d['nombre']}',
        optionsBuilder: (v) {
          final q = sinTildes(v.text.trim());
          if (q.length < 2) return const Iterable<Mapa>.empty();
          return _todosLosDistritos.where((d) => sinTildes('${d['nombre']}').contains(q)).take(20);
        },
        onSelected: (d) {
          FocusScope.of(context).unfocus();
          _elegir('${d['departamento']}', provincia: '${d['provincia']}', distrito: '${d['distrito']}');
        },
        fieldViewBuilder: (context, controlador, foco, alEnviar) => TextField(
          controller: controlador,
          focusNode: foco,
          onSubmitted: (_) => alEnviar(),
          decoration: const InputDecoration(labelText: 'Buscar un distrito', prefixIcon: Icon(Icons.search_rounded)),
        ),
        optionsViewBuilder: (context, alElegir, opciones) => Align(
          alignment: Alignment.topLeft,
          child: Material(
            color: Paleta.superficie,
            elevation: 4,
            borderRadius: BorderRadius.circular(14),
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxHeight: 320, maxWidth: 420),
              child: ListView(shrinkWrap: true, padding: EdgeInsets.zero, children: [
                for (final d in opciones)
                  ListTile(
                    title: Text('${d['nombre']}'),
                    subtitle: Text('${d['nombre_provincia']}, ${d['nombre_departamento']}', style: const TextStyle(color: Paleta.textoSecundario)),
                    onTap: () => alElegir(d),
                  ),
              ]),
            ),
          ),
        ),
      );

  Widget _elMapa(double ancho, List<Lugar> lugares) {
    final enMapa = [...lugares, for (final c in _cercanos) if (!lugares.any((l) => l.nombre == c.nombre)) c];
    final centro = _centro ?? _yo ?? (lugares.isNotEmpty ? lugares.first.punto : null);
    if (centro == null) return const SizedBox(height: 0);
    return ClipRRect(
      borderRadius: BorderRadius.circular(20),
      child: SizedBox(
        height: ancho > 700 ? 440 : 340,
        child: Semantics(
          label: 'Mapa con ${enMapa.length} establecimientos${_yo != null ? ' y tu ubicación' : ''}',
          child: FlutterMap(
            mapController: _mapa,
            options: MapOptions(initialCenter: centro, initialZoom: 13, onMapReady: () => _mapaListo = true),
            children: [
              TileLayer(urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png', userAgentPackageName: 'com.renatogates.quecubre'),
              MarkerLayer(markers: [
                for (final l in enMapa.where((l) => !l.internamiento))
                  Marker(point: l.punto, width: 30, height: 30,
                      child: Tooltip(message: l.nombre, child: const _PinClinica(internamiento: false, tamano: 30))),
                for (final l in enMapa.where((l) => l.internamiento))
                  Marker(point: l.punto, width: 36, height: 36,
                      child: Tooltip(message: l.nombre, child: const _PinClinica(internamiento: true, tamano: 36))),
                if (_yo != null)
                  Marker(point: _yo!, width: 30, height: 30, child: const Tooltip(message: 'Tu ubicación', child: _PuntoYo(tamano: 26))),
              ]),
              RichAttributionWidget(
                alignment: AttributionAlignment.bottomLeft,
                showFlutterMapAttribution: false,
                attributions: [
                  TextSourceAttribution('Colaboradores de OpenStreetMap', onTap: () => launchUrl(Uri.parse('https://www.openstreetmap.org/copyright'))),
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
                      child: Text('© OpenStreetMap', style: TextStyle(color: Paleta.texto, fontSize: 12)),
                    ),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _tarjetaCercanos() {
    final enRadio = _cercanos.where((l) => l.km! <= radioKm).length;
    return Tarjeta(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Titulo('Con internamiento cerca de ti', icono: Icons.near_me_rounded),
        const SizedBox(height: 6),
        Text(
          enRadio > 0
              ? 'Encontré $enRadio hospital${enRadio == 1 ? '' : 'es'} o clínica${enRadio == 1 ? '' : 's'} con internamiento a menos de ${radioKm.toStringAsFixed(0)} km de ti.'
              : 'No hay hospitales ni clínicas con internamiento a menos de ${radioKm.toStringAsFixed(0)} km de ti. Estos son los más cercanos:',
          style: const TextStyle(color: Paleta.textoSecundario),
        ),
        const SizedBox(height: 6),
        for (final l in _cercanos) _FilaLugar(l, alTocar: () => _mapa.move(l.punto, 15)),
      ]),
    );
  }

  Widget _tarjetaDistrito(List<Mapa> establecimientos, List<Lugar> lugares) {
    final fuente = Map<String, dynamic>.from(_datos?['fuente'] as Map? ?? {});
    final nombre = '${_distrito?['nombre'] ?? 'tu distrito'}';
    final sinCoordenadas = establecimientos.length - lugares.length;
    return Tarjeta(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Titulo('En $nombre', icono: Icons.list_alt_rounded),
        const SizedBox(height: 6),
        Aviso('${_datos?['aviso'] ?? 'Son establecimientos registrados en SUSALUD, no la red de tu aseguradora.'}',
            icono: Icons.local_hospital_outlined, color: Paleta.parcial),
        const SizedBox(height: 10),
        Text(
          establecimientos.isEmpty
              ? 'No hay establecimientos${_soloInternamiento ? ' con internamiento' : ''} activos registrados en $nombre.'
              : '${establecimientos.length} establecimiento${establecimientos.length == 1 ? '' : 's'}${_soloInternamiento ? ' con internamiento' : ''} '
                  'activo${establecimientos.length == 1 ? '' : 's'} en el distrito de $nombre'
                  '${sinCoordenadas > 0 ? ' ($sinCoordenadas sin ubicación en el mapa)' : ''}'
                  '${_yo != null ? ', ordenados por distancia a ti' : ''}.',
          style: const TextStyle(color: Paleta.textoSecundario),
        ),
        for (final l in lugares.take(60)) _FilaLugar(l, alTocar: () => _mapa.move(l.punto, 16)),
        if (lugares.length > 60)
          Text('Y ${lugares.length - 60} más en el mapa.', style: const TextStyle(color: Paleta.textoSecundario)),
        const Divider(height: 24),
        Text(
          'Fuente: RENIPRESS, Superintendencia Nacional de Salud (SUSALUD), en datosabiertos.gob.pe'
          '${fuente['corte'] != null ? ', corte del ${fuente['corte']}' : ''}. Licencia ODC-BY. Solo establecimientos activos.',
          style: const TextStyle(color: Paleta.textoSecundario, fontSize: 13),
        ),
      ]),
    );
  }
}

class _FilaLugar extends StatelessWidget {
  const _FilaLugar(this.l, {required this.alTocar});
  final Lugar l;
  final VoidCallback alTocar;

  @override
  Widget build(BuildContext context) => ListTile(
        contentPadding: EdgeInsets.zero,
        leading: ExcludeSemantics(child: _PinClinica(internamiento: l.internamiento, tamano: 28)),
        title: Text(l.nombre),
        subtitle: Text(
          [
            if ((l.distrito ?? '').isNotEmpty) _nombrePropio(l.distrito!),
            if (l.tipo.isNotEmpty) l.tipo,
            if (l.km != null) 'a ${textoKm(l.km!)} en línea recta',
          ].join(' · '),
          style: const TextStyle(color: Paleta.textoSecundario),
        ),
        onTap: alTocar,
      );

  static String _nombrePropio(String s) =>
      s.split(' ').map((p) => p.isEmpty ? p : p[0].toUpperCase() + p.substring(1).toLowerCase()).join(' ');
}

/// Las clínicas: un alfiler con cruz. Azul si tiene internamiento; gris cálido si no.
class _PinClinica extends StatelessWidget {
  const _PinClinica({required this.internamiento, required this.tamano});
  final bool internamiento;
  final double tamano;

  @override
  Widget build(BuildContext context) => Container(
        width: tamano,
        height: tamano,
        decoration: BoxDecoration(
          color: internamiento ? Paleta.accion : Paleta.textoSecundario,
          borderRadius: BorderRadius.circular(tamano * 0.3),
          border: Border.all(color: Paleta.superficie, width: 2),
          boxShadow: const [BoxShadow(color: Color(0x33000000), blurRadius: 3, offset: Offset(0, 1))],
        ),
        child: Icon(Icons.local_hospital_rounded, color: Paleta.superficie, size: tamano * 0.62),
      );
}

/// Tú: un punto redondo oscuro con borde blanco y halo, distinto de las clínicas (cuadradas, con cruz).
class _PuntoYo extends StatelessWidget {
  const _PuntoYo({required this.tamano});
  final double tamano;

  @override
  Widget build(BuildContext context) => Container(
        width: tamano,
        height: tamano,
        decoration: BoxDecoration(
          color: Paleta.texto,
          shape: BoxShape.circle,
          border: Border.all(color: Paleta.superficie, width: 3),
          boxShadow: const [BoxShadow(color: Color(0x552E2620), blurRadius: 0, spreadRadius: 4)],
        ),
      );
}

class _Leyenda extends StatelessWidget {
  const _Leyenda(this.simbolo, this.texto);
  final Widget simbolo;
  final String texto;

  @override
  Widget build(BuildContext context) => Row(mainAxisSize: MainAxisSize.min, children: [
        ExcludeSemantics(child: simbolo),
        const SizedBox(width: 6),
        Text(texto, style: const TextStyle(color: Paleta.textoSecundario, fontSize: 14)),
      ]);
}

import 'package:file_picker/file_picker.dart';
import 'package:material_ui/material_ui.dart';
import 'package:speech_to_text/speech_to_text.dart';

import 'api.dart';
import 'comun.dart';
import 'estado.dart';
import 'resultado.dart';
import 'tema.dart';
import 'textos.dart';

const _tarapoto = 'chubb_viajes_jetsmart';

class PantallaPoliza extends StatefulWidget {
  const PantallaPoliza({super.key});

  @override
  State<PantallaPoliza> createState() => _PantallaPolizaState();
}

class _PantallaPolizaState extends State<PantallaPoliza> {
  final _pregunta = TextEditingController();
  final _voz = SpeechToText();
  bool _vozLista = false;
  bool _escuchando = false;
  bool _subiendo = false;
  bool _preguntando = false;
  Mapa? _resultado;
  String? _resultadoDe;
  List<TextEditingController> _aclaraciones = [];

  Estado get e => EstadoScope.of(context);

  @override
  void dispose() {
    _pregunta.dispose();
    for (final c in _aclaraciones) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> _subir() async {
    final archivos = await FilePicker.pickFiles(type: FileType.custom, allowedExtensions: ['pdf']);
    if (archivos.isEmpty || !mounted) return;
    setState(() => _subiendo = true);
    try {
      final pares = [for (final a in archivos) (a.name, await a.readAsBytes())];
      await e.subir(pares);
      _limpiarResultado();
    } catch (err) {
      if (mounted) mostrarError(context, err);
    } finally {
      if (mounted) setState(() => _subiendo = false);
    }
  }

  void _limpiarResultado() => setState(() {
        _resultado = null;
        _aclaraciones = [];
      });

  Future<void> _escuchar() async {
    if (_escuchando) {
      await _voz.stop();
      setState(() => _escuchando = false);
      return;
    }
    _vozLista = _vozLista || await _voz.initialize(onStatus: (s) {
      if (mounted && (s == 'done' || s == 'notListening')) setState(() => _escuchando = false);
    });
    if (!_vozLista) {
      if (mounted) mostrarError(context, ErrorApi('Tu teléfono no tiene el dictado por voz disponible. Escribe tu pregunta.'));
      return;
    }
    setState(() => _escuchando = true);
    await _voz.listen(
      onResult: (r) => setState(() => _pregunta.text = r.recognizedWords),
      listenOptions: SpeechListenOptions(partialResults: true, cancelOnError: true),
    );
  }

  Future<void> _preguntar({List<Map<String, String>>? aclaraciones}) async {
    final texto = (aclaraciones != null ? _resultado!['pregunta'] : _pregunta.text).toString().trim();
    if (e.poliza == null) return mostrarError(context, ErrorApi('Primero sube tu PDF o elige un ejemplo.'));
    if (texto.length < 3) return mostrarError(context, ErrorApi('Escribe tu pregunta.'));
    if (_escuchando) await _voz.stop();
    setState(() => _preguntando = true);
    try {
      final r = await e.conPoliza((id) => e.api.post('/preguntar', {'poliza_id': id, 'pregunta': texto, 'aclaraciones': aclaraciones ?? []}));
      setState(() {
        _resultado = Map<String, dynamic>.from(r as Map);
        _resultadoDe = e.poliza!.id;
        _aclaraciones = [for (final _ in (_resultado!['repreguntas'] as List? ?? [])) TextEditingController()];
      });
    } on ErrorApi catch (err) {
      if (mounted) {
        err.esTope ? _avisoTope(err) : mostrarError(context, err);
      }
    } finally {
      if (mounted) setState(() => _preguntando = false);
    }
  }

  void _avisoTope(ErrorApi err) => showDialog<void>(
        context: context,
        builder: (context) => AlertDialog(
          backgroundColor: Paleta.superficie,
          icon: const Icon(Icons.hourglass_empty_rounded, color: Paleta.parcial),
          title: const Text('Por ahora es todo'),
          content: Text(err.mensaje),
          actions: [
            if (err.mensaje.contains('Mi cuenta'))
              FilledButton(onPressed: () { Navigator.pop(context); e.irA(2); }, child: const Text('Ir a Mi cuenta')),
            TextButton(onPressed: () => Navigator.pop(context), child: const Text('Entendido')),
          ],
        ),
      );

  @override
  Widget build(BuildContext context) {
    final estado = e;
    final p = estado.poliza;
    final ancho = MediaQuery.sizeOf(context).width;
    final columnas = ancho > 900;
    final izquierda = <Widget>[
      _Encabezado(),
      const SizedBox(height: 16),
      _tarjetaPoliza(estado),
      const SizedBox(height: 16),
      _tarjetaPregunta(estado),
    ];
    final derecha = <Widget>[
      if (_preguntando) const Tarjeta(child: Cargando('Buscando en tu póliza y verificando cada cita…')),
      if (!_preguntando && _resultado != null && _resultadoDe == p?.id) ...[
        _tarjetaResultado(),
        if (_resultado!['modo'] != 'aclaracion') ...[const SizedBox(height: 16), _QueHacerAhora(situacion: '${_resultado!['pregunta']}',
            fecha: (_resultado!['fecha_hecho'] as Map?)?['fecha'] as String?)],
      ],
      if (p != null) ...[const SizedBox(height: 16), const _Radiografia()],
      if (!_preguntando && _resultado == null) ...[
        const SizedBox(height: 16),
        const _ComoFunciona(),
        const SizedBox(height: 16),
        _Ideas(alElegir: (q) => setState(() => _pregunta.text = q)),
      ],
    ];
    if (!columnas) {
      return SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Column(children: [...izquierda, const SizedBox(height: 16), ...derecha]),
        ),
      );
    }
    // En tableta, dos columnas que se desplazan por separado: la de la respuesta no deja la otra en blanco.
    return SafeArea(
      child: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 1400),
          child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(flex: 5, child: SingleChildScrollView(padding: const EdgeInsets.fromLTRB(32, 16, 12, 16), child: Column(children: izquierda))),
            Expanded(flex: 6, child: SingleChildScrollView(padding: const EdgeInsets.fromLTRB(12, 16, 32, 16), child: Column(children: derecha))),
          ]),
        ),
      ),
    );
  }

  Widget _tarjetaPoliza(Estado estado) {
    final p = estado.poliza;
    return Tarjeta(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Titulo('Tu póliza', icono: Icons.description_rounded),
        const SizedBox(height: 14),
        if (_subiendo)
          const Cargando('Leyendo tu póliza. Un documento largo puede tardar medio minuto…')
        else if (p != null)
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: Paleta.fondo, borderRadius: BorderRadius.circular(14), border: Border.all(color: Paleta.accion)),
            child: Row(children: [
              ExcludeSemantics(child: Icon(p.esEjemplo ? Icons.menu_book_rounded : Icons.picture_as_pdf_rounded, color: Paleta.accion, size: 30)),
              const SizedBox(width: 12),
              Expanded(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(p.nombre, style: const TextStyle(fontWeight: FontWeight.w700)),
                  const SizedBox(height: 4),
                  Wrap(spacing: 8, runSpacing: 6, children: [
                    Text(p.esEjemplo ? 'Condicionado de ejemplo' : p.tipo == 'guardada' ? 'Guardada en tu cuenta' : 'Lista para preguntar',
                        style: const TextStyle(color: Paleta.textoSecundario, fontSize: 13.5)),
                    if (p.borradoAutomatico != null) InsigniaBorrado(p.borradoAutomatico!),
                  ]),
                ]),
              ),
              IconButton(tooltip: 'Quitar esta póliza', icon: const Icon(Icons.close), onPressed: () {
                estado.elegir(null);
                _limpiarResultado();
              }),
            ]),
          ),
        if (p?.tipo == 'subida' && estado.conCuenta) ...[const SizedBox(height: 10), _GuardarEnCuenta(alGuardar: (g) => estado.elegir(g))],
        if (p == null && !_subiendo) ...[
          FilledButton.icon(
            onPressed: _subir,
            icon: const Icon(Icons.upload_file_rounded),
            label: const Text('Subir el PDF de mi póliza'),
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
          ),
          const SizedBox(height: 8),
          const Text('Si viene en varios archivos, elígelos juntos. Necesita texto seleccionable.',
              style: TextStyle(color: Paleta.textoSecundario, fontSize: 13.5)),
          if (estado.guardadas.isNotEmpty) ...[
            const SizedBox(height: 16),
            const Text('Tus pólizas guardadas', style: TextStyle(fontWeight: FontWeight.w700)),
            const SizedBox(height: 8),
            for (final g in estado.guardadas)
              _OpcionPoliza(
                icono: Icons.bookmark_rounded,
                titulo: '${g['nombre']}',
                fecha: g['borrado_automatico'] as String?,
                alTocar: () {
                  estado.elegir(PolizaActual(id: '${g['poliza_id']}', nombre: '${g['nombre']}', tipo: 'guardada',
                      documento: g['sha256'] as String?, paginas: g['paginas'] as int?, borradoAutomatico: g['borrado_automatico'] as String?,
                      archivos: List<Map<String, dynamic>>.from(g['archivos'] ?? const [])));
                  _limpiarResultado();
                },
              ),
          ],
          const SizedBox(height: 16),
          const Text('¿No tienes una a mano? Prueba con un ejemplo', style: TextStyle(fontWeight: FontWeight.w700)),
          const SizedBox(height: 8),
          for (final f in estado.ejemplos)
            _OpcionPoliza(
              icono: Icons.menu_book_rounded,
              titulo: '${f['aseguradora']}',
              subtitulo: '${f['producto']}',
              alTocar: () {
                estado.elegir(PolizaActual(id: '${f['poliza_id']}', nombre: '${f['aseguradora']} · ${f['producto']}', tipo: 'ejemplo',
                    documento: '${f['poliza_id']}'));
                _limpiarResultado();
              },
            ),
        ],
      ]),
    );
  }

  Widget _tarjetaPregunta(Estado estado) {
    final ejemplos = estado.poliza?.id == _tarapoto
        ? [for (final f in estado.ejemplos.where((f) => f['poliza_id'] == _tarapoto)) ...(f['ejemplos'] as List).cast<String>()]
            .where((q) => q.contains('Tarapoto') || q.contains('al llegar a Lima'))
            .toList()
        : <String>[];
    return Tarjeta(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Titulo('Tu pregunta', icono: Icons.forum_rounded),
        const SizedBox(height: 14),
        TextField(
          controller: _pregunta,
          minLines: 3,
          maxLines: 6,
          textCapitalization: TextCapitalization.sentences,
          decoration: InputDecoration(
            labelText: 'Escribe o dicta tu pregunta',
            floatingLabelBehavior: FloatingLabelBehavior.never,
            hintText: 'Por ejemplo: me robaron la maleta en el aeropuerto, ¿me cubre?',
            suffixIcon: Padding(
              padding: const EdgeInsets.only(right: 4),
              child: IconButton(
                tooltip: _escuchando ? 'Dejar de escuchar' : 'Preguntar hablando',
                icon: Icon(_escuchando ? Icons.stop_circle_rounded : Icons.mic_rounded, color: Paleta.accion, size: 30),
                onPressed: _escuchar,
              ),
            ),
          ),
        ),
        if (_escuchando)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Semantics(liveRegion: true, child: const Text('Escuchando… cuando termines, revisa el texto y toca Preguntar.',
                style: TextStyle(color: Paleta.accion))),
          ),
        const SizedBox(height: 8),
        const Text('Puedes hacer varias preguntas en el mismo texto.', style: TextStyle(color: Paleta.textoSecundario, fontSize: 13.5)),
        const SizedBox(height: 14),
        FilledButton.icon(
          onPressed: _preguntando ? null : () => _preguntar(),
          icon: const Icon(Icons.search_rounded),
          label: const Text('Preguntar'),
          style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(54)),
        ),
        if (ejemplos.isNotEmpty) ...[
          const SizedBox(height: 14),
          const Text('Prueba con un ejemplo:', style: TextStyle(color: Paleta.textoSecundario)),
          for (final q in ejemplos)
            TextButton(
              style: TextButton.styleFrom(alignment: Alignment.centerLeft, padding: const EdgeInsets.symmetric(vertical: 8)),
              onPressed: () {
                _pregunta.text = q;
                _preguntar();
              },
              child: Text(q, style: const TextStyle(decoration: TextDecoration.underline, decorationColor: Paleta.accion)),
            ),
        ],
      ]),
    );
  }

  Widget _tarjetaResultado() {
    final r = _resultado!;
    final archivos = e.poliza?.archivos ?? const [];
    final cuerpo = <Widget>[Text('Pregunta: ${r['pregunta']}', style: const TextStyle(color: Paleta.textoSecundario)), const SizedBox(height: 14)];
    if (r['modo'] == 'aclaracion') {
      cuerpo.addAll([
        Aviso('${r['aviso']}', icono: Icons.chat_bubble_outline),
        const SizedBox(height: 12),
        for (final (i, q) in (r['repreguntas'] as List).cast<String>().indexed)
          Padding(padding: const EdgeInsets.only(bottom: 10), child: TextField(controller: _aclaraciones[i], decoration: InputDecoration(labelText: q))),
        FilledButton(
          onPressed: () {
            final datos = [
              for (final (i, q) in (r['repreguntas'] as List).cast<String>().indexed)
                {'pregunta': q, 'respuesta': _aclaraciones[i].text.trim()}
            ];
            if (datos.every((a) => a['respuesta']!.isEmpty)) return mostrarError(context, ErrorApi('Responde al menos una de las preguntas.'));
            _preguntar(aclaraciones: datos);
          },
          child: const Text('Responder'),
        ),
      ]);
    } else if (r['modo'] == 'varias') {
      cuerpo.addAll([
        Aviso('${r['aviso']}', icono: Icons.dashboard_customize_outlined),
        for (final (i, sub) in (r['respuestas'] as List).indexed) ...[
          const SizedBox(height: 22),
          Semantics(header: true, child: Text('Pregunta ${i + 1}: ${sub['pregunta']}', style: Theme.of(context).textTheme.titleMedium)),
          const SizedBox(height: 10),
          VistaRespuesta(Map<String, dynamic>.from(sub as Map), archivos),
        ],
        for (final q in (r['sin_responder'] as List? ?? []))
          Padding(padding: const EdgeInsets.only(top: 12), child: Aviso('No respondí «$q»: alcanzaste el límite de consultas de tu plan.')),
      ]);
    } else {
      cuerpo.add(VistaRespuesta(r, archivos));
    }
    return Tarjeta(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: cuerpo));
  }
}

class _Encabezado extends StatelessWidget {
  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(22),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(24),
          gradient: const LinearGradient(colors: [Color(0xFF16304A), Paleta.superficie], begin: Alignment.topLeft, end: Alignment.bottomRight),
          border: Border.all(color: Paleta.borde),
        ),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Row(children: [
            ClipRRect(
              borderRadius: BorderRadius.circular(16),
              child: Image.asset('assets/icono_512.png', width: 64, height: 64, semanticLabel: 'Logo de ¿Qué Cubre?'),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Semantics(header: true, child: Text(Textos.nombre, style: Theme.of(context).textTheme.headlineMedium)),
                const Text('Pregunta en tus palabras. Te respondo con la cláusula exacta y su página.',
                    style: TextStyle(color: Paleta.textoSecundario, fontSize: 15)),
              ]),
            ),
          ]),
          const SizedBox(height: 18),
          Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: Paleta.fondo, borderRadius: BorderRadius.circular(14), border: Border.all(color: Paleta.parcial)),
            child: const Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              ExcludeSemantics(child: Icon(Icons.gavel_rounded, color: Paleta.parcial)),
              SizedBox(width: 10),
              Expanded(child: Text(Textos.descargoInicio, style: TextStyle(fontSize: 15, height: 1.45))),
            ]),
          ),
        ]),
      );
}

class _ComoFunciona extends StatelessWidget {
  const _ComoFunciona();

  @override
  Widget build(BuildContext context) => Tarjeta(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Titulo('Cómo funciona', icono: Icons.auto_awesome_rounded),
          const SizedBox(height: 14),
          for (final (i, icono, texto) in [
            (1, Icons.upload_file_rounded, 'Sube el PDF de tu póliza o elige un ejemplo.'),
            (2, Icons.record_voice_over_rounded, 'Pregunta escribiendo o hablando, en tus palabras.'),
            (3, Icons.format_quote_rounded, 'Te respondo con la cláusula exacta, su artículo y su página, verificada en tu PDF.'),
            (4, Icons.local_hospital_rounded, 'Encuentra clínicas y hospitales cerca de ti en «Cerca de ti».'),
          ])
            Padding(
              padding: const EdgeInsets.only(bottom: 14),
              child: Row(children: [
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(color: Paleta.fondo, borderRadius: BorderRadius.circular(14), border: Border.all(color: Paleta.accion)),
                  child: ExcludeSemantics(child: Icon(icono, color: Paleta.accion)),
                ),
                const SizedBox(width: 14),
                Expanded(child: Text('$i. $texto', style: const TextStyle(fontSize: 15.5))),
              ]),
            ),
        ]),
      );
}

/// Ideas de preguntas, para quien no sabe por dónde empezar. Tocar una la pone en el campo.
class _Ideas extends StatelessWidget {
  const _Ideas({required this.alElegir});
  final ValueChanged<String> alElegir;

  static const _ideas = [
    (Icons.luggage_rounded, 'Se perdió mi maleta en el vuelo, ¿me cubre?'),
    (Icons.healing_rounded, 'Me caí y fui a emergencias, ¿me cubre la atención?'),
    (Icons.flight_takeoff_rounded, 'Cancelaron mi vuelo, ¿me devuelven algo?'),
    (Icons.medication_rounded, '¿Cubre las medicinas que me recetaron?'),
    (Icons.event_busy_rounded, '¿Cuánto tiempo tengo para avisar a la aseguradora?'),
  ];

  @override
  Widget build(BuildContext context) => Tarjeta(
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const Titulo('Ideas para preguntar', icono: Icons.lightbulb_rounded),
          const SizedBox(height: 12),
          Wrap(spacing: 10, runSpacing: 10, children: [
            for (final (icono, texto) in _ideas)
              ActionChip(
                avatar: Icon(icono, size: 18, color: Paleta.accion),
                label: Text(texto),
                onPressed: () => alElegir(texto),
                tooltip: 'Usar esta pregunta',
              ),
          ]),
          const SizedBox(height: 16),
          const Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            ExcludeSemantics(child: Icon(Icons.lock_rounded, color: Paleta.textoSecundario, size: 20)),
            SizedBox(width: 10),
            Expanded(child: Text(Textos.privacidadCorta, style: TextStyle(color: Paleta.textoSecundario, fontSize: 14))),
          ]),
        ]),
      );
}

class _OpcionPoliza extends StatelessWidget {
  const _OpcionPoliza({required this.icono, required this.titulo, this.subtitulo, this.fecha, required this.alTocar});
  final IconData icono;
  final String titulo;
  final String? subtitulo;
  final String? fecha;
  final VoidCallback alTocar;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 8),
        child: Material(
          color: Paleta.fondo,
          borderRadius: BorderRadius.circular(14),
          child: InkWell(
            borderRadius: BorderRadius.circular(14),
            onTap: alTocar,
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), border: Border.all(color: Paleta.borde)),
              child: Row(children: [
                ExcludeSemantics(child: Icon(icono, color: Paleta.accion)),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(titulo, style: const TextStyle(fontWeight: FontWeight.w600)),
                    if (subtitulo != null) Text(subtitulo!, style: const TextStyle(color: Paleta.textoSecundario, fontSize: 13.5)),
                    if (fecha != null) Padding(padding: const EdgeInsets.only(top: 4), child: InsigniaBorrado(fecha!)),
                  ]),
                ),
                const ExcludeSemantics(child: Icon(Icons.chevron_right, color: Paleta.textoSecundario)),
              ]),
            ),
          ),
        ),
      );
}

class _GuardarEnCuenta extends StatefulWidget {
  const _GuardarEnCuenta({required this.alGuardar});
  final void Function(PolizaActual) alGuardar;

  @override
  State<_GuardarEnCuenta> createState() => _GuardarEnCuentaState();
}

class _GuardarEnCuentaState extends State<_GuardarEnCuenta> {
  bool _guardando = false;

  @override
  Widget build(BuildContext context) {
    final e = EstadoScope.of(context);
    final dias = e.cuenta?['dias_de_guardado'] as int?;
    final cuando = dias == null ? null : DateTime.now().add(Duration(days: dias));
    final fecha = cuando == null ? null : '${cuando.day.toString().padLeft(2, '0')}/${cuando.month.toString().padLeft(2, '0')}/${cuando.year}';
    return Wrap(crossAxisAlignment: WrapCrossAlignment.center, spacing: 12, runSpacing: 8, children: [
      OutlinedButton.icon(
        onPressed: _guardando
            ? null
            : () async {
                setState(() => _guardando = true);
                final p = e.poliza!;
                try {
                  final borrado = await e.guardarEnCuenta();
                  final g = e.guardadas.first;
                  widget.alGuardar(PolizaActual(id: '${g['poliza_id']}', nombre: p.nombre, tipo: 'guardada', documento: p.documento,
                      paginas: p.paginas, borradoAutomatico: borrado, archivos: p.archivos));
                  if (context.mounted) {
                    ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(borrado == null ? 'Guardada' : 'Guardada · se borra el $borrado')));
                  }
                } catch (err) {
                  if (context.mounted) mostrarError(context, err);
                } finally {
                  if (mounted) setState(() => _guardando = false);
                }
              },
        icon: const Icon(Icons.bookmark_add_outlined),
        label: const Text('Guardar en mi cuenta'),
      ),
      if (fecha != null) InsigniaBorrado(fecha),
    ]);
  }
}

class _QueHacerAhora extends StatefulWidget {
  const _QueHacerAhora({required this.situacion, this.fecha});
  final String situacion;
  final String? fecha;

  @override
  State<_QueHacerAhora> createState() => _QueHacerAhoraState();
}

class _QueHacerAhoraState extends State<_QueHacerAhora> {
  DateTime? _fecha;
  bool _cargando = false;
  Mapa? _pasos;

  @override
  void initState() {
    super.initState();
    _fecha = widget.fecha == null ? null : DateTime.tryParse(widget.fecha!);
  }

  String _texto(DateTime d) => '${d.day.toString().padLeft(2, '0')}/${d.month.toString().padLeft(2, '0')}/${d.year}';

  @override
  Widget build(BuildContext context) {
    final e = EstadoScope.of(context);
    return Tarjeta(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Titulo('Qué hacer ahora: pasos y fecha límite', icono: Icons.event_available_rounded),
        const SizedBox(height: 12),
        Wrap(spacing: 12, runSpacing: 10, crossAxisAlignment: WrapCrossAlignment.center, children: [
          OutlinedButton.icon(
            onPressed: () async {
              final hoy = DateTime.now();
              final elegida = await showDatePicker(context: context, initialDate: _fecha ?? hoy, firstDate: DateTime(hoy.year - 2), lastDate: hoy,
                  helpText: '¿Cuándo ocurrió?');
              if (elegida != null) setState(() => _fecha = elegida);
            },
            icon: const Icon(Icons.calendar_month),
            label: Text(_fecha == null ? '¿Cuándo ocurrió?' : 'Ocurrió el ${_texto(_fecha!)}'),
          ),
          FilledButton(
            onPressed: _cargando
                ? null
                : () async {
                    setState(() => _cargando = true);
                    try {
                      final f = _fecha;
                      final r = await e.conPoliza((id) => e.api.post('/pasos', {
                            'poliza_id': id,
                            'situacion': widget.situacion,
                            'fecha_hecho': f == null ? null : '${f.year}-${f.month.toString().padLeft(2, '0')}-${f.day.toString().padLeft(2, '0')}',
                          }));
                      setState(() => _pasos = Map<String, dynamic>.from(r as Map));
                    } catch (err) {
                      if (context.mounted) mostrarError(context, err);
                    } finally {
                      if (mounted) setState(() => _cargando = false);
                    }
                  },
            child: const Text('Ver los pasos'),
          ),
        ]),
        if (_cargando) const Cargando('Buscando en tu póliza cómo se reclama…'),
        if (_pasos != null) ...[const SizedBox(height: 16), VistaPasos(_pasos!, e.poliza?.archivos ?? const [])],
      ]),
    );
  }
}

class _Radiografia extends StatefulWidget {
  const _Radiografia();

  @override
  State<_Radiografia> createState() => _RadiografiaState();
}

class _RadiografiaState extends State<_Radiografia> {
  bool _cargando = false;
  Mapa? _r;
  String? _de;
  String? _bloqueo;

  /// Lo que la cuenta trae del backend: si la radiografía de este documento ya es suya, si le
  /// queda la gratis o si es premium. El backend decide igual al pedirla.
  String _acceso(Estado e) {
    final c = e.cuenta;
    if (c == null) return 'sin_cuenta';
    final f = Map<String, dynamic>.from(c['funciones'] as Map);
    final doc = e.poliza?.documento;
    if (doc != null && (doc == f['radiografia_gratis_de'] || (f['radiografias_pagadas'] as List? ?? []).contains(doc))) return 'abierta';
    if (e.premium) return 'abierta';
    return f['radiografia_gratis_de'] == null ? 'gratis' : 'bloqueada';
  }

  @override
  Widget build(BuildContext context) {
    final e = EstadoScope.of(context);
    final p = e.poliza!;
    if (_de != p.id) {
      _r = null;
      _bloqueo = null;
    }
    final acceso = _bloqueo ?? _acceso(e);
    return Tarjeta(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Titulo('Radiografía de tu póliza', icono: Icons.document_scanner_rounded),
        const SizedBox(height: 6),
        const Text('Qué cubre y hasta cuánto, exclusiones, deducibles y carencias.', style: TextStyle(color: Paleta.textoSecundario)),
        const SizedBox(height: 14),
        if (_r != null)
          VistaRadiografia(_r!, p.archivos)
        else if (_cargando)
          const Cargando('Leyendo tu póliza: la primera vez tarda unos segundos…')
        else if (acceso == 'sin_cuenta')
          Bloqueada(texto: 'Crea una cuenta gratis para ver una radiografía', alTocar: () => e.irA(2))
        else if (acceso == 'bloqueada')
          Bloqueada(texto: '${Textos.botonPremium} para ver la radiografía de todas tus pólizas', alTocar: () => e.irA(2))
        else
          FilledButton.icon(
            onPressed: () async {
              setState(() {
                _cargando = true;
                _de = p.id;
              });
              try {
                final r = await e.conPoliza((id) => e.api.get('/polizas/$id/radiografia'));
                setState(() => _r = Map<String, dynamic>.from(r as Map));
                await e.refrescarCuenta();
              } on ErrorApi catch (err) {
                if (err.status == 403) {
                  setState(() => _bloqueo = 'bloqueada');
                } else if (context.mounted) {
                  mostrarError(context, err);
                }
              } finally {
                if (mounted) setState(() => _cargando = false);
              }
            },
            icon: const Icon(Icons.visibility_rounded),
            label: Text(acceso == 'gratis' ? 'Ver la radiografía · la primera es gratis' : 'Ver la radiografía'),
          ),
      ]),
    );
  }
}

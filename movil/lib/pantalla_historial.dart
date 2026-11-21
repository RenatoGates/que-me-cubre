import 'package:material_ui/material_ui.dart';

import 'comun.dart';
import 'estado.dart';
import 'resultado.dart';
import 'tema.dart';

/// El historial: las respuestas de esta sesión y, con cuenta, las de cada póliza guardada.
/// Volver a leer una respuesta no cuesta una consulta: se muestra lo que ya llegó.
class PantallaHistorial extends StatelessWidget {
  const PantallaHistorial({super.key});

  @override
  Widget build(BuildContext context) {
    final e = EstadoScope.of(context);
    return SafeArea(
      child: SingleChildScrollView(
        padding: const EdgeInsets.all(16),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Semantics(header: true, child: Text('Historial', style: Theme.of(context).textTheme.headlineMedium)),
              const SizedBox(height: 4),
              const Text('Vuelve a leer una respuesta completa, con sus citas. No cuenta como consulta.',
                  style: TextStyle(color: Paleta.textoSecundario)),
              const SizedBox(height: 16),
              Tarjeta(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  const Titulo('En esta sesión', icono: Icons.schedule_rounded),
                  const SizedBox(height: 8),
                  if (e.sesion.isEmpty)
                    const Text('Todavía no preguntaste nada. Tus respuestas aparecen aquí.', style: TextStyle(color: Paleta.textoSecundario)),
                  for (final h in e.sesion)
                    FilaRespuesta(h.respuesta, detalle: '${h.poliza.nombre} · ${_hora(h.hora)}',
                        alTocar: () => abrirRespuesta(context, h.respuesta, h.poliza)),
                  if (e.sesion.isNotEmpty && !e.conCuenta)
                    const Padding(
                      padding: EdgeInsets.only(top: 8),
                      child: Text('Al cerrar la app se borra. Con una cuenta, las respuestas de tus pólizas guardadas se conservan.',
                          style: TextStyle(color: Paleta.textoSecundario, fontSize: 14)),
                    ),
                ]),
              ),
              if (e.conCuenta && e.guardadas.isNotEmpty) ...[
                const SizedBox(height: 16),
                Tarjeta(
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    const Titulo('De tus pólizas guardadas', icono: Icons.bookmarks_rounded),
                    const SizedBox(height: 8),
                    for (final g in e.guardadas) _HistorialGuardada(g, key: ValueKey(g['poliza_id'])),
                  ]),
                ),
              ],
            ]),
          ),
        ),
      ),
    );
  }

  static String _hora(DateTime t) => '${t.hour.toString().padLeft(2, '0')}:${t.minute.toString().padLeft(2, '0')}';
}

class _HistorialGuardada extends StatefulWidget {
  const _HistorialGuardada(this.g, {super.key});
  final Mapa g;

  @override
  State<_HistorialGuardada> createState() => _HistorialGuardadaState();
}

class _HistorialGuardadaState extends State<_HistorialGuardada> {
  List<Mapa>? _consultas;
  Object? _error;

  Future<void> _cargar() async {
    try {
      final r = await EstadoScope.of(context).api.get('/polizas/${widget.g['poliza_id']}/consultas');
      if (mounted) setState(() => _consultas = lista(r['consultas']));
    } catch (err) {
      if (mounted) setState(() => _error = err);
    }
  }

  @override
  Widget build(BuildContext context) {
    final poliza = polizaGuardada(widget.g);
    return Theme(
      data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
      child: ExpansionTile(
        tilePadding: EdgeInsets.zero,
        iconColor: Paleta.accion,
        collapsedIconColor: Paleta.accion,
        onExpansionChanged: (abierto) => abierto && _consultas == null ? _cargar() : null,
        title: Text('${widget.g['nombre']}', style: const TextStyle(fontWeight: FontWeight.w700)),
        expandedCrossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (_error != null)
            const Text('No pude traer tus consultas. Revisa tu conexión.', style: TextStyle(color: Paleta.textoSecundario))
          else if (_consultas == null)
            const Cargando('Cargando tus consultas…')
          else if (_consultas!.isEmpty)
            const Text('Sin consultas todavía.', style: TextStyle(color: Paleta.textoSecundario))
          else
            for (final c in _consultas!)
              FilaRespuesta(c, detalle: _fecha('${c['creado'] ?? ''}'), alTocar: () => abrirRespuesta(context, c, poliza)),
        ],
      ),
    );
  }

  static String _fecha(String iso) {
    if (iso.length < 10) return '';
    final p = iso.substring(0, 10).split('-');
    return '${p[2]}/${p[1]}/${p[0]}';
  }
}

/// Una fila del historial: la pregunta y su veredicto (o veredictos, si eran varias preguntas).
class FilaRespuesta extends StatelessWidget {
  const FilaRespuesta(this.r, {super.key, required this.alTocar, this.detalle});
  final Mapa r;
  final VoidCallback alTocar;
  final String? detalle;

  @override
  Widget build(BuildContext context) {
    final partes = r['modo'] == 'varias' ? lista(r['respuestas']) : [r];
    return InkWell(
      onTap: alTocar,
      borderRadius: BorderRadius.circular(12),
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 10),
        child: Row(children: [
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${r['pregunta'] ?? ''}', maxLines: 2, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w600)),
              const SizedBox(height: 4),
              Wrap(spacing: 12, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
                for (final s in partes)
                  Row(mainAxisSize: MainAxisSize.min, children: [
                    ExcludeSemantics(child: Icon(Veredicto.de(s['cubre'] as String?).icono, size: 18, color: Veredicto.de(s['cubre'] as String?).color)),
                    const SizedBox(width: 4),
                    Text('${s['etiqueta_veredicto'] ?? 'Sin veredicto'}',
                        style: TextStyle(color: Veredicto.de(s['cubre'] as String?).color, fontWeight: FontWeight.w700)),
                  ]),
                if (detalle != null && detalle!.isNotEmpty) Text(detalle!, style: const TextStyle(color: Paleta.textoSecundario, fontSize: 14)),
              ]),
            ]),
          ),
          const ExcludeSemantics(child: Icon(Icons.chevron_right, color: Paleta.accion)),
        ]),
      ),
    );
  }
}

/// Abre una respuesta ya recibida, completa y con el detalle desplegado.
Future<void> abrirRespuesta(BuildContext context, Mapa r, PolizaActual? poliza) => Navigator.of(context).push(
      MaterialPageRoute<void>(builder: (_) => _PantallaRespuesta(r: r, poliza: poliza)),
    );

class _PantallaRespuesta extends StatelessWidget {
  const _PantallaRespuesta({required this.r, required this.poliza});
  final Mapa r;
  final PolizaActual? poliza;

  @override
  Widget build(BuildContext context) {
    final partes = r['modo'] == 'varias' ? lista(r['respuestas']) : [r];
    return Scaffold(
      appBar: AppBar(title: const Text('Tu respuesta')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(16),
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 760),
              child: Tarjeta(
                child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text('Pregunta: ${r['pregunta'] ?? ''}', style: const TextStyle(color: Paleta.textoSecundario)),
                  if (poliza != null) Text('Póliza: ${poliza!.nombre}', style: const TextStyle(color: Paleta.textoSecundario)),
                  const SizedBox(height: 14),
                  for (final (i, s) in partes.indexed) ...[
                    if (i > 0) const Padding(padding: EdgeInsets.symmetric(vertical: 16), child: Divider()),
                    if (partes.length > 1) ...[
                      Text('${s['pregunta'] ?? ''}', style: const TextStyle(fontWeight: FontWeight.w700)),
                      const SizedBox(height: 8),
                    ],
                    VistaRespuesta(s, poliza, detalleAbierto: true),
                  ],
                ]),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

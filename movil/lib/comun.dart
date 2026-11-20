import 'package:material_ui/material_ui.dart';

import 'api.dart';
import 'estado.dart';
import 'tema.dart';
import 'textos.dart';

class EstadoScope extends InheritedNotifier<Estado> {
  const EstadoScope({super.key, required Estado estado, required super.child}) : super(notifier: estado);

  static Estado of(BuildContext context) => context.dependOnInheritedWidgetOfExactType<EstadoScope>()!.notifier!;
}

class Tarjeta extends StatelessWidget {
  const Tarjeta({super.key, required this.child, this.padding = const EdgeInsets.all(20), this.color, this.borde});
  final Widget child;
  final EdgeInsets padding;
  final Color? color;
  final Color? borde;

  @override
  Widget build(BuildContext context) => Card(
        semanticContainer: false, // cada texto se recorre por separado con TalkBack
        color: color,
        shape: borde == null
            ? null
            : RoundedRectangleBorder(borderRadius: BorderRadius.circular(20), side: BorderSide(color: borde!, width: 1.4)),
        child: Padding(padding: padding, child: child),
      );
}

class Titulo extends StatelessWidget {
  const Titulo(this.texto, {super.key, this.icono});
  final String texto;
  final IconData? icono;

  @override
  Widget build(BuildContext context) => Semantics(
        header: true,
        child: Row(children: [
          if (icono != null) ...[ExcludeSemantics(child: Icon(icono, color: Paleta.accion, size: 22)), const SizedBox(width: 10)],
          Expanded(child: Text(texto, style: Theme.of(context).textTheme.titleMedium)),
        ]),
      );
}

/// El veredicto: color, ícono y texto. Nunca solo color.
class Veredicto {
  const Veredicto(this.color, this.icono);
  final Color color;
  final IconData icono;

  static Veredicto de(String? cubre) => switch (cubre) {
        'si' => const Veredicto(Paleta.cubierto, Icons.check_circle),
        'con_limites' => const Veredicto(Paleta.parcial, Icons.rule),
        'no' => const Veredicto(Paleta.noCubierto, Icons.cancel),
        _ => const Veredicto(Paleta.textoSecundario, Icons.help_outline),
      };
}

class InsigniaVeredicto extends StatelessWidget {
  const InsigniaVeredicto({super.key, required this.cubre, required this.etiqueta});
  final String? cubre;
  final String etiqueta;

  @override
  Widget build(BuildContext context) {
    final v = Veredicto.de(cubre);
    return Semantics(
      label: 'Veredicto: $etiqueta',
      excludeSemantics: true,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        decoration: BoxDecoration(
          color: Paleta.fondo,
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: v.color, width: 2),
        ),
        child: Row(mainAxisSize: MainAxisSize.min, children: [
          Icon(v.icono, color: v.color, size: 28),
          const SizedBox(width: 10),
          Flexible(child: Text(etiqueta, style: TextStyle(color: v.color, fontSize: 21, fontWeight: FontWeight.w800))),
        ]),
      ),
    );
  }
}

/// Junto a cada respuesta, visible y en letra normal.
class DescargoRespuesta extends StatelessWidget {
  const DescargoRespuesta({super.key});

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          color: Paleta.fondo,
          borderRadius: BorderRadius.circular(14),
          border: const Border(left: BorderSide(color: Paleta.parcial, width: 4)),
        ),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          const ExcludeSemantics(child: Icon(Icons.gavel_rounded, color: Paleta.parcial, size: 22)),
          const SizedBox(width: 10),
          Expanded(child: Text(Textos.descargoRespuesta, style: Theme.of(context).textTheme.bodyMedium)),
        ]),
      );
}

class InsigniaBorrado extends StatelessWidget {
  const InsigniaBorrado(this.fecha, {super.key});
  final String fecha;

  @override
  Widget build(BuildContext context) => Semantics(
        label: 'Se borra el $fecha',
        excludeSemantics: true,
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(color: Paleta.fondo, borderRadius: BorderRadius.circular(99), border: Border.all(color: Paleta.parcial)),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.schedule, size: 14, color: Paleta.parcial),
            const SizedBox(width: 4),
            Text('se borra el $fecha', style: const TextStyle(color: Paleta.parcial, fontSize: 13, fontWeight: FontWeight.w600)),
          ]),
        ),
      );
}

/// Una función premium bloqueada: se muestra, no se oculta.
class Bloqueada extends StatelessWidget {
  const Bloqueada({super.key, required this.texto, this.alTocar});
  final String texto;
  final VoidCallback? alTocar;

  @override
  Widget build(BuildContext context) => Semantics(
        button: alTocar != null,
        label: 'Función premium bloqueada. $texto',
        excludeSemantics: true,
        child: InkWell(
          onTap: alTocar,
          borderRadius: BorderRadius.circular(14),
          child: Container(
            padding: const EdgeInsets.all(14),
            decoration: BoxDecoration(color: Paleta.fondo, borderRadius: BorderRadius.circular(14), border: Border.all(color: Paleta.borde)),
            child: Row(children: [
              const Icon(Icons.lock_rounded, color: Paleta.accion),
              const SizedBox(width: 12),
              Expanded(child: Text(texto, style: const TextStyle(color: Paleta.texto, fontWeight: FontWeight.w600))),
              if (alTocar != null) const Icon(Icons.chevron_right, color: Paleta.accion),
            ]),
          ),
        ),
      );
}

class Cargando extends StatelessWidget {
  const Cargando(this.texto, {super.key});
  final String texto;

  @override
  Widget build(BuildContext context) => Semantics(
        liveRegion: true,
        label: texto,
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 18),
          child: Row(children: [
            const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 3, color: Paleta.accion)),
            const SizedBox(width: 14),
            Expanded(child: Text(texto, style: const TextStyle(color: Paleta.textoSecundario))),
          ]),
        ),
      );
}

class Aviso extends StatelessWidget {
  const Aviso(this.texto, {super.key, this.icono = Icons.info_outline, this.color = Paleta.accion});
  final String texto;
  final IconData icono;
  final Color color;

  @override
  Widget build(BuildContext context) => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(color: Paleta.fondo, borderRadius: BorderRadius.circular(14), border: Border.all(color: color)),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          ExcludeSemantics(child: Icon(icono, color: color)),
          const SizedBox(width: 10),
          Expanded(child: Text(texto)),
        ]),
      );
}

void mostrarError(BuildContext context, Object e) {
  final texto = e is ErrorApi ? e.mensaje : 'Algo falló. Vuelve a intentar.';
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(texto)));
}

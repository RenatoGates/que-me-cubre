import 'package:flutter/services.dart';
import 'package:material_ui/material_ui.dart';

import 'comun.dart';
import 'tema.dart';

typedef Mapa = Map<String, dynamic>;

List<Mapa> _lista(dynamic v) => v == null ? [] : List<Mapa>.from((v as List).map((x) => Map<String, dynamic>.from(x as Map)));

/// Página de corrido → (archivo, página en ese archivo), si la póliza vino en varios PDF.
String donde(Mapa c, List<Mapa> archivos) {
  final paginas = (c['paginas'] as List?)?.cast<int>() ?? [c['pagina'] as int];
  String una(int pagina) {
    if (archivos.length < 2) return 'pág. $pagina';
    var desde = 0;
    for (final a in archivos) {
      final n = a['paginas'] as int;
      if (pagina <= desde + n) return '${a['nombre']}, pág. ${pagina - desde}';
      desde += n;
    }
    return 'pág. $pagina';
  }

  return paginas.length == 1 || paginas.first == paginas.last ? una(paginas.first) : '${una(paginas.first)} a ${una(paginas.last)}';
}

String refs(List? numeros) {
  final n = (numeros ?? const []).cast<int>();
  if (n.isEmpty) return '';
  return n.length == 1 ? ' (cita ${n.first})' : ' (citas ${n.join(', ')})';
}

class Lista extends StatelessWidget {
  const Lista(this.titulo, this.items, {super.key, this.icono = Icons.circle, this.color = Paleta.textoSecundario});
  final String titulo;
  final List<String> items;
  final IconData icono;
  final Color color;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 18),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Semantics(header: true, child: Text(titulo, style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700))),
        const SizedBox(height: 8),
        for (final i in items)
          Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Padding(padding: const EdgeInsets.only(top: 7), child: ExcludeSemantics(child: Icon(icono, size: 8, color: color))),
              const SizedBox(width: 10),
              Expanded(child: Text(i)),
            ]),
          ),
      ]),
    );
  }
}

/// Una cita verificada, con el botón para ubicarla en el propio PDF.
class TarjetaCita extends StatelessWidget {
  const TarjetaCita(this.c, this.archivos, {super.key});
  final Mapa c;
  final List<Mapa> archivos;

  void _ubicar(BuildContext context) {
    final texto = '${c['texto_literal']}';
    final inicio = texto.length > 90 ? '${texto.substring(0, 90)}…' : texto;
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: Paleta.superficie,
      showDragHandle: true,
      builder: (context) => SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 0, 24, 24),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Cómo encontrarla en tu PDF', style: Theme.of(context).textTheme.titleLarge),
            const SizedBox(height: 16),
            _Paso(Icons.description_outlined, 'Abre tu póliza en ${donde(c, archivos)}.'),
            _Paso(Icons.bookmark_border, 'Busca «${c['articulo']}», en la sección «${c['seccion']}».'),
            _Paso(Icons.format_quote, 'El texto empieza así: «$inicio»'),
            const SizedBox(height: 12),
            OutlinedButton.icon(
              onPressed: () {
                Clipboard.setData(ClipboardData(text: texto.length > 60 ? texto.substring(0, 60) : texto));
                Navigator.pop(context);
                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Copiado: pégalo en el buscador de tu lector de PDF.')));
              },
              icon: const Icon(Icons.copy),
              label: const Text('Copiar el inicio para buscarlo'),
            ),
          ]),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final v = Map<String, dynamic>.from(c['verificacion'] as Map? ?? {});
    final lectores = ['pdfplumber', 'pypdf'].where((n) => v[n] == true).length;
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(color: Paleta.fondo, borderRadius: BorderRadius.circular(16), border: Border.all(color: Paleta.borde)),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
            decoration: BoxDecoration(color: Paleta.accion, borderRadius: BorderRadius.circular(99)),
            child: Text('Cita ${c['n']}', style: const TextStyle(color: Paleta.fondo, fontWeight: FontWeight.w800, fontSize: 13)),
          ),
          const SizedBox(width: 10),
          Expanded(child: Text('${c['articulo']} · ${donde(c, archivos)}', style: const TextStyle(fontWeight: FontWeight.w700))),
        ]),
        const SizedBox(height: 10),
        Container(
          padding: const EdgeInsets.only(left: 12),
          decoration: const BoxDecoration(border: Border(left: BorderSide(color: Paleta.accion, width: 3))),
          child: SelectableText('${c['texto_literal']}', style: const TextStyle(fontSize: 15.5, height: 1.5)),
        ),
        const SizedBox(height: 10),
        Row(children: [
          const ExcludeSemantics(child: Icon(Icons.verified, size: 18, color: Paleta.cubierto)),
          const SizedBox(width: 6),
          Expanded(
            child: Text(lectores == 2 ? 'Verificada: el texto está literal en esa página de tu PDF.' : 'Verificada en esa página de tu PDF.',
                style: const TextStyle(color: Paleta.textoSecundario, fontSize: 13.5)),
          ),
        ]),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton.icon(
            onPressed: () => _ubicar(context),
            icon: const Icon(Icons.find_in_page_outlined),
            label: Text('Ver esta cláusula en tu póliza · ${donde(c, archivos)}'),
          ),
        ),
      ]),
    );
  }
}

class _Paso extends StatelessWidget {
  const _Paso(this.icono, this.texto);
  final IconData icono;
  final String texto;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          ExcludeSemantics(child: Icon(icono, color: Paleta.accion)),
          const SizedBox(width: 12),
          Expanded(child: Text(texto, style: const TextStyle(fontSize: 16))),
        ]),
      );
}

class Citas extends StatelessWidget {
  const Citas(this.citas, this.archivos, {super.key, this.titulo = 'Citas de tu póliza'});
  final List<Mapa> citas;
  final List<Mapa> archivos;
  final String titulo;

  @override
  Widget build(BuildContext context) {
    if (citas.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Titulo(titulo, icono: Icons.format_quote_rounded),
        const SizedBox(height: 12),
        for (final c in citas) TarjetaCita(c, archivos),
      ]),
    );
  }
}

/// Lo que la póliza menciona pero no trae: cláusulas con nombre propio resaltadas y remisiones
/// a otros documentos plegadas.
class MencionadasAusentes extends StatelessWidget {
  const MencionadasAusentes(this.r, this.archivos, {super.key});
  final Mapa r;
  final List<Mapa> archivos;

  @override
  Widget build(BuildContext context) {
    final bloque = _lista(r['mencionadas_ausentes']);
    String nivel(Mapa m) => '${m['nivel'] ?? (m['tipo'] == 'documento' ? 'remision' : 'clausula_ausente')}';
    final clausulas = bloque.where((m) => nivel(m) == 'clausula_ausente').toList();
    final remisiones = bloque.where((m) => nivel(m) == 'remision').toList();
    final delModelo = _lista(r['no_incluido_en_documento']);
    if (clausulas.isEmpty && remisiones.isEmpty && delModelo.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Titulo('Lo que tu póliza menciona pero no trae', icono: Icons.content_paste_search),
        const SizedBox(height: 10),
        for (final m in clausulas)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Aviso('${m['mensaje']} Se menciona en ${m['seccion']} › ${m['articulo']}, ${donde(m, archivos)}: «${m['mencion']}»',
                icono: Icons.description_outlined, color: Paleta.parcial),
          ),
        for (final m in delModelo)
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Aviso('${m['nombre']} no está en este documento. ${m['por_que_importa']}${refs([m['cita']])}',
                icono: Icons.description_outlined, color: Paleta.parcial),
          ),
        if (remisiones.isNotEmpty)
          Theme(
            data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
            child: ExpansionTile(
              tilePadding: EdgeInsets.zero,
              iconColor: Paleta.accion,
              collapsedIconColor: Paleta.accion,
              title: Text('Remisiones a otros documentos (${remisiones.length}): ahí suelen estar los montos',
                  style: const TextStyle(fontWeight: FontWeight.w600)),
              children: [
                Lista('', [for (final m in remisiones) '${m['mensaje']} Se menciona en ${m['seccion']} › ${m['articulo']}, ${donde(m, archivos)}.'])
              ],
            ),
          ),
      ]),
    );
  }
}

class Pasajes extends StatelessWidget {
  const Pasajes(this.pasajes, this.archivos, {super.key});
  final List<Mapa> pasajes;
  final List<Mapa> archivos;

  @override
  Widget build(BuildContext context) => Column(children: [
        for (final p in pasajes)
          Container(
            margin: const EdgeInsets.only(bottom: 10),
            decoration: BoxDecoration(color: Paleta.fondo, borderRadius: BorderRadius.circular(14), border: Border.all(color: Paleta.borde)),
            child: Theme(
              data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
              child: ExpansionTile(
                iconColor: Paleta.accion,
                collapsedIconColor: Paleta.accion,
                title: Text('${p['seccion']} › ${p['articulo']} · ${donde(p, archivos)}', style: const TextStyle(fontWeight: FontWeight.w600)),
                childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                children: [SelectableText('${p['texto']}')],
              ),
            ),
          ),
      ]);
}

/// Una respuesta completa: veredicto, explicación, ausencias, citas, lo que podría aplicar y el descargo.
class VistaRespuesta extends StatelessWidget {
  const VistaRespuesta(this.r, this.archivos, {super.key});
  final Mapa r;
  final List<Mapa> archivos;

  @override
  Widget build(BuildContext context) {
    final cubre = r['cubre'] as String?;
    final etiqueta = '${r['etiqueta_veredicto'] ?? 'Sin veredicto'}';
    final children = <Widget>[InsigniaVeredicto(cubre: cubre, etiqueta: etiqueta), const SizedBox(height: 14)];
    if (cubre == 'fuera_de_alcance') {
      children.add(Text('${r['respuesta'] ?? ''}'));
    } else if (r['modo'] != 'completo') {
      children.addAll([
        Aviso('${r['aviso'] ?? ''}', icono: Icons.warning_amber_rounded, color: Paleta.parcial),
        MencionadasAusentes(r, archivos),
        const SizedBox(height: 18),
        const Titulo('Cláusulas que encontré para tu pregunta', icono: Icons.manage_search),
        const SizedBox(height: 10),
        Pasajes(_lista(r['pasajes']), archivos),
      ]);
    } else {
      children.addAll([
        Text('${r['respuesta'] ?? ''}', style: Theme.of(context).textTheme.bodyLarge),
        Lista('Condiciones y límites', [for (final c in _lista(r['condiciones'])) '${c['descripcion']}${refs(c['citas'] as List?)}'],
            color: Paleta.parcial),
        Lista('Exclusiones que aplican a lo que contaste',
            [for (final c in _lista(r['exclusiones_aplicables'])) '${c['descripcion']}${refs(c['citas'] as List?)}'], color: Paleta.noCubierto),
        MencionadasAusentes(r, archivos),
        Citas(_lista(r['citas']), archivos),
        if (_lista(r['podrian_aplicar']).isNotEmpty) ...[
          const SizedBox(height: 8),
          const Titulo('Exclusiones que podrían aplicar según tu caso', icono: Icons.help_center_outlined),
          const SizedBox(height: 8),
          Aviso('No es lo que pasó: aplicarían solo si se da algo que no contaste.\n\n'
              '${[for (final p in _lista(r['podrian_aplicar'])) '• ${p['descripcion']}${refs(p['citas'] as List?)}'].join('\n')}'),
        ],
      ]);
    }
    children.addAll([const SizedBox(height: 18), const DescargoRespuesta()]);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: children);
  }
}

class VistaPasos extends StatelessWidget {
  const VistaPasos(this.r, this.archivos, {super.key});
  final Mapa r;
  final List<Mapa> archivos;

  String _fecha(String iso) {
    final p = iso.split('-');
    return '${p[2]}/${p[1]}/${p[0]}';
  }

  @override
  Widget build(BuildContext context) {
    final children = <Widget>[];
    if (r['modo'] != 'pasos') {
      children.addAll([Aviso('${r['aviso'] ?? ''}', icono: Icons.warning_amber_rounded, color: Paleta.parcial), const SizedBox(height: 12),
          Pasajes(_lista(r['pasajes']), archivos)]);
    } else {
      for (final p in _lista(r['plazos'])) {
        final plazo = '${p['cantidad']} ${p['unidad'] == 'horas' ? 'horas' : 'días'}';
        final c = p['calculo'] as Map?;
        if (c == null) {
          children.add(Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Aviso('Plazo para ${p['para']}: $plazo, ${p['desde']}${refs([p['cita']])}. Indica cuándo ocurrió y calculo la fecha límite.',
                icono: Icons.hourglass_bottom, color: Paleta.parcial),
          ));
          continue;
        }
        final vencido = c['vencido'] == true;
        final dias = c['dias_restantes'] as int? ?? 0;
        final cuanto = vencido ? 'ya venció' : dias == 0 ? 'vence hoy' : 'quedan $dias día${dias == 1 ? '' : 's'}';
        final urgente = vencido || dias <= 2;
        children.add(Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Aviso(
            'Fecha límite para ${p['para']}: ${_fecha('${c['fecha_limite']}')} ($cuanto). Son $plazo ${p['desde']}${refs([p['cita']])}, '
            'contados desde el ${_fecha('${c['fecha_hecho']}')}.${[for (final n in (c['notas'] as List? ?? [])) '\n\n$n'].join()}',
            icono: urgente ? Icons.alarm : Icons.hourglass_bottom,
            color: urgente ? Paleta.noCubierto : Paleta.parcial,
          ),
        ));
      }
      if (r['sin_plazo'] != null) children.add(Aviso('${r['sin_plazo']}'));
      children.addAll([
        Lista('A quién avisar', [for (final x in _lista(r['a_quien_avisar'])) '${x['descripcion']}${refs(x['citas'] as List?)}']),
        Lista('Documentos que tienes que presentar', [for (final x in _lista(r['documentos'])) '${x['descripcion']}${refs(x['citas'] as List?)}']),
        Lista('Pasos', [
          for (final (i, x) in _lista(r['pasos']).indexed) '${i + 1}. ${x['descripcion']}${refs(x['citas'] as List?)}'
        ]),
        MencionadasAusentes({...r, 'no_incluido_en_documento': []}, archivos),
        Citas(_lista(r['citas']), archivos),
      ]);
    }
    children.addAll([const SizedBox(height: 16), const DescargoRespuesta()]);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: children);
  }
}

class VistaRadiografia extends StatelessWidget {
  const VistaRadiografia(this.r, this.archivos, {super.key});
  final Mapa r;
  final List<Mapa> archivos;

  @override
  Widget build(BuildContext context) {
    final noEncontrado = Map<String, dynamic>.from(r['no_encontrado'] as Map? ?? {});
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      if (r['modo'] != 'radiografia') Aviso('${r['aviso'] ?? ''}', icono: Icons.warning_amber_rounded, color: Paleta.parcial),
      Lista('Qué cubre y hasta cuánto', [
        for (final c in _lista(r['coberturas']))
          '${c['nombre']}: ${c['que_cubre']} ${c['limite'] != null ? 'Hasta: ${c['limite']}.' : 'Monto: no está en este documento.'}${refs(c['citas'] as List?)}'
      ], color: Paleta.cubierto),
      for (final (titulo, campo, color) in [
        ('Exclusiones principales', 'exclusiones', Paleta.noCubierto),
        ('Deducibles y copagos', 'deducibles', Paleta.parcial),
        ('Carencias y períodos de espera', 'carencias', Paleta.parcial),
      ])
        _lista(r[campo]).isEmpty
            ? Padding(
                padding: const EdgeInsets.only(top: 18),
                child: Text('$titulo: ${noEncontrado[campo] ?? 'no está en este documento.'}',
                    style: const TextStyle(color: Paleta.textoSecundario)),
              )
            : Lista(titulo, [for (final x in _lista(r[campo])) '${x['descripcion']}${refs(x['citas'] as List?)}'], color: color),
      MencionadasAusentes({...r, 'no_incluido_en_documento': []}, archivos),
      Citas(_lista(r['citas']), archivos),
      const SizedBox(height: 10),
      const Text('Es un resumen de los pasajes más relevantes de tu póliza, no la póliza entera.', style: TextStyle(color: Paleta.textoSecundario)),
      const SizedBox(height: 16),
      const DescargoRespuesta(),
    ]);
  }
}

import 'package:material_ui/material_ui.dart';

import 'comun.dart';
import 'estado.dart';
import 'tema.dart';
import 'visor_pdf.dart';

typedef Mapa = Map<String, dynamic>;

List<Mapa> lista(dynamic v) => v == null ? [] : List<Mapa>.from((v as List).map((x) => Map<String, dynamic>.from(x as Map)));

/// Página de corrido → (índice del archivo, página dentro de ese archivo), si la póliza vino en varios PDF.
(int, int) ubicar(List<Mapa> archivos, int pagina) {
  if (archivos.length < 2) return (0, pagina);
  var desde = 0;
  for (final (i, a) in archivos.indexed) {
    final n = a['paginas'] as int;
    if (pagina <= desde + n) return (i, pagina - desde);
    desde += n;
  }
  return (archivos.length - 1, pagina);
}

String donde(Mapa c, List<Mapa> archivos) {
  final paginas = (c['paginas'] as List?)?.cast<int>() ?? [c['pagina'] as int];
  String una(int pagina) {
    if (archivos.length < 2) return 'pág. $pagina';
    final (i, p) = ubicar(archivos, pagina);
    return '${archivos[i]['nombre']}, pág. $p';
  }

  return paginas.length == 1 || paginas.first == paginas.last ? una(paginas.first) : '${una(paginas.first)} a ${una(paginas.last)}';
}

String refs(List? numeros) {
  final n = (numeros ?? const []).cast<int>();
  if (n.isEmpty) return '';
  return n.length == 1 ? ' (cita ${n.first})' : ' (citas ${n.join(', ')})';
}

class Lista extends StatelessWidget {
  const Lista(this.titulo, this.items, {super.key, this.color = Paleta.textoSecundario});
  final String titulo;
  final List<String> items;
  final Color color;

  @override
  Widget build(BuildContext context) {
    if (items.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (titulo.isNotEmpty)
            Semantics(
              header: true,
              child: Text(titulo, style: Theme.of(context).textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w700)),
            ),
          const SizedBox(height: 8),
          for (final i in items)
            Padding(
              padding: const EdgeInsets.only(bottom: 8),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Padding(
                    padding: const EdgeInsets.only(top: 8),
                    child: ExcludeSemantics(child: Icon(Icons.circle, size: 7, color: color)),
                  ),
                  const SizedBox(width: 10),
                  Expanded(child: Text(i)),
                ],
              ),
            ),
        ],
      ),
    );
  }
}

/// Una cita verificada: el texto citado en su bloque, y debajo el botón que abre el PDF en esa página.
class TarjetaCita extends StatelessWidget {
  const TarjetaCita(this.c, this.poliza, {super.key});
  final Mapa c;
  final PolizaActual? poliza;

  @override
  Widget build(BuildContext context) {
    final archivos = poliza?.archivos ?? const <Mapa>[];
    final pagina = (c['pagina'] as int?) ?? ((c['paginas'] as List?)?.first as int? ?? 1);
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Paleta.superficie,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: Paleta.borde),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 3),
                decoration: BoxDecoration(color: Paleta.accion, borderRadius: BorderRadius.circular(99)),
                child: Text(
                  'Cita ${c['n']}',
                  style: const TextStyle(color: Paleta.sobreAccion, fontWeight: FontWeight.w800, fontSize: 13),
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text('${c['articulo']} · ${donde(c, archivos)}', style: const TextStyle(fontWeight: FontWeight.w700)),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Container(
            width: double.infinity,
            padding: const EdgeInsets.fromLTRB(14, 10, 12, 10),
            decoration: const BoxDecoration(
              color: Paleta.citaFondo,
              border: Border(left: BorderSide(color: Paleta.accion, width: 4)),
            ),
            child: SelectableText('${c['texto_literal']}', style: const TextStyle(fontSize: 15.5, height: 1.5, color: Paleta.texto)),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              const ExcludeSemantics(child: Icon(Icons.verified, size: 18, color: Paleta.cubierto)),
              const SizedBox(width: 6),
              const Expanded(
                child: Text(
                  'Verificada: el texto está literal en esa página de tu PDF.',
                  style: TextStyle(color: Paleta.textoSecundario, fontSize: 13.5),
                ),
              ),
            ],
          ),
          if (poliza != null)
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                onPressed: () => abrirEnLaPagina(context, poliza!, pagina),
                icon: const Icon(Icons.find_in_page_outlined),
                label: Text('Ver esta cláusula en tu póliza · ${donde(c, archivos)}'),
              ),
            ),
        ],
      ),
    );
  }
}

class Citas extends StatelessWidget {
  const Citas(this.citas, this.poliza, {super.key, this.titulo = 'Citas de tu póliza'});
  final List<Mapa> citas;
  final PolizaActual? poliza;
  final String titulo;

  @override
  Widget build(BuildContext context) {
    if (citas.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Titulo(titulo, icono: Icons.format_quote_rounded),
          const SizedBox(height: 12),
          for (final c in citas) TarjetaCita(c, poliza),
        ],
      ),
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
    final bloque = lista(r['mencionadas_ausentes']);
    String nivel(Mapa m) => '${m['nivel'] ?? (m['tipo'] == 'documento' ? 'remision' : 'clausula_ausente')}';
    final clausulas = bloque.where((m) => nivel(m) == 'clausula_ausente').toList();
    final remisiones = bloque.where((m) => nivel(m) == 'remision').toList();
    final delModelo = lista(r['no_incluido_en_documento']);
    if (clausulas.isEmpty && remisiones.isEmpty && delModelo.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Titulo('Lo que tu póliza menciona pero no trae', icono: Icons.content_paste_search),
          const SizedBox(height: 10),
          for (final m in clausulas)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Aviso(
                '${m['mensaje']} Se menciona en ${m['seccion']} › ${m['articulo']}, ${donde(m, archivos)}.',
                icono: Icons.description_outlined,
                color: Paleta.parcial,
              ),
            ),
          for (final m in delModelo)
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Aviso(
                '${m['nombre']} no está en este documento. ${m['por_que_importa']}${refs([m['cita']])}',
                icono: Icons.description_outlined,
                color: Paleta.parcial,
              ),
            ),
          if (remisiones.isNotEmpty)
            Lista('Remisiones a otros documentos (ahí suelen estar los montos)', [
              for (final m in remisiones) '${m['mensaje']} Se menciona en ${m['seccion']} › ${m['articulo']}, ${donde(m, archivos)}.',
            ]),
        ],
      ),
    );
  }
}

class Pasajes extends StatelessWidget {
  const Pasajes(this.pasajes, this.archivos, {super.key});
  final List<Mapa> pasajes;
  final List<Mapa> archivos;

  @override
  Widget build(BuildContext context) => Column(
    children: [
      for (final p in pasajes)
        Padding(
          padding: const EdgeInsets.only(bottom: 10),
          child: Material(
            color: Paleta.superficie,
            clipBehavior: Clip.antiAlias,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(14),
              side: const BorderSide(color: Paleta.borde),
            ),
            child: Theme(
              data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
              child: ExpansionTile(
                iconColor: Paleta.accion,
                collapsedIconColor: Paleta.accion,
                title: Text(
                  '${p['seccion']} › ${p['articulo']} · ${donde(p, archivos)}',
                  style: const TextStyle(fontWeight: FontWeight.w600),
                ),
                childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                children: [SelectableText('${p['texto']}')],
              ),
            ),
          ),
        ),
    ],
  );
}

/// Plegado: el detalle debajo del veredicto. Abierto en el historial, donde se lee completo.
class Detalle extends StatelessWidget {
  const Detalle({super.key, required this.children, this.abierto = false, this.titulo = 'Ver el detalle y las citas'});
  final List<Widget> children;
  final bool abierto;
  final String titulo;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 16),
    child: Material(
      color: Paleta.fondo,
      clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(16),
        side: const BorderSide(color: Paleta.borde),
      ),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          initiallyExpanded: abierto,
          iconColor: Paleta.accion,
          collapsedIconColor: Paleta.accion,
          title: Text(
            titulo,
            style: const TextStyle(fontWeight: FontWeight.w700, color: Paleta.accion),
          ),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          children: children,
        ),
      ),
    ),
  );
}

/// Una respuesta: el veredicto y por qué arriba, en 2 o 3 líneas; el resto, plegado; el descargo, siempre visible.
class VistaRespuesta extends StatelessWidget {
  const VistaRespuesta(this.r, this.poliza, {super.key, this.detalleAbierto = false});
  final Mapa r;
  final PolizaActual? poliza;
  final bool detalleAbierto;

  @override
  Widget build(BuildContext context) {
    final archivos = poliza?.archivos ?? const <Mapa>[];
    final cubre = r['cubre'] as String?;
    final etiqueta = '${r['etiqueta_veredicto'] ?? 'Sin veredicto'}';
    final razonamiento = '${r['razonamiento'] ?? ''}'.trim();
    final limite = r['limite'] is Map ? Map<String, dynamic>.from(r['limite'] as Map) : null;
    final children = <Widget>[InsigniaVeredicto(cubre: cubre, etiqueta: etiqueta), const SizedBox(height: 12)];
    if (cubre == 'fuera_de_alcance') {
      children.add(Text('${r['respuesta'] ?? ''}', style: Theme.of(context).textTheme.bodyLarge));
    } else if (r['modo'] != 'completo') {
      children.addAll([
        Aviso('${r['aviso'] ?? ''}', icono: Icons.warning_amber_rounded, color: Paleta.parcial),
        Detalle(
          abierto: detalleAbierto,
          titulo: 'Ver las cláusulas que encontré',
          children: [MencionadasAusentes(r, archivos), const SizedBox(height: 8), Pasajes(lista(r['pasajes']), archivos)],
        ),
      ]);
    } else {
      children.add(
        Text(
          razonamiento.isNotEmpty ? razonamiento : '${r['respuesta'] ?? ''}',
          style: const TextStyle(fontSize: 17.5, height: 1.5, color: Paleta.texto),
        ),
      );
      if (limite != null && '${limite['descripcion'] ?? ''}'.isNotEmpty) {
        children.add(
          Padding(
            padding: const EdgeInsets.only(top: 10),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const ExcludeSemantics(child: Icon(Icons.rule, color: Paleta.parcial, size: 20)),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    'Límite: ${limite['descripcion']}${refs([limite['cita']])}',
                    style: const TextStyle(color: Paleta.parcial, fontWeight: FontWeight.w700),
                  ),
                ),
              ],
            ),
          ),
        );
      }
      children.add(
        Detalle(
          abierto: detalleAbierto,
          children: [
            if (razonamiento.isNotEmpty) Text('${r['respuesta'] ?? ''}', style: Theme.of(context).textTheme.bodyLarge),
            Lista('Condiciones', [
              for (final c in lista(r['condiciones'])) '${c['descripcion']}${refs(c['citas'] as List?)}',
            ], color: Paleta.parcial),
            Lista('Exclusiones que aplican a lo que contaste', [
              for (final c in lista(r['exclusiones_aplicables'])) '${c['descripcion']}${refs(c['citas'] as List?)}',
            ]),
            Lista('Exclusiones que podrían aplicar si se da algo que no contaste', [
              for (final p in lista(r['podrian_aplicar'])) '${p['descripcion']}${refs(p['citas'] as List?)}',
            ]),
            MencionadasAusentes(r, archivos),
            Citas(lista(r['citas']), poliza),
          ],
        ),
      );
    }
    children.addAll([const SizedBox(height: 16), const DescargoRespuesta()]);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: children);
  }
}

class VistaPasos extends StatelessWidget {
  const VistaPasos(this.r, this.poliza, {super.key});
  final Mapa r;
  final PolizaActual? poliza;

  String _fecha(String iso) {
    final p = iso.split('-');
    return '${p[2]}/${p[1]}/${p[0]}';
  }

  @override
  Widget build(BuildContext context) {
    final archivos = poliza?.archivos ?? const <Mapa>[];
    final children = <Widget>[];
    if (r['modo'] != 'pasos') {
      children.addAll([
        Aviso('${r['aviso'] ?? ''}', icono: Icons.warning_amber_rounded, color: Paleta.parcial),
        const SizedBox(height: 12),
        Pasajes(lista(r['pasajes']), archivos),
      ]);
    } else {
      for (final p in lista(r['plazos'])) {
        final plazo = '${p['cantidad']} ${p['unidad'] == 'horas' ? 'horas' : 'días'}';
        final c = p['calculo'] as Map?;
        if (c == null) {
          children.add(
            Padding(
              padding: const EdgeInsets.only(bottom: 10),
              child: Aviso(
                'Plazo para ${p['para']}: $plazo, ${p['desde']}${refs([p['cita']])}. Indica cuándo ocurrió y calculo la fecha límite.',
                icono: Icons.hourglass_bottom,
                color: Paleta.parcial,
              ),
            ),
          );
          continue;
        }
        final vencido = c['vencido'] == true;
        final dias = c['dias_restantes'] as int? ?? 0;
        final cuanto = vencido
            ? 'ya venció'
            : dias == 0
            ? 'vence hoy'
            : 'quedan $dias día${dias == 1 ? '' : 's'}';
        children.add(
          Padding(
            padding: const EdgeInsets.only(bottom: 10),
            child: Aviso(
              'Fecha límite para ${p['para']}: ${_fecha('${c['fecha_limite']}')} ($cuanto). Son $plazo ${p['desde']}${refs([p['cita']])}, '
              'contados desde el ${_fecha('${c['fecha_hecho']}')}.${[for (final n in (c['notas'] as List? ?? [])) '\n\n$n'].join()}',
              icono: vencido || dias <= 2 ? Icons.alarm : Icons.hourglass_bottom,
              color: Paleta.parcial,
            ),
          ),
        );
      }
      if (r['sin_plazo'] != null) children.add(Aviso('${r['sin_plazo']}'));
      children.addAll([
        Lista('A quién avisar', [for (final x in lista(r['a_quien_avisar'])) '${x['descripcion']}${refs(x['citas'] as List?)}']),
        Lista('Documentos que tienes que presentar', [
          for (final x in lista(r['documentos'])) '${x['descripcion']}${refs(x['citas'] as List?)}',
        ]),
        Lista('Pasos', [for (final (i, x) in lista(r['pasos']).indexed) '${i + 1}. ${x['descripcion']}${refs(x['citas'] as List?)}']),
        Detalle(
          children: [
            MencionadasAusentes({...r, 'no_incluido_en_documento': []}, archivos),
            Citas(lista(r['citas']), poliza),
          ],
        ),
      ]);
    }
    children.addAll([const SizedBox(height: 16), const DescargoRespuesta()]);
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: children);
  }
}

class VistaRadiografia extends StatelessWidget {
  const VistaRadiografia(this.r, this.poliza, {super.key});
  final Mapa r;
  final PolizaActual? poliza;

  @override
  Widget build(BuildContext context) {
    final archivos = poliza?.archivos ?? const <Mapa>[];
    final noEncontrado = Map<String, dynamic>.from(r['no_encontrado'] as Map? ?? {});
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (r['modo'] != 'radiografia') Aviso('${r['aviso'] ?? ''}', icono: Icons.warning_amber_rounded, color: Paleta.parcial),
        Lista('Qué cubre y hasta cuánto', [
          for (final c in lista(r['coberturas']))
            '${c['nombre']}: ${c['que_cubre']} ${c['limite'] != null ? 'Hasta: ${c['limite']}.' : 'Monto: no está en este documento.'}${refs(c['citas'] as List?)}',
        ], color: Paleta.cubierto),
        for (final (titulo, campo) in [
          ('Exclusiones principales', 'exclusiones'),
          ('Deducibles y copagos', 'deducibles'),
          ('Carencias y períodos de espera', 'carencias'),
        ])
          lista(r[campo]).isEmpty
              ? Padding(
                  padding: const EdgeInsets.only(top: 18),
                  child: Text(
                    '$titulo: ${noEncontrado[campo] ?? 'no está en este documento.'}',
                    style: const TextStyle(color: Paleta.textoSecundario),
                  ),
                )
              : Lista(titulo, [for (final x in lista(r[campo])) '${x['descripcion']}${refs(x['citas'] as List?)}']),
        Detalle(
          children: [
            MencionadasAusentes({...r, 'no_incluido_en_documento': []}, archivos),
            Citas(lista(r['citas']), poliza),
          ],
        ),
        const SizedBox(height: 10),
        const Text(
          'Es un resumen de los pasajes más relevantes de tu póliza, no la póliza entera.',
          style: TextStyle(color: Paleta.textoSecundario),
        ),
        const SizedBox(height: 16),
        const DescargoRespuesta(),
      ],
    );
  }
}

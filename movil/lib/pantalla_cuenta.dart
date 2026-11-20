import 'package:google_sign_in/google_sign_in.dart';
import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import 'api.dart';
import 'comun.dart';
import 'compras.dart';
import 'resultado.dart';
import 'tema.dart';
import 'textos.dart';

/// Mi cuenta. Sin contadores: ni consultas, ni pólizas usadas de un total.
class PantallaCuenta extends StatelessWidget {
  const PantallaCuenta({super.key, required this.compras});
  final Compras compras;

  @override
  Widget build(BuildContext context) {
    final e = EstadoScope.of(context);
    final ancho = MediaQuery.sizeOf(context).width;
    return SafeArea(
      child: ListView(padding: EdgeInsets.symmetric(horizontal: ancho > 900 ? 32 : 16, vertical: 16), children: [
        Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              Semantics(header: true, child: Text('Mi cuenta', style: Theme.of(context).textTheme.headlineMedium)),
              const SizedBox(height: 16),
              if (!e.cuentasDisponibles)
                const Tarjeta(child: Aviso('Las cuentas todavía no están disponibles.'))
              else if (!e.conCuenta)
                const _Acceso()
              else ...[
                _Resumen(compras: compras),
                const SizedBox(height: 16),
                const _Guardadas(),
                const SizedBox(height: 16),
                const _PagasDoble(),
                const SizedBox(height: 16),
                const _ZonaBorrado(),
              ],
              const SizedBox(height: 16),
              _Privacidad(politica: e.politica),
            ]),
          ),
        ),
      ]),
    );
  }
}

class _Privacidad extends StatelessWidget {
  const _Privacidad({required this.politica});
  final String politica;

  @override
  Widget build(BuildContext context) => Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text(Textos.privacidadCorta, style: TextStyle(color: Paleta.textoSecundario, fontSize: 13.5)),
        TextButton.icon(
          style: TextButton.styleFrom(padding: EdgeInsets.zero, alignment: Alignment.centerLeft),
          onPressed: () => launchUrl(Uri.parse(politica), mode: LaunchMode.externalApplication),
          icon: const Icon(Icons.privacy_tip_outlined),
          label: const Text('Política de privacidad'),
        ),
      ]);
}

class _Casilla extends StatelessWidget {
  const _Casilla({required this.valor, required this.alCambiar, required this.politica});
  final bool valor;
  final ValueChanged<bool> alCambiar;
  final String politica;

  @override
  Widget build(BuildContext context) => Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Checkbox(value: valor, onChanged: (v) => alCambiar(v ?? false),
            semanticLabel: 'Acepto la política de privacidad y que se guarde el texto de mi póliza y mis consultas'),
        Expanded(
          child: Padding(
            padding: const EdgeInsets.only(top: 12),
            child: Wrap(children: [
              const Text('Acepto la '),
              InkWell(
                onTap: () => launchUrl(Uri.parse(politica), mode: LaunchMode.externalApplication),
                child: const Text('política de privacidad',
                    style: TextStyle(color: Paleta.accion, decoration: TextDecoration.underline, decorationColor: Paleta.accion)),
              ),
              const Text(' y que se guarde el texto de mi póliza y mis consultas, que pueden incluir datos de salud.'),
            ]),
          ),
        ),
      ]);
}

class _Acceso extends StatefulWidget {
  const _Acceso();

  @override
  State<_Acceso> createState() => _AccesoState();
}

class _AccesoState extends State<_Acceso> {
  final _correo = TextEditingController();
  final _clave = TextEditingController();
  bool _crear = false;
  bool _acepto = false;
  bool _ocupado = false;
  bool _pideCasillaGoogle = false;

  @override
  void dispose() {
    _correo.dispose();
    _clave.dispose();
    super.dispose();
  }

  Future<void> _hacer(Future<void> Function() accion) async {
    setState(() => _ocupado = true);
    try {
      await accion();
    } on GoogleSignInException catch (err) {
      if (err.code != GoogleSignInExceptionCode.canceled && mounted) mostrarError(context, ErrorApi('No pude entrar con Google.'));
    } catch (err) {
      if (mounted) mostrarError(context, err);
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final e = EstadoScope.of(context);
    if (_pideCasillaGoogle) {
      return Tarjeta(
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          const Titulo('Crea tu cuenta con Google', icono: Icons.person_add_alt_1_rounded),
          const SizedBox(height: 12),
          _Casilla(valor: _acepto, alCambiar: (v) => setState(() => _acepto = v), politica: e.politica),
          const SizedBox(height: 12),
          FilledButton(
            onPressed: _ocupado
                ? null
                : () => _hacer(() async {
                      if (!_acepto) throw ErrorApi('Marca la casilla para crear tu cuenta.');
                      await e.entrarConGoogle(acepto: true);
                    }),
            child: const Text('Crear mi cuenta'),
          ),
          TextButton(onPressed: () => setState(() { _pideCasillaGoogle = false; e.cancelarGoogle(); }), child: const Text('Cancelar')),
        ]),
      );
    }
    return Tarjeta(
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Text('Guarda tu póliza para no subirla cada vez y vuelve a tus consultas.', style: TextStyle(color: Paleta.textoSecundario)),
        const SizedBox(height: 16),
        if (e.config['google_server_client_id'] != null) ...[
          FilledButton.icon(
            onPressed: _ocupado
                ? null
                : () => _hacer(() async {
                      final listo = await e.entrarConGoogle();
                      if (!listo && mounted) setState(() => _pideCasillaGoogle = true);
                    }),
            icon: const Icon(Icons.account_circle_rounded),
            label: const Text('Entrar con Google'),
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(56)),
          ),
          const SizedBox(height: 14),
          const Row(children: [
            Expanded(child: Divider()),
            Padding(padding: EdgeInsets.symmetric(horizontal: 12), child: Text('o con tu correo', style: TextStyle(color: Paleta.textoSecundario))),
            Expanded(child: Divider()),
          ]),
          const SizedBox(height: 14),
        ],
        SegmentedButton<bool>(
          segments: const [ButtonSegment(value: false, label: Text('Entrar')), ButtonSegment(value: true, label: Text('Crear cuenta'))],
          selected: {_crear},
          onSelectionChanged: (s) => setState(() => _crear = s.first),
        ),
        const SizedBox(height: 14),
        TextField(controller: _correo, keyboardType: TextInputType.emailAddress, autofillHints: const [AutofillHints.email],
            decoration: const InputDecoration(labelText: 'Correo')),
        const SizedBox(height: 12),
        TextField(controller: _clave, obscureText: true, autofillHints: [_crear ? AutofillHints.newPassword : AutofillHints.password],
            decoration: InputDecoration(labelText: _crear ? 'Contraseña (8 caracteres o más)' : 'Contraseña')),
        if (_crear) ...[const SizedBox(height: 8), _Casilla(valor: _acepto, alCambiar: (v) => setState(() => _acepto = v), politica: e.politica)],
        const SizedBox(height: 14),
        OutlinedButton(
          onPressed: _ocupado
              ? null
              : () => _hacer(() async {
                    if (_crear) {
                      if (!_acepto) throw ErrorApi('Marca la casilla para crear tu cuenta.');
                      await e.registrar(_correo.text.trim(), _clave.text, true);
                    } else {
                      await e.entrar(_correo.text.trim(), _clave.text);
                    }
                  }),
          child: Text(_crear ? 'Crear mi cuenta' : 'Entrar'),
        ),
        if (!_crear)
          TextButton(onPressed: () => setState(() => _crear = true), child: const Text('¿Olvidaste tu contraseña?')),
      ]),
    );
  }
}

class _Resumen extends StatefulWidget {
  const _Resumen({required this.compras});
  final Compras compras;

  @override
  State<_Resumen> createState() => _ResumenState();
}

class _ResumenState extends State<_Resumen> {
  bool _comprando = false;

  @override
  Widget build(BuildContext context) {
    final e = EstadoScope.of(context);
    final c = e.cuenta!;
    final ofrecer = !e.premium || c['volver_a_comprar'] == true;
    return Tarjeta(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const CircleAvatar(radius: 24, backgroundColor: Paleta.fondo, child: Icon(Icons.person_rounded, color: Paleta.accion)),
          const SizedBox(width: 14),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${c['correo']}', style: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16)),
              const SizedBox(height: 4),
              Row(children: [
                ExcludeSemantics(child: Icon(e.premium ? Icons.workspace_premium_rounded : Icons.person_outline,
                    size: 18, color: e.premium ? Paleta.parcial : Paleta.textoSecundario)),
                const SizedBox(width: 4),
                Text(e.premium ? 'Premium' : 'Plan gratuito', style: const TextStyle(color: Paleta.textoSecundario)),
              ]),
            ]),
          ),
          IconButton(
            tooltip: 'Cerrar sesión',
            icon: const Icon(Icons.logout_rounded),
            onPressed: () => e.salir(),
          ),
        ]),
        if (ofrecer) ...[
          const Divider(height: 32),
          if (!e.premium) ...[
            for (final f in Textos.funcionesPremium)
              Padding(
                padding: const EdgeInsets.only(bottom: 8),
                child: Row(children: [
                  const ExcludeSemantics(child: Icon(Icons.check_rounded, color: Paleta.cubierto)),
                  const SizedBox(width: 10),
                  Expanded(child: Text(f)),
                ]),
              ),
            const SizedBox(height: 8),
          ],
          FilledButton.icon(
            onPressed: _comprando
                ? null
                : () async {
                    setState(() => _comprando = true);
                    try {
                      await widget.compras.comprar();
                    } catch (err) {
                      if (context.mounted) mostrarError(context, err);
                    } finally {
                      if (mounted) setState(() => _comprando = false);
                    }
                  },
            icon: const Icon(Icons.workspace_premium_rounded),
            label: const Text(Textos.botonPremium),
            style: FilledButton.styleFrom(minimumSize: const Size.fromHeight(54)),
          ),
        ],
      ]),
    );
  }
}

class _Guardadas extends StatelessWidget {
  const _Guardadas();

  @override
  Widget build(BuildContext context) {
    final e = EstadoScope.of(context);
    return Tarjeta(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Titulo('Tus pólizas guardadas', icono: Icons.bookmarks_rounded),
        const SizedBox(height: 12),
        if (e.guardadas.isEmpty)
          const Text('Ninguna todavía. Sube tu PDF en «Tu póliza» y toca «Guardar en mi cuenta».', style: TextStyle(color: Paleta.textoSecundario)),
        for (final g in e.guardadas) _TarjetaGuardada(g),
      ]),
    );
  }
}

class _TarjetaGuardada extends StatefulWidget {
  const _TarjetaGuardada(this.g);
  final Mapa g;

  @override
  State<_TarjetaGuardada> createState() => _TarjetaGuardadaState();
}

class _TarjetaGuardadaState extends State<_TarjetaGuardada> {
  List<Mapa>? _historial;

  Future<void> _cargar() async {
    final r = await EstadoScope.of(context).api.get('/polizas/${widget.g['poliza_id']}/consultas');
    if (mounted) setState(() => _historial = [for (final x in r['consultas'] as List) Map<String, dynamic>.from(x as Map)]);
  }

  Future<void> _borrarPoliza() async {
    final e = EstadoScope.of(context);
    final si = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: Paleta.superficie,
        title: const Text('¿Borrar esta póliza?'),
        content: const Text('Se borra con sus consultas y no se puede deshacer.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Conservarla')),
          FilledButton(style: FilledButton.styleFrom(backgroundColor: Paleta.noCubierto), onPressed: () => Navigator.pop(context, true),
              child: const Text('Sí, borrarla')),
        ],
      ),
    );
    if (si != true) return;
    await e.api.delete('/polizas/${widget.g['poliza_id']}');
    if (e.poliza?.id == widget.g['poliza_id']) e.elegir(null);
    await e.refrescarCuenta();
  }

  @override
  Widget build(BuildContext context) {
    final g = widget.g;
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(color: Paleta.fondo, borderRadius: BorderRadius.circular(16), border: Border.all(color: Paleta.borde)),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          iconColor: Paleta.accion,
          collapsedIconColor: Paleta.accion,
          onExpansionChanged: (abierto) => abierto && _historial == null ? _cargar() : null,
          title: Text('${g['nombre']}', style: const TextStyle(fontWeight: FontWeight.w700)),
          subtitle: Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Align(
              alignment: Alignment.centerLeft,
              child: g['borrado_automatico'] == null
                  ? const Text('No se borra sola', style: TextStyle(color: Paleta.textoSecundario))
                  : InsigniaBorrado('${g['borrado_automatico']}'),
            ),
          ),
          childrenPadding: const EdgeInsets.fromLTRB(16, 0, 16, 12),
          children: [
            if (_historial == null) const Cargando('Cargando tus consultas…'),
            if (_historial != null && _historial!.isEmpty) const Text('Sin consultas todavía.', style: TextStyle(color: Paleta.textoSecundario)),
            for (final c in _historial ?? <Mapa>[])
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: Text('${c['pregunta']}', style: const TextStyle(fontWeight: FontWeight.w600)),
                subtitle: Text(
                  [for (final s in (c['respuestas'] as List? ?? [c])) '${(s as Map)['etiqueta_veredicto'] ?? 'Sin veredicto'}'].join(' · '),
                  style: const TextStyle(color: Paleta.textoSecundario),
                ),
                trailing: IconButton(
                  tooltip: 'Borrar esta consulta',
                  icon: const Icon(Icons.delete_outline, color: Paleta.noCubierto),
                  onPressed: () async {
                    await EstadoScope.of(context).api.delete('/consultas/${c['consulta_id']}');
                    if (mounted) _cargar();
                  },
                ),
              ),
            Align(
              alignment: Alignment.centerLeft,
              child: TextButton.icon(
                style: TextButton.styleFrom(foregroundColor: Paleta.noCubierto),
                onPressed: () => _borrarPoliza().catchError((Object err) {
                  if (mounted) mostrarError(context, err);
                }),
                icon: const Icon(Icons.delete_forever_outlined),
                label: const Text('Borrar esta póliza'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _PagasDoble extends StatefulWidget {
  const _PagasDoble();

  @override
  State<_PagasDoble> createState() => _PagasDobleState();
}

class _PagasDobleState extends State<_PagasDoble> {
  final Set<String> _elegidas = {};
  bool _cargando = false;
  Mapa? _r;

  @override
  Widget build(BuildContext context) {
    final e = EstadoScope.of(context);
    final permitido = (e.cuenta?['funciones'] as Map?)?['superposiciones'] == true;
    return Tarjeta(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Titulo('¿Pagas doble?', icono: Icons.compare_arrows_rounded),
        const SizedBox(height: 6),
        const Text('Coberturas que se repiten entre tus pólizas.', style: TextStyle(color: Paleta.textoSecundario)),
        const SizedBox(height: 12),
        if (!permitido)
          Bloqueada(texto: '${Textos.botonPremium} para comparar tus pólizas')
        else if (e.guardadas.length < 2)
          const Text('Guarda al menos dos pólizas para compararlas.', style: TextStyle(color: Paleta.textoSecundario))
        else ...[
          for (final g in e.guardadas)
            CheckboxListTile(
              contentPadding: EdgeInsets.zero,
              value: _elegidas.contains(g['poliza_id']),
              title: Text('${g['nombre']}'),
              onChanged: (v) => setState(() => v == true ? _elegidas.add('${g['poliza_id']}') : _elegidas.remove(g['poliza_id'])),
            ),
          FilledButton(
            onPressed: _elegidas.length < 2 || _cargando
                ? null
                : () async {
                    setState(() => _cargando = true);
                    try {
                      final r = await e.api.post('/superposiciones', {'poliza_ids': _elegidas.toList()});
                      setState(() => _r = Map<String, dynamic>.from(r as Map));
                    } catch (err) {
                      if (context.mounted) mostrarError(context, err);
                    } finally {
                      if (mounted) setState(() => _cargando = false);
                    }
                  },
            child: const Text('Comparar'),
          ),
          if (_cargando) const Cargando('Comparando tus pólizas…'),
          if (_r != null) ...[
            const SizedBox(height: 12),
            Aviso('${_r!['aviso']}'),
            Lista('Coincidencias', [
              for (final p in (_r!['pares'] as List))
                '${p['a']['poliza']}: ${p['a']['cobertura']} y ${p['b']['poliza']}: ${p['b']['cobertura']}. ${p['por_que']}'
            ]),
            const SizedBox(height: 12),
            const DescargoRespuesta(),
          ],
        ],
      ]),
    );
  }
}

class _ZonaBorrado extends StatefulWidget {
  const _ZonaBorrado();

  @override
  State<_ZonaBorrado> createState() => _ZonaBorradoState();
}

class _ZonaBorradoState extends State<_ZonaBorrado> {
  final _clave = TextEditingController();
  bool _seguro = false;

  @override
  void dispose() {
    _clave.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final e = EstadoScope.of(context);
    final conClave = e.cuenta?['acceso'] != 'google';
    return Tarjeta(
      borde: Paleta.noCubierto,
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        const Titulo('Borrar mi cuenta y todo', icono: Icons.delete_forever_rounded),
        const SizedBox(height: 12),
        if (conClave) TextField(controller: _clave, obscureText: true, decoration: const InputDecoration(labelText: 'Tu contraseña')),
        CheckboxListTile(
          contentPadding: EdgeInsets.zero,
          controlAffinity: ListTileControlAffinity.leading,
          value: _seguro,
          title: const Text('Entiendo que se borra todo y no se puede deshacer'),
          onChanged: (v) => setState(() => _seguro = v ?? false),
        ),
        FilledButton(
          style: FilledButton.styleFrom(backgroundColor: Paleta.noCubierto),
          onPressed: () async {
            if (!_seguro || (conClave && _clave.text.isEmpty)) {
              return mostrarError(context, ErrorApi(conClave ? 'Escribe tu contraseña y marca la casilla.' : 'Marca la casilla para borrar todo.'));
            }
            try {
              await e.borrarCuenta(_clave.text);
              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Tu cuenta y todo lo guardado se borraron.')));
              }
            } catch (err) {
              if (context.mounted) mostrarError(context, err);
            }
          },
          child: const Text('Borrar mi cuenta y todo'),
        ),
      ]),
    );
  }
}

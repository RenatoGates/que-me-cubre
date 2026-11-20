import 'dart:async';
import 'dart:ui';

import 'package:material_ui/material_ui.dart';
import 'package:url_launcher/url_launcher.dart';

import 'comun.dart';
import 'compras.dart';
import 'estado.dart';
import 'pantalla_cuenta.dart';
import 'pantalla_mapa.dart';
import 'pantalla_poliza.dart';
import 'telemetria.dart';
import 'tema.dart';
import 'textos.dart';

Future<void> main() async {
  runZonedGuarded(() async {
    WidgetsFlutterBinding.ensureInitialized();
    await Telemetria.iniciar();
    // Solo en una compilación de prueba (--dart-define=QMC_PRUEBA_CRASHLYTICS=true): un error cuyo
    // mensaje trae texto como el de una póliza, para ver en la consola de Firebase que no llega.
    if (const bool.fromEnvironment('QMC_PRUEBA_CRASHLYTICS')) {
      Telemetria.registrar(const FormatException('PRUEBA-CRASHLYTICS Tarapoto ana.secreta@ejemplo.pe ¿me cubre la maleta?'),
          StackTrace.current);
    }
    FlutterError.onError = Telemetria.errorDeFlutter;
    PlatformDispatcher.instance.onError = (error, pila) {
      Telemetria.registrar(error, pila, fatal: true);
      return true;
    };
    runApp(const QueCubreApp());
  }, (error, pila) => Telemetria.registrar(error, pila, fatal: true));
}

class QueCubreApp extends StatefulWidget {
  const QueCubreApp({super.key});

  @override
  State<QueCubreApp> createState() => _QueCubreAppState();
}

class _QueCubreAppState extends State<QueCubreApp> {
  final _estado = Estado();
  late final _compras = Compras(_estado);
  late Future<void> _arranque = _iniciar();

  Future<void> _iniciar() async {
    await _estado.iniciar();
    if (!_estado.actualizacionObligatoria) _compras.iniciar();
  }

  @override
  void dispose() {
    _compras.cerrar();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => EstadoScope(
        estado: _estado,
        child: MaterialApp(
          title: Textos.nombre,
          debugShowCheckedModeBanner: false,
          theme: temaQueCubre(),
          home: FutureBuilder<void>(
            future: _arranque,
            builder: (context, s) {
              if (s.connectionState != ConnectionState.done) return const _Bienvenida();
              if (s.hasError) return _SinConexion(alReintentar: () => setState(() => _arranque = _iniciar()));
              if (_estado.actualizacionObligatoria) return const PantallaActualizar();
              return Principal(compras: _compras);
            },
          ),
        ),
      );
}

class _Bienvenida extends StatelessWidget {
  const _Bienvenida();

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              ClipRRect(borderRadius: BorderRadius.circular(28),
                  child: Image.asset('assets/icono_512.png', width: 128, height: 128, semanticLabel: 'Logo de ¿Qué Cubre?')),
              const SizedBox(height: 24),
              Text(Textos.nombre, style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 24),
              const Cargando('Preparando todo. La primera vez puede tardar cerca de un minuto…'),
            ]),
          ),
        ),
      );
}

class _SinConexion extends StatelessWidget {
  const _SinConexion({required this.alReintentar});
  final VoidCallback alReintentar;

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.wifi_off_rounded, size: 64, color: Paleta.textoSecundario),
              const SizedBox(height: 16),
              const Text(Textos.sinConexion, textAlign: TextAlign.center, style: TextStyle(fontSize: 17)),
              const SizedBox(height: 20),
              FilledButton.icon(onPressed: alReintentar, icon: const Icon(Icons.refresh), label: const Text('Volver a intentar')),
            ]),
          ),
        ),
      );
}

/// Si la versión instalada quedó por debajo de la mínima que acepta el backend, no se puede seguir.
class PantallaActualizar extends StatelessWidget {
  const PantallaActualizar({super.key});

  @override
  Widget build(BuildContext context) => Scaffold(
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Icon(Icons.system_update_rounded, size: 72, color: Paleta.accion),
              const SizedBox(height: 20),
              Semantics(header: true, child: Text('Actualiza ¿Qué Cubre?', style: Theme.of(context).textTheme.headlineMedium)),
              const SizedBox(height: 12),
              const Text('Esta versión ya no funciona. Instala la última desde Google Play para seguir.', textAlign: TextAlign.center,
                  style: TextStyle(fontSize: 17)),
              const SizedBox(height: 24),
              FilledButton.icon(
                onPressed: () => launchUrl(Uri.parse('market://details?id=com.renatogates.quecubre'), mode: LaunchMode.externalApplication),
                icon: const Icon(Icons.shop_rounded),
                label: const Text('Actualizar'),
              ),
            ]),
          ),
        ),
      );
}

class Principal extends StatelessWidget {
  const Principal({super.key, required this.compras});
  final Compras compras;

  @override
  Widget build(BuildContext context) {
    final e = EstadoScope.of(context);
    final paginas = [const PantallaPoliza(), const PantallaMapa(), PantallaCuenta(compras: compras)];
    return Scaffold(
      body: IndexedStack(index: e.pestana, children: paginas),
      bottomNavigationBar: NavigationBar(
        selectedIndex: e.pestana,
        onDestinationSelected: e.irA,
        destinations: const [
          NavigationDestination(icon: Icon(Icons.description_outlined), selectedIcon: Icon(Icons.description_rounded), label: 'Tu póliza'),
          NavigationDestination(icon: Icon(Icons.local_hospital_outlined), selectedIcon: Icon(Icons.local_hospital_rounded), label: 'Cerca de ti'),
          NavigationDestination(icon: Icon(Icons.person_outline_rounded), selectedIcon: Icon(Icons.person_rounded), label: 'Mi cuenta'),
        ],
      ),
    );
  }
}

import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:material_ui/material_ui.dart';
import 'package:pdfx/pdfx.dart';

import 'api.dart';
import 'comun.dart';
import 'estado.dart';
import 'resultado.dart';
import 'tema.dart';

/// Abre el PDF de la póliza en la página de una cita. El archivo es el que la persona tiene en su
/// teléfono: nunca se sube ni se guarda en el servidor. Si es una póliza guardada (en la cuenta
/// está solo su texto), se le pide elegir su PDF una vez y se guarda una copia solo en el teléfono.
Future<void> abrirEnLaPagina(BuildContext context, PolizaActual poliza, int pagina) async {
  final e = EstadoScope.of(context);
  List<(String, Uint8List)>? archivos;
  try {
    archivos = await e.pdfDe(poliza);
  } catch (err) {
    if (context.mounted) mostrarError(context, err);
    return;
  }
  if (archivos == null) {
    if (!context.mounted) return;
    final elegir = await showDialog<bool>(
      context: context,
      builder: (context) => AlertDialog(
        icon: const Icon(Icons.picture_as_pdf_rounded, color: Paleta.accion),
        title: const Text('Elige el PDF de tu póliza'),
        content: const Text('Tu cuenta guarda el texto de la póliza, no el archivo. Elígelo una vez y desde ahora se abre en la página '
            'de cada cita. Se queda solo en tu teléfono.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Ahora no')),
          FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('Elegir mi PDF')),
        ],
      ),
    );
    if (elegir != true) return;
    final elegidos = await FilePicker.pickFiles(type: FileType.custom, allowedExtensions: ['pdf']);
    if (elegidos.isEmpty) return;
    final pares = [for (final a in elegidos) (a.name, await a.readAsBytes())];
    if (!await e.recordarPdf(poliza, pares)) {
      if (context.mounted) mostrarError(context, ErrorApi('Ese PDF no es el de esta póliza. Elige el mismo archivo que subiste.'));
      return;
    }
    archivos = pares;
  }
  final (i, enArchivo) = ubicar(poliza.archivos, pagina);
  final (nombre, datos) = archivos[i.clamp(0, archivos.length - 1)];
  if (!context.mounted) return;
  await Navigator.of(context).push(MaterialPageRoute<void>(builder: (_) => PantallaPdf(nombre: nombre, datos: datos, pagina: enArchivo)));
}

class PantallaPdf extends StatefulWidget {
  const PantallaPdf({super.key, required this.nombre, required this.datos, required this.pagina});
  final String nombre;
  final Uint8List datos;
  final int pagina;

  @override
  State<PantallaPdf> createState() => _PantallaPdfState();
}

class _PantallaPdfState extends State<PantallaPdf> {
  late final _control = PdfControllerPinch(document: PdfDocument.openData(widget.datos), initialPage: widget.pagina);

  @override
  void dispose() {
    _control.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Scaffold(
        appBar: AppBar(title: Text('Página ${widget.pagina} · ${widget.nombre}', overflow: TextOverflow.ellipsis)),
        body: ColoredBox(color: Paleta.citaFondo, child: PdfViewPinch(controller: _control)),
      );
}

import 'package:material_ui/material_ui.dart';

/// La paleta clara (crema y azul) decidida para ¿Qué Cubre?. Los contrastes están medidos en
/// pruebas/medir_contraste.py. «Con límites» se oscureció de #B06A00 a #A36200: el original no
/// llegaba a 4,5:1 sobre el fondo crema.
class Paleta {
  static const fondo = Color(0xFFFBF7F2);
  static const superficie = Color(0xFFFFFFFF); // tarjetas
  static const borde = Color(0xFFE8DFD4);
  static const texto = Color(0xFF2E2620);
  static const textoSecundario = Color(0xFF7A6E62);
  static const accion = Color(0xFF2D6BE5); // botón primario, con texto blanco
  static const sobreAccion = Color(0xFFFFFFFF);
  static const cubierto = Color(0xFF1E7A4D);
  static const noCubierto = Color(0xFFC0392B); // reservado para «no cubre»
  static const parcial = Color(0xFFA36200); // «con límites»
  static const citaFondo = Color(0xFFF3EDE4); // el bloque del texto citado, con barra lateral en `accion`
}

ThemeData temaQueCubre() {
  const esquema = ColorScheme(
    brightness: Brightness.light,
    primary: Paleta.accion,
    onPrimary: Paleta.sobreAccion,
    secondary: Paleta.accion,
    onSecondary: Paleta.sobreAccion,
    error: Paleta.parcial, // el rojo queda solo para «no cubre»
    onError: Paleta.sobreAccion,
    surface: Paleta.superficie,
    onSurface: Paleta.texto,
    onSurfaceVariant: Paleta.textoSecundario,
    outline: Paleta.borde,
  );
  final base = ThemeData(colorScheme: esquema, useMaterial3: true, scaffoldBackgroundColor: Paleta.fondo);
  final texto = base.textTheme.apply(bodyColor: Paleta.texto, displayColor: Paleta.texto);
  return base.copyWith(
    textTheme: texto.copyWith(
      headlineMedium: texto.headlineMedium?.copyWith(fontWeight: FontWeight.w800, letterSpacing: -0.5),
      titleLarge: texto.titleLarge?.copyWith(fontWeight: FontWeight.w700),
      titleMedium: texto.titleMedium?.copyWith(fontWeight: FontWeight.w700),
      bodyLarge: texto.bodyLarge?.copyWith(height: 1.5),
      bodyMedium: texto.bodyMedium?.copyWith(height: 1.5),
    ),
    appBarTheme: const AppBarTheme(backgroundColor: Paleta.fondo, foregroundColor: Paleta.texto, elevation: 0, centerTitle: false),
    cardTheme: CardThemeData(
      color: Paleta.superficie,
      elevation: 0,
      margin: EdgeInsets.zero,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20), side: const BorderSide(color: Paleta.borde)),
    ),
    filledButtonTheme: FilledButtonThemeData(
      style: FilledButton.styleFrom(
        backgroundColor: Paleta.accion,
        foregroundColor: Paleta.sobreAccion,
        minimumSize: const Size(48, 52),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: Paleta.accion,
        backgroundColor: Paleta.superficie,
        minimumSize: const Size(48, 48),
        side: const BorderSide(color: Paleta.accion, width: 1.4),
        textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 15),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
    textButtonTheme: TextButtonThemeData(
      style: TextButton.styleFrom(foregroundColor: Paleta.accion, minimumSize: const Size(48, 48),
          textStyle: const TextStyle(fontWeight: FontWeight.w700)),
    ),
    inputDecorationTheme: InputDecorationTheme(
      filled: true,
      fillColor: Paleta.superficie,
      labelStyle: const TextStyle(color: Paleta.textoSecundario),
      hintStyle: const TextStyle(color: Paleta.textoSecundario),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Paleta.borde)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Paleta.borde)),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Paleta.accion, width: 2)),
    ),
    chipTheme: base.chipTheme.copyWith(
      backgroundColor: Paleta.superficie,
      labelStyle: const TextStyle(color: Paleta.texto, fontWeight: FontWeight.w600),
      side: const BorderSide(color: Paleta.borde),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: Paleta.superficie,
      indicatorColor: Paleta.accion,
      labelTextStyle: WidgetStateProperty.all(const TextStyle(color: Paleta.texto, fontWeight: FontWeight.w600, fontSize: 13)),
      iconTheme: WidgetStateProperty.resolveWith((estados) =>
          IconThemeData(color: estados.contains(WidgetState.selected) ? Paleta.sobreAccion : Paleta.textoSecundario)),
    ),
    dividerTheme: const DividerThemeData(color: Paleta.borde, space: 1),
    snackBarTheme: const SnackBarThemeData(backgroundColor: Paleta.texto, contentTextStyle: TextStyle(color: Paleta.superficie)),
    dialogTheme: const DialogThemeData(backgroundColor: Paleta.superficie),
    checkboxTheme: CheckboxThemeData(
      side: const BorderSide(color: Paleta.textoSecundario, width: 2),
      fillColor: WidgetStateProperty.resolveWith((e) => e.contains(WidgetState.selected) ? Paleta.accion : Colors.transparent),
      checkColor: WidgetStateProperty.all(Paleta.sobreAccion),
    ),
    switchTheme: SwitchThemeData(
      thumbColor: WidgetStateProperty.resolveWith((e) => e.contains(WidgetState.selected) ? Paleta.sobreAccion : Paleta.textoSecundario),
      trackColor: WidgetStateProperty.resolveWith((e) => e.contains(WidgetState.selected) ? Paleta.accion : Paleta.borde),
    ),
  );
}

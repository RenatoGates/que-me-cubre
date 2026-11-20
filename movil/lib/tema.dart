import 'package:material_ui/material_ui.dart';

/// La paleta decidida para ¿Qué Cubre?. El coral queda reservado para "no cubierto".
/// Los contrastes están medidos en pruebas/medir_contraste.py.
class Paleta {
  static const fondo = Color(0xFF0F1729);
  static const superficie = Color(0xFF1A2338);
  static const texto = Color(0xFFE8EDF7);
  static const textoSecundario = Color(0xFF9AA7BF);
  static const accion = Color(0xFF3DBFB0);
  static const cubierto = Color(0xFF35C77A);
  static const noCubierto = Color(0xFFFF6B5A);
  static const parcial = Color(0xFFF5B544);
  static const borde = Color(0xFF2B3753); // solo líneas divisorias, nunca texto
}

ThemeData temaQueCubre() {
  const esquema = ColorScheme(
    brightness: Brightness.dark,
    primary: Paleta.accion,
    onPrimary: Paleta.fondo,
    secondary: Paleta.accion,
    onSecondary: Paleta.fondo,
    error: Paleta.parcial, // el coral queda solo para «no cubre»
    onError: Paleta.fondo,
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
      bodyLarge: texto.bodyLarge?.copyWith(height: 1.45),
      bodyMedium: texto.bodyMedium?.copyWith(height: 1.45),
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
        foregroundColor: Paleta.fondo,
        minimumSize: const Size(48, 52),
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
        textStyle: const TextStyle(fontWeight: FontWeight.w700, fontSize: 16),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
      ),
    ),
    outlinedButtonTheme: OutlinedButtonThemeData(
      style: OutlinedButton.styleFrom(
        foregroundColor: Paleta.accion,
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
      fillColor: Paleta.fondo,
      labelStyle: const TextStyle(color: Paleta.textoSecundario),
      hintStyle: const TextStyle(color: Paleta.textoSecundario),
      border: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Paleta.borde)),
      enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Paleta.borde)),
      focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(14), borderSide: const BorderSide(color: Paleta.accion, width: 2)),
    ),
    chipTheme: base.chipTheme.copyWith(
      backgroundColor: Paleta.fondo,
      selectedColor: Paleta.accion,
      labelStyle: const TextStyle(color: Paleta.texto, fontWeight: FontWeight.w600),
      secondaryLabelStyle: const TextStyle(color: Paleta.fondo, fontWeight: FontWeight.w700),
      side: const BorderSide(color: Paleta.borde),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
    ),
    navigationBarTheme: NavigationBarThemeData(
      backgroundColor: Paleta.superficie,
      indicatorColor: Paleta.accion,
      labelTextStyle: WidgetStateProperty.all(const TextStyle(color: Paleta.texto, fontWeight: FontWeight.w600, fontSize: 13)),
      iconTheme: WidgetStateProperty.resolveWith((estados) =>
          IconThemeData(color: estados.contains(WidgetState.selected) ? Paleta.fondo : Paleta.textoSecundario)),
    ),
    dividerTheme: const DividerThemeData(color: Paleta.borde, space: 1),
    snackBarTheme: const SnackBarThemeData(backgroundColor: Paleta.texto, contentTextStyle: TextStyle(color: Paleta.fondo)),
    checkboxTheme: CheckboxThemeData(
      side: const BorderSide(color: Paleta.textoSecundario, width: 2),
      fillColor: WidgetStateProperty.resolveWith((e) => e.contains(WidgetState.selected) ? Paleta.accion : Colors.transparent),
      checkColor: WidgetStateProperty.all(Paleta.fondo),
    ),
  );
}

import 'package:flutter/material.dart';

/// Parse a "#RRGGBB" string into a Color, falling back to grey.
Color colorFromHex(String hex) {
  var h = hex.replaceAll('#', '').trim();
  if (h.length == 6) h = 'FF$h';
  final value = int.tryParse(h, radix: 16);
  return value == null ? const Color(0xFF757575) : Color(value);
}

class SatyaTheme {
  static const seed = Color(0xFF0F6E3F); // trustworthy green

  static ThemeData light() {
    final scheme = ColorScheme.fromSeed(seedColor: seed);
    return ThemeData(
      colorScheme: scheme,
      useMaterial3: true,
      appBarTheme: const AppBarTheme(centerTitle: false),
    );
  }
}

import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import 'models.dart';

/// Talks to the Satya backend. The base URL is configurable in Settings so the
/// same build works against a local server or the deployed one.
class ApiClient {
  /// Default for the Android emulator hitting a backend on the host machine.
  static const String defaultBaseUrl = 'http://10.0.2.2:8000';
  static const _baseUrlKey = 'satya_base_url';

  String _baseUrl;
  ApiClient._(this._baseUrl);

  static Future<ApiClient> create() async {
    final prefs = await SharedPreferences.getInstance();
    return ApiClient._(prefs.getString(_baseUrlKey) ?? defaultBaseUrl);
  }

  String get baseUrl => _baseUrl;

  Future<void> setBaseUrl(String url) async {
    _baseUrl = url.trim();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_baseUrlKey, _baseUrl);
  }

  Future<FactCheckResult> checkText(String text, String lang) async {
    final r = await http.post(
      Uri.parse('$_baseUrl/v1/check/text'),
      headers: {'content-type': 'application/json'},
      body: jsonEncode({'text': text, 'lang': lang}),
    );
    return _parse(r);
  }

  Future<FactCheckResult> checkUrl(String url, String lang) async {
    final r = await http.post(
      Uri.parse('$_baseUrl/v1/check/url'),
      headers: {'content-type': 'application/json'},
      body: jsonEncode({'url': url, 'lang': lang}),
    );
    return _parse(r);
  }

  Future<FactCheckResult> checkImage(File image, String lang) async {
    final req = http.MultipartRequest('POST', Uri.parse('$_baseUrl/v1/check/image'))
      ..fields['lang'] = lang
      ..files.add(await http.MultipartFile.fromPath('file', image.path));
    final streamed = await req.send();
    final r = await http.Response.fromStream(streamed);
    return _parse(r);
  }

  FactCheckResult _parse(http.Response r) {
    final body = jsonDecode(utf8.decode(r.bodyBytes)) as Map<String, dynamic>;
    if (r.statusCode == 200) {
      return FactCheckResult.fromJson(body);
    }
    throw ApiException((body['detail'] ?? 'Something went wrong').toString(), r.statusCode);
  }
}

class ApiException implements Exception {
  final String message;
  final int statusCode;
  ApiException(this.message, this.statusCode);
  @override
  String toString() => message;
}

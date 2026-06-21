import 'dart:convert';

/// A source citation returned with a verdict.
class Source {
  final String title;
  final String url;
  final String publisher;

  Source({required this.title, required this.url, required this.publisher});

  factory Source.fromJson(Map<String, dynamic> j) => Source(
        title: (j['title'] ?? '') as String,
        url: (j['url'] ?? '') as String,
        publisher: (j['publisher'] ?? '') as String,
      );

  Map<String, dynamic> toJson() =>
      {'title': title, 'url': url, 'publisher': publisher};
}

/// The structured result of a fact-check, as returned by the backend.
class FactCheckResult {
  final String verdict; // TRUE | MOSTLY_TRUE | MISLEADING | FALSE | UNVERIFIABLE
  final String labelEn;
  final String labelHi;
  final String colorHex; // e.g. "#D32F2F"
  final String confidence;
  final String claim;
  final String summary;
  final List<String> evidence;
  final List<Source> sources;
  final bool cached;
  final DateTime checkedAt;

  FactCheckResult({
    required this.verdict,
    required this.labelEn,
    required this.labelHi,
    required this.colorHex,
    required this.confidence,
    required this.claim,
    required this.summary,
    required this.evidence,
    required this.sources,
    required this.cached,
    required this.checkedAt,
  });

  factory FactCheckResult.fromJson(Map<String, dynamic> j) => FactCheckResult(
        verdict: (j['verdict'] ?? 'UNVERIFIABLE') as String,
        labelEn: (j['verdict_label_en'] ?? '') as String,
        labelHi: (j['verdict_label_hi'] ?? '') as String,
        colorHex: (j['verdict_color'] ?? '#757575') as String,
        confidence: (j['confidence'] ?? 'low') as String,
        claim: (j['claim'] ?? '') as String,
        summary: (j['summary'] ?? '') as String,
        evidence:
            ((j['evidence'] ?? []) as List).map((e) => e.toString()).toList(),
        sources: ((j['sources'] ?? []) as List)
            .map((s) => Source.fromJson(s as Map<String, dynamic>))
            .toList(),
        cached: (j['cached'] ?? false) as bool,
        checkedAt: DateTime.now(),
      );

  Map<String, dynamic> toJson() => {
        'verdict': verdict,
        'verdict_label_en': labelEn,
        'verdict_label_hi': labelHi,
        'verdict_color': colorHex,
        'confidence': confidence,
        'claim': claim,
        'summary': summary,
        'evidence': evidence,
        'sources': sources.map((s) => s.toJson()).toList(),
        'cached': cached,
        'checked_at': checkedAt.toIso8601String(),
      };

  String encode() => jsonEncode(toJson());

  /// Plain-text version a user can re-forward to fight the misinformation.
  String shareText() {
    final src = sources.isNotEmpty ? '\n\nSources: ${sources.map((s) => s.url).join(', ')}' : '';
    return 'Satya fact-check: $labelEn\n\n$claim\n\n$summary$src\n\n— Checked with Satya';
  }
}

import 'package:flutter/material.dart';
import 'package:share_plus/share_plus.dart';
import 'package:url_launcher/url_launcher.dart';

import '../core/models.dart';
import '../core/theme.dart';

class ResultScreen extends StatelessWidget {
  final FactCheckResult result;
  const ResultScreen({super.key, required this.result});

  @override
  Widget build(BuildContext context) {
    final color = colorFromHex(result.colorHex);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Result'),
        actions: [
          IconButton(
            icon: const Icon(Icons.share),
            onPressed: () => Share.share(result.shareText()),
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _verdictBadge(context, color),
          const SizedBox(height: 16),
          _section(context, 'Claim', result.claim),
          _section(context, 'What we found', result.summary),
          if (result.evidence.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text('Evidence', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            ...result.evidence.map((e) => Padding(
                  padding: const EdgeInsets.symmetric(vertical: 2),
                  child: Text('•  $e'),
                )),
          ],
          if (result.sources.isNotEmpty) ...[
            const SizedBox(height: 16),
            Text('Sources', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 4),
            ...result.sources.map((s) => _sourceTile(context, s)),
          ],
          const SizedBox(height: 24),
          Text(
            'Verdict is based on evidence available now. Always check the linked '
            'sources yourself before sharing.',
            style: Theme.of(context).textTheme.bodySmall,
          ),
        ],
      ),
    );
  }

  Widget _verdictBadge(BuildContext context, Color color) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.12),
        border: Border.all(color: color, width: 2),
        borderRadius: BorderRadius.circular(12),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            result.labelEn,
            style: Theme.of(context)
                .textTheme
                .headlineSmall
                ?.copyWith(color: color, fontWeight: FontWeight.bold),
          ),
          if (result.labelHi.isNotEmpty)
            Text(result.labelHi, style: TextStyle(color: color, fontSize: 18)),
          const SizedBox(height: 6),
          Row(
            children: [
              Chip(
                label: Text('Confidence: ${result.confidence}'),
                visualDensity: VisualDensity.compact,
              ),
              if (result.cached) ...[
                const SizedBox(width: 8),
                const Chip(
                  label: Text('Already checked'),
                  visualDensity: VisualDensity.compact,
                ),
              ],
            ],
          ),
        ],
      ),
    );
  }

  Widget _section(BuildContext context, String title, String body) {
    if (body.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 4),
          Text(body, style: Theme.of(context).textTheme.bodyLarge),
        ],
      ),
    );
  }

  Widget _sourceTile(BuildContext context, Source s) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      leading: const Icon(Icons.link),
      title: Text(s.title.isNotEmpty ? s.title : s.url),
      subtitle: Text(s.publisher),
      onTap: () async {
        final uri = Uri.tryParse(s.url);
        if (uri != null && await canLaunchUrl(uri)) {
          await launchUrl(uri, mode: LaunchMode.externalApplication);
        }
      },
    );
  }
}

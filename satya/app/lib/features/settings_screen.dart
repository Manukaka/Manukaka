import 'package:flutter/material.dart';

import '../core/api_client.dart';

class SettingsScreen extends StatefulWidget {
  final ApiClient api;
  const SettingsScreen({super.key, required this.api});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late final TextEditingController _url =
      TextEditingController(text: widget.api.baseUrl);

  Future<void> _save() async {
    await widget.api.setBaseUrl(_url.text);
    if (!mounted) return;
    ScaffoldMessenger.of(context)
        .showSnackBar(const SnackBar(content: Text('Saved')));
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Settings')),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Backend server', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          TextField(
            controller: _url,
            decoration: const InputDecoration(
              border: OutlineInputBorder(),
              helperText: 'e.g. http://10.0.2.2:8000 (emulator) or your deployed URL',
            ),
          ),
          const SizedBox(height: 12),
          FilledButton(onPressed: _save, child: const Text('Save')),
          const SizedBox(height: 24),
          const Text(
            'Satya checks forwards, screenshots, and links against trusted '
            'Indian fact-checkers. Checks are stored only on this device.',
          ),
        ],
      ),
    );
  }

  @override
  void dispose() {
    _url.dispose();
    super.dispose();
  }
}

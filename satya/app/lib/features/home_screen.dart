import 'dart:io';

import 'package:flutter/material.dart';
import 'package:image_picker/image_picker.dart';

import '../core/api_client.dart';
import '../core/history_store.dart';
import '../core/models.dart';
import 'history_screen.dart';
import 'result_screen.dart';
import 'settings_screen.dart';

class HomeScreen extends StatefulWidget {
  final ApiClient api;
  final HistoryStore history;
  const HomeScreen({super.key, required this.api, required this.history});

  @override
  State<HomeScreen> createState() => HomeScreenState();
}

class HomeScreenState extends State<HomeScreen> {
  final _controller = TextEditingController();
  final _picker = ImagePicker();
  String _lang = 'hinglish';
  bool _busy = false;

  // ---- entry points used by the share-sheet handler in main.dart ----
  void checkSharedText(String text) {
    _controller.text = text;
    _run(() => widget.api.checkText(text, _lang));
  }

  void checkSharedImage(File image) => _run(() => widget.api.checkImage(image, _lang));

  // ---- user-driven actions ----
  Future<void> _checkTyped() async {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    final isUrl = RegExp(r'^https?://').hasMatch(text);
    await _run(() => isUrl ? widget.api.checkUrl(text, _lang) : widget.api.checkText(text, _lang));
  }

  Future<void> _pickImage(ImageSource source) async {
    final picked = await _picker.pickImage(source: source, imageQuality: 85);
    if (picked == null) return;
    await _run(() => widget.api.checkImage(File(picked.path), _lang));
  }

  Future<void> _run(Future<FactCheckResult> Function() action) async {
    if (_busy) return;
    setState(() => _busy = true);
    try {
      final result = await action();
      await widget.history.add(result);
      if (!mounted) return;
      Navigator.of(context).push(
        MaterialPageRoute(builder: (_) => ResultScreen(result: result)),
      );
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(e.toString())),
      );
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Satya · सत्य'),
        actions: [
          IconButton(
            icon: const Icon(Icons.history),
            tooltip: 'History',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => HistoryScreen(history: widget.history)),
            ),
          ),
          IconButton(
            icon: const Icon(Icons.settings),
            tooltip: 'Settings',
            onPressed: () => Navigator.of(context).push(
              MaterialPageRoute(builder: (_) => SettingsScreen(api: widget.api)),
            ),
          ),
        ],
      ),
      body: SafeArea(
        child: AbsorbPointer(
          absorbing: _busy,
          child: Opacity(
            opacity: _busy ? 0.5 : 1,
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text(
                  'Paste a WhatsApp forward, news, or link — get the truth.',
                  style: Theme.of(context).textTheme.titleMedium,
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: _controller,
                  maxLines: 6,
                  decoration: const InputDecoration(
                    hintText: 'Paste the message or link here…',
                    border: OutlineInputBorder(),
                  ),
                ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    const Text('Answer in: '),
                    const SizedBox(width: 8),
                    DropdownButton<String>(
                      value: _lang,
                      items: const [
                        DropdownMenuItem(value: 'hinglish', child: Text('Hinglish')),
                        DropdownMenuItem(value: 'hi', child: Text('हिंदी')),
                        DropdownMenuItem(value: 'en', child: Text('English')),
                      ],
                      onChanged: (v) => setState(() => _lang = v ?? 'hinglish'),
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                FilledButton.icon(
                  onPressed: _checkTyped,
                  icon: const Icon(Icons.search),
                  label: const Text('Check'),
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () => _pickImage(ImageSource.gallery),
                        icon: const Icon(Icons.image),
                        label: const Text('Screenshot'),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: () => _pickImage(ImageSource.camera),
                        icon: const Icon(Icons.camera_alt),
                        label: const Text('Camera'),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 24),
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(12),
                    child: Text(
                      'Tip: in WhatsApp, tap Share on any message or image and '
                      'choose Satya to check it instantly.',
                      style: Theme.of(context).textTheme.bodySmall,
                    ),
                  ),
                ),
                if (_busy) ...[
                  const SizedBox(height: 24),
                  const Center(child: CircularProgressIndicator()),
                  const SizedBox(height: 8),
                  const Center(child: Text('Researching across trusted sources…')),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
}

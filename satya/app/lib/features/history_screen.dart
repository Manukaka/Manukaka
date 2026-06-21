import 'package:flutter/material.dart';

import '../core/history_store.dart';
import '../core/models.dart';
import '../core/theme.dart';
import 'result_screen.dart';

class HistoryScreen extends StatefulWidget {
  final HistoryStore history;
  const HistoryScreen({super.key, required this.history});

  @override
  State<HistoryScreen> createState() => _HistoryScreenState();
}

class _HistoryScreenState extends State<HistoryScreen> {
  late Future<List<FactCheckResult>> _future;

  @override
  void initState() {
    super.initState();
    _future = widget.history.load();
  }

  Future<void> _clear() async {
    await widget.history.clear();
    setState(() => _future = widget.history.load());
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('History'),
        actions: [
          IconButton(icon: const Icon(Icons.delete_outline), onPressed: _clear),
        ],
      ),
      body: FutureBuilder<List<FactCheckResult>>(
        future: _future,
        builder: (context, snap) {
          if (!snap.hasData) {
            return const Center(child: CircularProgressIndicator());
          }
          final items = snap.data!;
          if (items.isEmpty) {
            return const Center(child: Text('No checks yet.'));
          }
          return ListView.separated(
            itemCount: items.length,
            separatorBuilder: (_, __) => const Divider(height: 1),
            itemBuilder: (context, i) {
              final r = items[i];
              return ListTile(
                leading: CircleAvatar(backgroundColor: colorFromHex(r.colorHex)),
                title: Text(r.claim.isNotEmpty ? r.claim : r.summary,
                    maxLines: 2, overflow: TextOverflow.ellipsis),
                subtitle: Text(r.labelEn),
                onTap: () => Navigator.of(context).push(
                  MaterialPageRoute(builder: (_) => ResultScreen(result: r)),
                ),
              );
            },
          );
        },
      ),
    );
  }
}

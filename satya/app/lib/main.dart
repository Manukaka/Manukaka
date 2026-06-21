import 'dart:async';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:receive_sharing_intent/receive_sharing_intent.dart';

import 'core/api_client.dart';
import 'core/history_store.dart';
import 'core/theme.dart';
import 'features/home_screen.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final api = await ApiClient.create();
  runApp(SatyaApp(api: api, history: HistoryStore()));
}

class SatyaApp extends StatefulWidget {
  final ApiClient api;
  final HistoryStore history;
  const SatyaApp({super.key, required this.api, required this.history});

  @override
  State<SatyaApp> createState() => _SatyaAppState();
}

class _SatyaAppState extends State<SatyaApp> {
  final _homeKey = GlobalKey<HomeScreenState>();
  StreamSubscription<List<SharedMediaFile>>? _sub;

  @override
  void initState() {
    super.initState();
    // Content shared into Satya while it is already running.
    _sub = ReceiveSharingIntent.instance.getMediaStream().listen(_handleShared);
    // Content that launched the app via the share sheet.
    ReceiveSharingIntent.instance.getInitialMedia().then((files) {
      _handleShared(files);
      ReceiveSharingIntent.instance.reset();
    });
  }

  void _handleShared(List<SharedMediaFile> files) {
    if (files.isEmpty) return;
    final f = files.first;
    final home = _homeKey.currentState;
    if (home == null) return;
    switch (f.type) {
      case SharedMediaType.text:
      case SharedMediaType.url:
        home.checkSharedText(f.path);
        break;
      case SharedMediaType.image:
        home.checkSharedImage(File(f.path));
        break;
      default:
        break;
    }
  }

  @override
  void dispose() {
    _sub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'Satya',
      debugShowCheckedModeBanner: false,
      theme: SatyaTheme.light(),
      home: HomeScreen(key: _homeKey, api: widget.api, history: widget.history),
    );
  }
}

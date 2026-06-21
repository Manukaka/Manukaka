# Satya app (Flutter)

Android-first fact-check app. Core flow: **share a WhatsApp forward (text or
screenshot), or paste a link → get a clear, colour-coded verdict with trusted
Indian sources, in your language.**

## Project scaffolding

This folder contains the Satya source (`lib/`) plus the custom Android manifest.
To get a buildable project, generate the platform scaffolding once and keep
these files:

```bash
cd satya/app
flutter create .          # generates android/ ios/ etc. — keep our lib/ and pubspec.yaml
flutter pub get
```

When prompted, keep the provided `lib/`, `pubspec.yaml`, and
`android/app/src/main/AndroidManifest.xml` (the manifest adds the
share-sheet intent filters and camera/internet permissions). Set the Android
`applicationId` to `com.satya.app` in `android/app/build.gradle`.

## Run

1. Start the backend (see `../backend/README.md`).
2. Point the app at it: default base URL is `http://10.0.2.2:8000` (Android
   emulator → host machine). Change it in **Settings** for a real device or
   deployed backend.
3. `flutter run`.

## Checks

```bash
flutter analyze
flutter build apk --debug
```

## Features in this MVP

- Paste text or a link → fact-check (auto-detects URLs).
- Pick a **screenshot** from the gallery or shoot one with the **camera**.
- **Share into Satya** from WhatsApp/browser (text, link, or image).
- Colour-coded verdict (सच / झूठ / भ्रामक / …) with confidence, plain-language
  explanation, evidence, and tappable sources.
- Language toggle: Hinglish / हिंदी / English.
- Local **history** of checks (device-only, no account).
- **Share result** to re-forward the correction.

## Structure

```
lib/
  main.dart                 app + share-intent wiring
  core/
    api_client.dart         backend calls + base-URL setting
    models.dart             FactCheckResult, Source
    theme.dart              theme + hex→Color
    history_store.dart      local history (shared_preferences)
  features/
    home_screen.dart        paste box, buttons, language
    result_screen.dart      verdict badge, evidence, sources, share
    history_screen.dart     past checks
    settings_screen.dart    backend URL
```

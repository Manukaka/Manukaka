# Manu Mobile — voice-driven agentic Android app

Manu listens to your spoken instruction (Marathi / Hindi / English), looks at
whatever is on your screen, and drives your phone for you — opening apps, tapping,
typing, scrolling, sending messages, searching the web, and reading the screen back
to you. The "thinking" happens in the [backend](../backend) (which holds the Claude
API key); the phone only observes the screen and performs actions.

> **Reality check:** because Manu controls other apps via Android's Accessibility
> API, it is distributed as a **signed APK you sideload**, not a public Play Store
> listing (Google's policy forbids general phone-automation there). That's exactly
> the developer-mode / self-trial path you're on. Reliability is strong on common
> flows and improves each phase; risky actions (send / call / pay / delete) always
> ask for a spoken "yes" first.

## How it works
```
You speak ─► SpeechRecognizer ─► goal
                                   │
  ┌───── AgentLoop (on device) ◄──┘
  │  observe screen (AccessibilityService reads the node tree)
  │  ─► POST /agent/step to backend ─► Claude picks ONE action
  │  ◄─ open_app / tap / type / swipe / read_aloud / ask_user / done
  │  execute it, then observe again … until done
  └─► TextToSpeech speaks replies in your language
```

## Build & install on your Samsung A55

### 1. Prerequisites
- Android Studio (Ladybug or newer) **or** JDK 17 + the Android SDK on the command line.
- The [backend](../backend) running and reachable from the phone (note its URL,
  e.g. `https://your-host` or your laptop's LAN IP like `http://192.168.1.5:8080`).

### 2. Build the debug APK
In Android Studio: open the `mobile/` folder, let it sync, then **Run**.

Or from the command line:
```bash
cd mobile
# point the app at your backend (LAN IP or public URL):
./gradlew assembleDebug -PmanuBackendUrl="http://192.168.1.5:8080"
# APK lands at app/build/outputs/apk/debug/app-debug.apk
```
If your backend requires the shared secret, also pass
`-PmanuSharedSecret="the-same-value-as-MANU_APP_SHARED_SECRET"`.

### 3. Enable Developer Mode + install
1. On the A55: **Settings ▸ About phone ▸ Software information** → tap **Build number**
   7 times to unlock Developer options.
2. **Settings ▸ Developer options** → enable **USB debugging**.
3. Connect USB and install:
   ```bash
   adb install -r app/build/outputs/apk/debug/app-debug.apk
   ```
   (or just copy the APK to the phone and tap it to sideload).

### 4. First run — grant the things Manu needs
1. Open **Manu**. Allow the **microphone** (and notifications) prompt.
2. Tap **"Manu ला Accessibility परवानगी द्या"** → in the list enable **Manu** →
   accept the warning. This is what lets Manu see and operate other apps.
3. Make sure the **Backend URL** field shows your backend address.
4. The first time you start a task you'll also see a **"Start recording / casting
   with Manu?"** system dialog — that's the **screen-capture** used only as a vision
   fallback when the text view of a screen isn't enough. Tap **Start now**. (You can
   decline; Manu then runs text-only and just won't "see" picture-only screens.)

### 5. Try it — smoke test (this is the real end-to-end check)
Tap the big **बोलण्यासाठी दाबा** (tap to speak) button and run each of these once.
Tick them off — this is the on-device acceptance test (it can only be done on a real
phone, not in CI):

| Capability | Say | Expected |
|---|---|---|
| Open app + control | *"Settings उघड"* | Settings opens; Manu says it's done |
| Read screen aloud | *"स्क्रीनवर काय आहे ते वाच"* | Manu speaks a summary of the screen |
| Web search | *"Chrome मध्ये आजचं हवामान शोध आणि सांग"* | Chrome opens, searches, reads the result |
| Send message (with confirm) | *"WhatsApp मध्ये आईला मेसेज कर 'मी निघालो'"* | Manu types it, then **asks "पाठवू का?"** and only sends after you say *"हो"* |

### 6. If a task gets stuck — diagnosing with logcat
Manu narrates each step in the status line, but for detail:
```bash
adb logcat | grep -iE "manu|AccessibilityService|MediaProjection"
```
Common fixes:
- **Nothing happens / "Accessibility off"** → re-enable Manu under
  Settings ▸ Accessibility (Samsung sometimes revokes it after updates).
- **Manu keeps retrying the same tap** → it will attach a screenshot and try another
  element after two failures; if it still can't, it asks you what to do.
- **"Server शी संपर्क होत नाही"** → the Backend URL is wrong/unreachable from the
  phone; confirm the phone and backend are on the same network (or use a public URL).

## Project layout
| Path | What it does |
|---|---|
| `MainActivity.kt` | UI, permissions, captures the spoken goal, starts the task |
| `service/AgentForegroundService.kt` | keeps the task running while Manu drives other apps |
| `agent/AgentLoop.kt` | the observe → backend → act loop |
| `agent/BackendClient.kt` | talks to `/agent/step` (no API key on device) |
| `accessibility/ScreenReader.kt` | turns the live screen into an observation |
| `accessibility/Actuator.kt` | performs taps / swipes / typing / back / home |
| `accessibility/ScreenCapturer.kt` | screenshot (MediaProjection) for the vision fallback |
| `voice/VoiceInput.kt`, `voice/Speaker.kt` | on-device speech-to-text and text-to-speech |

## Notes & limits (Phase 1)
- **Vision fallback is on:** when a screen's text view is sparse (or a tap keeps
  failing), Manu attaches a downscaled screenshot so Claude can "see" it. Text-first
  otherwise, to keep cost low.
- A usage dashboard, hands-free wake word, and per-app recipes come in Phase 2.
- The wake word is a button tap for now.
- Everything Manu "says" is in the language you spoke.

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

### 4. First run — grant the two things Manu needs
1. Open **Manu**. Allow the **microphone** (and notifications) prompt.
2. Tap **"Manu ला Accessibility परवानगी द्या"** → in the list enable **Manu** →
   accept the warning. This is what lets Manu see and operate other apps.
3. Make sure the **Backend URL** field shows your backend address.

### 5. Try it
Tap the big **बोलण्यासाठी दाबा** (tap to speak) button and say something like:
- *"Settings उघड"*
- *"Chrome मध्ये आजचं हवामान शोध आणि सांग"*
- *"स्क्रीनवर काय आहे ते वाच"*
- *"WhatsApp मध्ये आईला मेसेज कर 'मी निघालो'"* → Manu will confirm before sending.

## Project layout
| Path | What it does |
|---|---|
| `MainActivity.kt` | UI, permissions, captures the spoken goal, starts the task |
| `service/AgentForegroundService.kt` | keeps the task running while Manu drives other apps |
| `agent/AgentLoop.kt` | the observe → backend → act loop |
| `agent/BackendClient.kt` | talks to `/agent/step` (no API key on device) |
| `accessibility/ScreenReader.kt` | turns the live screen into an observation |
| `accessibility/Actuator.kt` | performs taps / swipes / typing / back / home |
| `voice/VoiceInput.kt`, `voice/Speaker.kt` | on-device speech-to-text and text-to-speech |

## Notes & limits (Phase 0)
- Screenshot/vision fallback, model-routing polish, a usage dashboard, and per-app
  recipes come in later phases (see the root plan). Phase 0 is a working skeleton.
- The wake word is a button tap for now; hands-free wake word is a later phase.
- Everything Manu "says" is in the language you spoke.

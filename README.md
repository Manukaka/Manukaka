# 🪷 Manu — Your Private, Offline Personal AI Assistant

Manu runs **100% offline on your own Windows laptop**. You feed it your phone
call recordings, WhatsApp chats, and SMS messages — it transcribes and
understands them (Marathi, Hindi, Hinglish, English), remembers what's going on
in your life, and answers questions / gives advice in a private desktop chat
window. **Nothing ever leaves your computer.**

Built for: Windows 11, NVIDIA RTX 4060 (8 GB), Intel i7, 16 GB+ RAM.

> **Looking for the phone app?** A separate, cloud-powered **voice agent for
> Android** (open apps, tap/type, browse, read the screen aloud — all by voice) is
> being built under [`mobile/`](mobile/) with its Claude proxy in
> [`backend/`](backend/). It's a different architecture from this offline desktop
> assistant; see [`mobile/README.md`](mobile/README.md) to build and sideload it.

---

## 1. One-time setup (needs internet ONCE)

1. Download this project: click the green **Code** button → **Download ZIP**, and unzip it (e.g. to `C:\Manu`).
2. Double-click **`setup.bat`** and wait. It installs:
   - Python 3.11, ffmpeg, and [Ollama](https://ollama.com) (the local AI engine)
   - PyTorch with CUDA (so your RTX 4060 is used)
   - The chat model **qwen3:8b** (~5 GB) — strong in Marathi/Hindi/English
   - The speech model **Whisper large-v3** (~3 GB) and the **BGE-M3** memory/search model (~2 GB)
3. **Speaker separation (who said what in calls):** during setup you'll be asked
   for a free Hugging Face token:
   - Create a free account at https://huggingface.co/join
   - Open https://huggingface.co/pyannote/segmentation-3.0 and https://huggingface.co/pyannote/speaker-diarization-3.1 — click **"Agree and access"** on both
   - Create a token at https://huggingface.co/settings/tokens and paste it when asked
   - This is needed **once**; afterwards everything is cached and fully offline.

Total download is roughly 12 GB, so the first setup takes a while. After that,
you can disconnect from the internet forever — Manu keeps working.

## 2. Getting your data out of your phone

| Data | How to export | Where to put it |
|---|---|---|
| **Call recordings** | Copy the audio files from your phone's recorder folder (`.m4a`, `.mp3`, `.amr`, `.opus` all work). Keep the original file names — Manu reads the contact name and date from them. | `ingest\audio\` |
| **WhatsApp chats** | In WhatsApp open a chat → ⋮ → **More** → **Export chat** → **Without media**. Send the `.txt` to your laptop. Repeat per chat. | `ingest\whatsapp\` |
| **SMS** | Install the free Android app **SMS Backup & Restore**, back up SMS as **XML**, copy the `.xml` to your laptop. | `ingest\sms\` |

You can drop **hundreds of files at once** — bulk is the whole point.

## 3. Daily use

1. Double-click **`run.bat`** → the Manu window opens.
2. Drop new files into the `ingest` folders, press **"Process new files"**, and
   watch the progress (transcribing calls takes roughly 1 minute per 2–3 minutes
   of audio on the 4060). Files already processed are skipped automatically, so
   re-processing is always safe.
3. Chat! Ask in Marathi, Hindi, or English — Manu replies in your language:
   - *"आईशी काय बोलणं झालं होतं गेल्या आठवड्यात?"*
   - *"What commitments do I have coming up?"*
   - *"Rahul ke saath Goa trip ka kya plan tha?"*
   - *"Looking at my conversations, what should I not forget this month?"*

While files are processing, chat is paused (the graphics card is busy
transcribing) — it unlocks automatically when processing finishes.

## 4. What Manu builds from your data

- `data\transcripts\` — readable transcripts of every call, with speakers separated
- `data\chroma\` — a private search index of all conversations
- `data\profile\profile.md` — Manu's growing notes about your life (people,
  commitments, money, health, work). Open it anytime — it's your data. Manu reads
  this before answering every question, plus the most relevant conversation excerpts.

**Privacy:** everything lives in the `data\` folder on your disk. Delete that
folder and Manu forgets everything. The `.gitignore` makes sure your personal
data is never uploaded if you push this project to GitHub.

## 5. Troubleshooting

| Problem | Fix |
|---|---|
| "Ollama not running" in the header | Start Ollama from the Start menu (it normally auto-starts), then wait a few seconds. |
| "model missing" in the header | Open PowerShell and run `ollama pull qwen3:8b`. |
| CUDA out-of-memory during transcription | Close games/browsers using the GPU and press "Process new files" again. |
| A recording fails to transcribe | Check it plays in a media player; exotic formats may need `ffmpeg` reinstall (`winget install Gyan.FFmpeg`). |
| Slow replies | First reply after starting loads the model (~20 s). If always slow, try the smaller model: edit `config.yaml` → `model: "qwen2.5:7b-instruct"` and `ollama pull qwen2.5:7b-instruct`. |
| Want transcription without the HF token | In `config.yaml` set `diarization.enabled: false` — calls become plain transcripts. |
| No GUI window opens | The app falls back to your browser at http://127.0.0.1:8765 automatically. |

## 6. For the curious — how it works

```
recordings ─ ffmpeg ─ Whisper large-v3 ─ pyannote (who said what) ─┐
WhatsApp .txt ── parser ─────────────────────────────────────────┼─ chunks ─ BGE-M3 ─ ChromaDB
SMS .xml ─────── parser ─────────────────────────────────────────┘                      │
                                                                                        ▼
you ⇄ desktop window (pywebview) ⇄ FastAPI ⇄ Ollama (qwen3:8b) ◄── profile.md + relevant excerpts
```

- One 8 GB GPU runs everything by **taking turns**: the chat model is unloaded
  while Whisper transcribes, then reloaded for chatting.
- `python scripts\ingest_cli.py` runs the same processing from a terminal.
- Tests: `python -m pytest tests\`

# 🪷 Manu — Your Private, Offline Personal AI Assistant

Manu runs **100% offline on your own Windows laptop**. You feed it your phone
call recordings, WhatsApp chats, SMS messages, **and your Google Photos** — it
transcribes and understands them (Marathi, Hindi, Hinglish, English), looks
*inside* your photos, remembers what's going on in your life, and answers
questions / gives advice in a private desktop window. It also draws your life as
a **3D mind map**, a **timeline**, **people pages**, and a **places map**.
**Nothing ever leaves your computer.**

Built for: Windows 11, NVIDIA RTX 4060 (8 GB), Intel i7, 16 GB+ RAM.

**The five tabs:**
- **💬 Chat** — ask anything about your life; answers are grounded in your data
- **🕸 Mind Map** — a 3D (or 2D) network of people, places and events; click a dot to see that person's photos and conversations
- **🕒 Timeline** — your calls, chats and photos mixed together by date
- **👥 People** — a card for everyone in your life, with an AI relationship summary
- **📍 Places** — an offline map pinned with where your photos were taken

---

## 1. One-time setup (needs internet ONCE)

1. Download this project: click the green **Code** button → **Download ZIP**, and unzip it (e.g. to `C:\Manu`).
2. Double-click **`setup.bat`** and wait. It installs:
   - Python 3.11, ffmpeg, and [Ollama](https://ollama.com) (the local AI engine)
   - PyTorch with CUDA (so your RTX 4060 is used)
   - The chat model **qwen3:8b** (~5 GB) — strong in Marathi/Hindi/English
   - The photo-understanding model **qwen2.5vl:7b** (~6 GB) — describes your photos
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
| **Photos** | See the Google Photos steps below. | `ingest\photos\` |

You can drop **hundreds of files at once** — bulk is the whole point.

### Getting your Google Photos (offline, via Takeout)

Manu does **not** connect to your Google account — instead you download your
photos once using Google's official export, which keeps everything offline and
includes your photos' **dates, locations, and the people Google tagged in them**.

1. Go to **https://takeout.google.com**
2. Click **Deselect all**, then scroll down and tick **only Google Photos**
3. Click **Next step** → **Create export** (choose `.zip`). Google emails you a download link (can take a while for big libraries).
4. Download the ZIP file(s) and drop them straight into `ingest\photos\` — Manu unzips them for you.
   (Or, if you prefer, unzip yourself and drop the `Google Photos` folder in, then delete the ZIP to save disk space.)
5. Press **Process new files**.

**Notes for big photo libraries:**
- Manu uses the AI to describe **every** photo so they become searchable and show
  up in your mind map. This is thorough but slow — roughly **5 seconds per photo**
  (so ~1 hour per 700 photos). For 10,000 photos expect an overnight run.
- **You can close Manu anytime** — captioning resumes where it left off next run.
- In a hurry? Edit `config.yaml` → `photos: captions: false` to skip photo
  descriptions (you still get dates, places, and people tags), or switch to the
  faster `caption_model: "gemma3:4b"` (then `ollama pull gemma3:4b`).
- Videos are skipped for now.
- Photos take real disk space — a Takeout ZIP is duplicated when unzipped.

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
   - *"When were we at that beach restaurant?"* (it can find this from a photo!)
4. Explore the other tabs — **Mind Map**, **Timeline**, **People**, **Places** —
   to *see* your life instead of just asking about it.

While files are processing, chat and the other tabs are paused (the graphics card
is busy) — they unlock automatically when processing finishes. Captioning a large
photo library can hold this for hours, which is why closing and resuming later is
safe.

## 4. What Manu builds from your data

- `data\transcripts\` — readable transcripts of every call, with speakers separated
- `data\chroma\` — a private search index of all conversations **and photo descriptions**
- `data\graph.db` — your life-graph: people, places, events, and your photo
  catalogue (this powers the Mind Map, Timeline, People and Places tabs)
- `data\thumbs\` — small thumbnails so the gallery views load instantly
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
| "model missing" in the header | Open PowerShell and run `ollama pull qwen3:8b`. For photos also run `ollama pull qwen2.5vl:7b`. |
| CUDA out-of-memory during transcription or photo captioning | Close games/browsers using the GPU and press "Process new files" again. Photo model too heavy? Set `caption_model: "gemma3:4b"` in `config.yaml` and `ollama pull gemma3:4b`. |
| Photo captioning is taking too long | Close Manu (progress is saved); it resumes next run. Or set `photos: captions: false` in `config.yaml` to skip descriptions. |
| Mind Map / Places is empty | You need photos or conversations processed first. The map only shows photos that have GPS location info. |
| A photo's people/date is missing | It depends on what Google saved in the Takeout export; photos without that info still appear, just with less detail. |
| A recording fails to transcribe | Check it plays in a media player; exotic formats may need `ffmpeg` reinstall (`winget install Gyan.FFmpeg`). |
| Slow replies | First reply after starting loads the model (~20 s). If always slow, try the smaller model: edit `config.yaml` → `model: "qwen2.5:7b-instruct"` and `ollama pull qwen2.5:7b-instruct`. |
| Want transcription without the HF token | In `config.yaml` set `diarization.enabled: false` — calls become plain transcripts. |
| No GUI window opens | The app falls back to your browser at http://127.0.0.1:8765 automatically. |

## 6. For the curious — how it works

```
recordings ─ ffmpeg ─ Whisper large-v3 ─ pyannote (who said what) ─┐
WhatsApp .txt ── parser ─────────────────────────────────────────┤
SMS .xml ─────── parser ─────────────────────────────────────────┼─ chunks ─ BGE-M3 ─ ChromaDB
Photos (Takeout) ─ metadata + qwen2.5vl captions ────────────────┘        │           │
       │                                                                  │           ▼
       └─ people tags + GPS ─ reverse-geocode ─ life-graph (SQLite) ──────┴──► Mind Map / Timeline / People / Places
                                                                                      │
you ⇄ desktop window (pywebview, tabs) ⇄ FastAPI ⇄ Ollama (qwen3:8b) ◄── profile.md + relevant excerpts
```

- One 8 GB GPU runs everything by **taking turns**: the chat model is unloaded
  while Whisper transcribes, then the photo model captions, then the chat model
  comes back — never two at once.
- Photo locations are turned into place names **offline** (no internet maps), and
  the Places tab draws the world from a bundled outline — no map tiles are downloaded.
- `python scripts\ingest_cli.py` runs the same processing from a terminal.
- Tests: `python -m pytest tests\`  ·  Refresh bundled UI libraries: `python scripts\vendor_ui_libs.py`

"""One-time model downloader so everything afterwards runs fully offline.

Downloads: Whisper large-v3 (faster-whisper build), BGE-M3 embeddings, and the
two gated pyannote diarization models (needs a free Hugging Face token once).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assistant import config  # noqa: E402

PYANNOTE_GATED = [
    "pyannote/segmentation-3.0",
    "pyannote/speaker-diarization-3.1",
]


def download_whisper():
    model = config.CFG["stt"]["whisper_model"]
    print(f"\n[1/3] Downloading Whisper '{model}' (~3 GB, one time)…")
    from huggingface_hub import snapshot_download
    snapshot_download(f"Systran/faster-whisper-{model}")
    print("      done.")


def download_embeddings():
    model = config.CFG["rag"]["embedding_model"]
    print(f"\n[2/3] Downloading embedding model '{model}' (~2 GB, one time)…")
    from huggingface_hub import snapshot_download
    snapshot_download(model)
    print("      done.")


def download_pyannote():
    print("\n[3/3] Speaker-separation models (pyannote) — these are 'gated':")
    print("      1. Create a free account at https://huggingface.co/join")
    for repo in PYANNOTE_GATED:
        print(f"      2. Open https://huggingface.co/{repo} and click 'Agree and access'")
    print("      3. Create a token at https://huggingface.co/settings/tokens (read access)")
    token = input("\nPaste your Hugging Face token (or press Enter to skip diarization): ").strip()
    if not token:
        print("Skipped. Calls will still be transcribed, just without 'who said what'.")
        print("Set diarization.enabled: false in config.yaml, or re-run this script later.")
        return
    from huggingface_hub import snapshot_download
    for repo in PYANNOTE_GATED:
        print(f"      downloading {repo}…")
        snapshot_download(repo, token=token)
    print("      done. The token is no longer needed — everything is cached locally.")


if __name__ == "__main__":
    print("Manu model downloader — needs internet ONCE; afterwards the app is fully offline.")
    download_whisper()
    download_embeddings()
    download_pyannote()
    print("\nAll set! Double-click run.bat to start Manu.")

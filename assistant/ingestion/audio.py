"""Call-recording pipeline: ffmpeg → faster-whisper → pyannote → merged transcript.

Heavy libraries (torch, faster_whisper, pyannote) are imported lazily inside
functions so the rest of the app — parsers, tests, the chat server — never pays
for them and can run on machines without a GPU.
"""
import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .. import config
from .models import Message

AUDIO_EXTS = {".m4a", ".mp3", ".amr", ".opus", ".wav", ".ogg", ".aac", ".3gp", ".flac"}

# e.g. "Call recording Amol Patil_230512_1830.m4a", "Amol Patil 2024-05-13 18.30.m4a"
DATE_PATTERNS = [
    re.compile(r"(\d{4})[-_.]?(\d{2})[-_.]?(\d{2})[ T_-]?(\d{2})[-_.:]?(\d{2})"),
    re.compile(r"(\d{2})(\d{2})(\d{2})[ _-](\d{2})(\d{2})"),  # yymmdd_hhmm
]


@dataclass
class Utterance:
    speaker: str
    start: float
    end: float
    text: str


def contact_from_filename(path: Path) -> str:
    name = path.stem
    name = re.sub(r"^(call\s*recording|recording|call)[\s_-]*", "", name, flags=re.IGNORECASE)
    # Drop trailing date/number blocks: "Amol Patil_230512_1830" -> "Amol Patil"
    name = re.split(r"[_\-]?\d{4,}", name)[0]
    name = name.replace("_", " ").strip(" -_.")
    return name or path.stem


def timestamp_from_file(path: Path) -> datetime:
    for pat in DATE_PATTERNS:
        m = pat.search(path.stem)
        if m:
            g = [int(x) for x in m.groups()]
            try:
                if pat is DATE_PATTERNS[1]:  # yymmdd
                    return datetime(2000 + g[0], g[1], g[2], g[3], g[4])
                return datetime(g[0], g[1], g[2], g[3], g[4])
            except ValueError:
                continue
    return datetime.fromtimestamp(path.stat().st_mtime)


def to_wav(src: Path) -> Path:
    """Convert any phone-recorder format to 16kHz mono WAV for the models."""
    out = Path(tempfile.gettempdir()) / (src.stem + "_16k.wav")
    subprocess.run(
        ["ffmpeg", "-y", "-i", str(src), "-ac", "1", "-ar", "16000", str(out)],
        check=True, capture_output=True,
    )
    return out


def _assign_speaker(word_start: float, word_end: float, turns: list) -> str:
    """Pick the diarization turn with max overlap; fall back to nearest midpoint."""
    def overlap(t):
        return max(0.0, min(word_end, t[1]) - max(word_start, t[0]))
    best = max(turns, key=overlap, default=None)
    if best and overlap(best) > 0:
        return best[2]
    mid = (word_start + word_end) / 2
    return min(turns, key=lambda t: abs((t[0] + t[1]) / 2 - mid))[2]


class AudioPipeline:
    """Loads whisper + pyannote once and processes a batch of recordings."""

    def __init__(self):
        stt = config.CFG["stt"]
        dia = config.CFG["diarization"]
        from faster_whisper import WhisperModel
        self.whisper = WhisperModel(
            stt["whisper_model"], device=stt["device"], compute_type=stt["compute_type"]
        )
        self.language: Optional[str] = stt.get("language")
        self.diarizer = None
        self.num_speakers = dia.get("num_speakers")
        if dia.get("enabled", True):
            import torch
            from pyannote.audio import Pipeline
            self.diarizer = Pipeline.from_pretrained(dia["model"])
            if stt["device"] == "cuda" and torch.cuda.is_available():
                self.diarizer.to(torch.device("cuda"))

    def transcribe(self, wav: Path) -> List[Utterance]:
        segments, _info = self.whisper.transcribe(
            str(wav), language=self.language, word_timestamps=True, vad_filter=True
        )
        words = []
        for seg in segments:
            for w in (seg.words or []):
                words.append(w)

        turns = []
        if self.diarizer is not None:
            kwargs = {"num_speakers": self.num_speakers} if self.num_speakers else {}
            diarization = self.diarizer(str(wav), **kwargs)
            turns = [(t.start, t.end, spk)
                     for t, _, spk in diarization.itertracks(yield_label=True)]

        utterances: List[Utterance] = []
        for w in words:
            speaker = _assign_speaker(w.start, w.end, turns) if turns else "SPEAKER_00"
            if utterances and utterances[-1].speaker == speaker:
                utterances[-1].text += w.word
                utterances[-1].end = w.end
            else:
                utterances.append(Utterance(speaker, w.start, w.end, w.word.strip()))
        for u in utterances:
            u.text = u.text.strip()
        return [u for u in utterances if u.text]

    def close(self):
        """Release VRAM so Ollama can load the LLM afterwards."""
        import gc
        self.whisper = None
        self.diarizer = None
        gc.collect()
        try:
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except ImportError:
            pass


def save_transcript(audio_file: Path, utterances: List[Utterance]) -> None:
    config.TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)
    data = [{"speaker": u.speaker, "start": round(u.start, 2),
             "end": round(u.end, 2), "text": u.text} for u in utterances]
    (config.TRANSCRIPTS_DIR / f"{audio_file.stem}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [f"[{u.speaker}] {u.text}" for u in utterances]
    (config.TRANSCRIPTS_DIR / f"{audio_file.stem}.txt").write_text(
        "\n".join(lines), encoding="utf-8")


def utterances_to_messages(audio_file: Path, utterances: List[Utterance]) -> List[Message]:
    """Express a call transcript in the same Message shape as chats, so chunking is uniform."""
    contact = contact_from_filename(audio_file)
    base_ts = timestamp_from_file(audio_file)
    out: List[Message] = []
    for u in utterances:
        out.append(Message(
            timestamp=base_ts, sender=u.speaker, text=u.text,
            contact=contact, source_type="call", source_file=audio_file.name,
        ))
    return out

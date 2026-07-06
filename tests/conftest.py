import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from assistant import config  # noqa: E402


@pytest.fixture
def tmp_data_dirs(tmp_path, monkeypatch):
    """Point every data/ingest path at a throwaway directory so tests never
    touch the repo's real folders."""
    paths = {
        "INGEST_DIR": tmp_path / "ingest",
        "INGEST_AUDIO": tmp_path / "ingest" / "audio",
        "INGEST_WHATSAPP": tmp_path / "ingest" / "whatsapp",
        "INGEST_SMS": tmp_path / "ingest" / "sms",
        "DATA_DIR": tmp_path / "data",
        "CHROMA_DIR": tmp_path / "data" / "chroma",
        "TRANSCRIPTS_DIR": tmp_path / "data" / "transcripts",
        "PROFILE_DIR": tmp_path / "data" / "profile",
        "PROFILE_BACKUP_DIR": tmp_path / "data" / "profile" / "backups",
        "PROFILE_JSON": tmp_path / "data" / "profile" / "profile.json",
        "PROFILE_MD": tmp_path / "data" / "profile" / "profile.md",
        "MANIFEST_PATH": tmp_path / "data" / "manifest.json",
        "LOG_DIR": tmp_path / "data" / "logs",
    }
    for name, value in paths.items():
        monkeypatch.setattr(config, name, value)
    return tmp_path

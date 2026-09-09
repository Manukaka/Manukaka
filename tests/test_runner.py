import json
import shutil
from pathlib import Path

from assistant.ingestion import runner
from assistant.llm import ollama_client
from assistant.rag import embeddings, store

FIXTURES = Path(__file__).parent / "fixtures"


def test_new_files_skips_manifest_gitkeep_and_wrong_ext(tmp_path):
    (tmp_path / "a.txt").write_text("one", encoding="utf-8")
    (tmp_path / "b.txt").write_text("two", encoding="utf-8")
    (tmp_path / ".gitkeep").write_text("", encoding="utf-8")
    (tmp_path / "notes.pdf").write_text("skip me", encoding="utf-8")

    manifest = {runner._sha256(tmp_path / "a.txt"): "a.txt"}
    fresh = runner._new_files(tmp_path, {".txt"}, manifest)
    assert [f.name for f in fresh] == ["b.txt"]


def test_new_files_missing_folder_is_empty():
    assert runner._new_files(Path("/does/not/exist"), {".txt"}, {}) == []


def _fake_rag(monkeypatch, indexed):
    monkeypatch.setattr(embeddings, "embed_texts",
                        lambda texts: [[0.0] * 3 for _ in texts])
    monkeypatch.setattr(store, "upsert_chunks",
                        lambda chunks, embs: indexed.extend(chunks))


def test_run_ingest_text_sources_end_to_end(tmp_data_dirs, monkeypatch):
    shutil.copy(FIXTURES / "WhatsApp Chat with Aai.txt",
                _mk(runner.config.INGEST_WHATSAPP) / "WhatsApp Chat with Aai.txt")
    shutil.copy(FIXTURES / "sms_backup.xml",
                _mk(runner.config.INGEST_SMS) / "sms_backup.xml")

    indexed = []
    _fake_rag(monkeypatch, indexed)
    monkeypatch.setattr(ollama_client, "is_up", lambda: False)  # skip profile phase

    statuses = []
    counters = runner.run_ingest(statuses.append)

    assert counters["whatsapp"] == 1
    assert counters["sms"] == 1
    assert counters["audio"] == 0
    assert counters["errors"] == 0
    assert counters["chunks"] == len(indexed) > 0

    manifest = json.loads(runner.config.MANIFEST_PATH.read_text(encoding="utf-8"))
    assert set(manifest.values()) == {"WhatsApp Chat with Aai.txt", "sms_backup.xml"}
    assert any("skipping profile update" in s for s in statuses)


def test_run_ingest_is_idempotent(tmp_data_dirs, monkeypatch):
    shutil.copy(FIXTURES / "WhatsApp Chat with Aai.txt",
                _mk(runner.config.INGEST_WHATSAPP) / "WhatsApp Chat with Aai.txt")
    indexed = []
    _fake_rag(monkeypatch, indexed)
    monkeypatch.setattr(ollama_client, "is_up", lambda: False)

    assert runner.run_ingest(lambda s: None)["whatsapp"] == 1
    second = runner.run_ingest(lambda s: None)
    assert second["whatsapp"] == 0 and second["chunks"] == 0  # nothing re-processed


def test_run_ingest_counts_parse_failures(tmp_data_dirs, monkeypatch):
    bad = _mk(runner.config.INGEST_SMS) / "broken.xml"
    bad.write_text("<smses><sms", encoding="utf-8")  # malformed XML
    indexed = []
    _fake_rag(monkeypatch, indexed)
    monkeypatch.setattr(ollama_client, "is_up", lambda: False)

    counters = runner.run_ingest(lambda s: None)
    assert counters["errors"] == 1
    assert counters["sms"] == 0
    # a failed file must NOT enter the manifest, so a fixed export retries later
    manifest = json.loads(runner.config.MANIFEST_PATH.read_text(encoding="utf-8"))
    assert "broken.xml" not in manifest.values()


def _mk(folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    return folder

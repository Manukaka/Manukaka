"""Shared fixtures: redirect Manu's data paths into a temp dir so tests never
touch a real graph.db or thumbs folder, and reset the sqlite connection."""
from pathlib import Path

import pytest

from assistant import config
from assistant.graph import store as graph_store

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def tmp_data(tmp_path, monkeypatch):
    data = tmp_path / "data"
    photos = tmp_path / "ingest" / "photos"
    thumbs = data / "thumbs"
    for d in (data, photos, thumbs):
        d.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(config, "DATA_DIR", data)
    monkeypatch.setattr(config, "GRAPH_DB", data / "graph.db")
    monkeypatch.setattr(config, "THUMBS_DIR", thumbs)
    monkeypatch.setattr(config, "INGEST_PHOTOS", photos)
    graph_store.close()
    yield {"data": data, "photos": photos, "thumbs": thumbs}
    graph_store.close()

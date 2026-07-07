from assistant.ingestion.watcher import FolderWatcher


def _wa_dir(config):
    d = config.INGEST_WHATSAPP
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_triggers_once_files_are_stable(tmp_data_dirs):
    from assistant import config
    d = _wa_dir(config)
    w = FolderWatcher()

    assert w.should_ingest() is False        # first poll: nothing to compare yet
    assert w.should_ingest() is True         # stable (even empty) → startup catch-up
    w.mark_ingested()
    assert w.should_ingest() is False        # settled

    (d / "chat.txt").write_text("hello", encoding="utf-8")
    assert w.should_ingest() is False        # snapshot changed → wait for stability
    assert w.should_ingest() is True         # unchanged twice → go
    w.mark_ingested()
    assert w.should_ingest() is False


def test_growing_file_is_not_ingested_midcopy(tmp_data_dirs):
    from assistant import config
    d = _wa_dir(config)
    w = FolderWatcher()
    w.should_ingest(), w.should_ingest()
    w.mark_ingested()

    f = d / "export.txt"
    f.write_text("part1", encoding="utf-8")
    assert w.should_ingest() is False        # new file
    f.write_text("part1part2", encoding="utf-8")
    assert w.should_ingest() is False        # still growing between polls
    assert w.should_ingest() is True         # size finally stable


def test_ignores_gitkeep_and_wrong_extensions(tmp_data_dirs):
    from assistant import config
    d = _wa_dir(config)
    w = FolderWatcher()
    w.should_ingest(), w.should_ingest()
    w.mark_ingested()

    (d / ".gitkeep").write_text("", encoding="utf-8")
    (d / "notes.pdf").write_text("x", encoding="utf-8")
    assert w.should_ingest() is False
    assert w.should_ingest() is False        # snapshot never changed → stays settled

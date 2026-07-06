import json

from assistant.llm import ollama_client
from assistant.memory import profile


def _extraction(**overrides):
    result = {
        "people": [], "commitments": [], "finances": [],
        "health": [], "work": [], "preferences": [],
    }
    result.update(overrides)
    return result


def test_extract_appends_facts_and_renders_md(tmp_data_dirs, monkeypatch):
    monkeypatch.setattr(ollama_client, "extract", lambda *a, **k: _extraction(
        commitments=[{"what": "pay electricity bill", "due": "20 May"}],
        finances=["MSEB bill ₹1,431 due 20 May"],
    ))
    profile.extract_from_conversation("SMS with MSEB, 13 May 2024", "…")

    stored = json.loads(profile.config.PROFILE_JSON.read_text(encoding="utf-8"))
    assert len(stored["commitments"]) == 1
    assert stored["commitments"][0]["source"] == "SMS with MSEB, 13 May 2024"

    md = profile.load_profile_md()
    # Commitments render first (most actionable) and dict facts flatten to text
    assert md.index("Commitments") < md.index("Finances")
    assert "pay electricity bill" in md and "20 May" in md


def test_extract_none_result_changes_nothing(tmp_data_dirs, monkeypatch):
    monkeypatch.setattr(ollama_client, "extract", lambda *a, **k: None)
    profile.extract_from_conversation("call with Aai", "…")
    assert not profile.config.PROFILE_JSON.exists()


def test_merge_backs_up_before_rewriting(tmp_data_dirs, monkeypatch):
    monkeypatch.setitem(profile.config.CFG["profile"], "max_facts_before_merge", 2)
    calls = {"n": 0}

    def fake_extract(prompt, schema, system=None):
        calls["n"] += 1
        if system == profile.prompts.PROFILE_MERGE_SYSTEM:
            return _extraction(work=["merged: new job at Infosys"])
        return _extraction(work=[f"fact {calls['n']}"])

    monkeypatch.setattr(ollama_client, "extract", fake_extract)
    for i in range(3):  # third insert crosses the threshold → merge
        profile.extract_from_conversation(f"chat {i}", "…")

    stored = json.loads(profile.config.PROFILE_JSON.read_text(encoding="utf-8"))
    assert stored["work"][0]["fact"] == "merged: new job at Infosys"
    assert stored["work"][0]["source"] == "merged"

    backups = list(profile.config.PROFILE_BACKUP_DIR.glob("profile-*.json"))
    assert len(backups) == 1
    pre_merge = json.loads(backups[0].read_text(encoding="utf-8"))
    assert len(pre_merge["work"]) >= 2  # the un-merged facts are recoverable


def test_failed_merge_keeps_existing_profile(tmp_data_dirs, monkeypatch):
    monkeypatch.setitem(profile.config.CFG["profile"], "max_facts_before_merge", 1)

    def fake_extract(prompt, schema, system=None):
        if system == profile.prompts.PROFILE_MERGE_SYSTEM:
            return None  # merge LLM call failed
        return _extraction(health=["BP medicine morning and night"])

    monkeypatch.setattr(ollama_client, "extract", fake_extract)
    profile.extract_from_conversation("chat 0", "…")
    profile.extract_from_conversation("chat 1", "…")

    stored = json.loads(profile.config.PROFILE_JSON.read_text(encoding="utf-8"))
    assert len(stored["health"]) == 2  # nothing was lost


def test_render_md_respects_max_chars(tmp_data_dirs, monkeypatch):
    monkeypatch.setitem(profile.config.CFG["profile"], "profile_md_max_chars", 120)
    data = {c: [] for c in profile.CATEGORIES}
    data["work"] = [{"fact": "x" * 50, "source": "s", "date": "2024-05-13"}] * 10
    assert len(profile.render_md(data)) <= 120

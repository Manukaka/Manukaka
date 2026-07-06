import pytest

from assistant.config import load_config


def _write(tmp_path, text):
    p = tmp_path / "config.yaml"
    p.write_text(text, encoding="utf-8")
    return p


def test_minimal_config_gets_defaults(tmp_path):
    cfg = load_config(_write(tmp_path, "llm:\n  model: qwen3:8b\n"))
    assert cfg["llm"]["model"] == "qwen3:8b"
    assert cfg["llm"]["num_ctx"] == 8192          # default filled in
    assert cfg["rag"]["top_k_use"] == 6
    assert cfg["stt"]["language"] is None
    assert cfg["app"]["port"] == 8765


def test_typo_in_key_is_named_in_the_error(tmp_path):
    path = _write(tmp_path, "llm:\n  model: qwen3:8b\n  temprature: 0.4\n")
    with pytest.raises(SystemExit) as exc:
        load_config(path)
    assert "temprature" in str(exc.value)


def test_wrong_type_is_rejected(tmp_path):
    path = _write(tmp_path, "llm:\n  model: qwen3:8b\n  num_ctx: lots\n")
    with pytest.raises(SystemExit) as exc:
        load_config(path)
    assert "num_ctx" in str(exc.value)


def test_missing_required_model(tmp_path):
    path = _write(tmp_path, "llm: {}\n")
    with pytest.raises(SystemExit) as exc:
        load_config(path)
    assert "model" in str(exc.value)


def test_missing_file(tmp_path):
    with pytest.raises(SystemExit):
        load_config(tmp_path / "nope.yaml")


def test_invalid_yaml(tmp_path):
    path = _write(tmp_path, "llm: [unclosed\n")
    with pytest.raises(SystemExit):
        load_config(path)


def test_repo_config_is_valid():
    from assistant import config
    cfg = load_config(config.ROOT / "config.yaml")
    assert cfg["llm"]["model"]

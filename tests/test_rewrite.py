from assistant.llm import ollama_client
from assistant.rag import rewrite

HISTORY = [
    {"role": "user", "content": "Rahul ke saath Goa trip ka kya plan tha?"},
    {"role": "assistant", "content": "June first week ka plan tha [1]."},
]


def test_no_history_skips_the_llm(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("must not call the LLM without history")
    monkeypatch.setattr(ollama_client, "extract", boom)
    assert rewrite.rewrite("what did she say?", []) == []


def test_disabled_by_config(monkeypatch):
    monkeypatch.setitem(rewrite.config.CFG["rag"], "query_rewrite", False)
    monkeypatch.setattr(ollama_client, "extract",
                        lambda *a, **k: {"queries": ["should not be used"]})
    assert rewrite.rewrite("what did she say?", HISTORY) == []


def test_returns_capped_cleaned_queries(monkeypatch):
    monkeypatch.setattr(ollama_client, "extract", lambda *a, **k: {
        "queries": ["  Goa trip dates Rahul ", "kab jana hai Goa", "extra third", ""],
    })
    out = rewrite.rewrite("kab jana hai?", HISTORY)
    assert out == ["Goa trip dates Rahul", "kab jana hai Goa"]  # trimmed, max 2


def test_echo_of_question_is_dropped(monkeypatch):
    monkeypatch.setattr(ollama_client, "extract",
                        lambda *a, **k: {"queries": ["What did she say?"]})
    assert rewrite.rewrite("what did she say?", HISTORY) == []


def test_llm_failure_falls_back_to_nothing(monkeypatch):
    monkeypatch.setattr(ollama_client, "extract", lambda *a, **k: None)
    assert rewrite.rewrite("what did she say?", HISTORY) == []

    def boom(*a, **k):
        raise RuntimeError("ollama exploded")
    monkeypatch.setattr(ollama_client, "extract", boom)
    assert rewrite.rewrite("what did she say?", HISTORY) == []

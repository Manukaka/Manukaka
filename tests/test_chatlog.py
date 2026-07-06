from assistant.memory import chatlog


def test_append_and_recent_order(tmp_data_dirs):
    chatlog.append("user", "pahila prashna")
    chatlog.append("assistant", "pahila uttar")
    chatlog.append("user", "dusra prashna")
    msgs = chatlog.recent()
    assert [m["role"] for m in msgs] == ["user", "assistant", "user"]
    assert msgs[0]["content"] == "pahila prashna"


def test_recent_limit_keeps_newest(tmp_data_dirs):
    for i in range(10):
        chatlog.append("user", f"m{i}")
    msgs = chatlog.recent(limit=3)
    assert [m["content"] for m in msgs] == ["m7", "m8", "m9"]


def test_persists_across_connections(tmp_data_dirs):
    chatlog.append("user", "kayam rahato ka?")
    assert chatlog.recent()[0]["content"] == "kayam rahato ka?"  # new connection reads it


def test_clear(tmp_data_dirs):
    chatlog.append("user", "x")
    chatlog.clear()
    assert chatlog.recent() == []

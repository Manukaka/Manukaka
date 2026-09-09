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


def test_named_conversations_are_isolated(tmp_data_dirs):
    a = chatlog.create_conversation("Goa trip")
    b = chatlog.create_conversation("Money")
    chatlog.append("user", "goa plan?", a)
    chatlog.append("assistant", "June", a)
    chatlog.append("user", "loan status?", b)

    assert [m["content"] for m in chatlog.recent(conv_id=a)] == ["goa plan?", "June"]
    assert [m["content"] for m in chatlog.recent(conv_id=b)] == ["loan status?"]


def test_first_user_message_auto_titles(tmp_data_dirs):
    cid = chatlog.create_conversation()  # default "New chat"
    chatlog.append("user", "Rahul ke saath Goa trip ka plan kya tha bilkul", cid)
    conv = next(c for c in chatlog.list_conversations() if c["id"] == cid)
    assert conv["title"].startswith("Rahul ke saath Goa")
    assert len(conv["title"]) <= 40


def test_append_returns_conversation_id_and_none_uses_current(tmp_data_dirs):
    cid = chatlog.append("user", "hi")           # no conv_id → current is created
    again = chatlog.append("assistant", "hello")  # same current conversation
    assert cid == again
    assert len(chatlog.list_conversations()) == 1


def test_list_orders_by_recent_and_counts(tmp_data_dirs):
    a = chatlog.create_conversation("older")
    chatlog.create_conversation("newer")
    chatlog.append("user", "x", a)   # touching a makes it most-recent
    listing = chatlog.list_conversations()
    assert [c["title"] for c in listing] == ["older", "newer"]
    assert listing[0]["count"] == 1 and listing[1]["count"] == 0


def test_rename_and_delete(tmp_data_dirs):
    cid = chatlog.create_conversation("temp")
    chatlog.append("user", "note", cid)
    chatlog.rename(cid, "Renamed")
    assert chatlog.list_conversations()[0]["title"] == "Renamed"

    chatlog.delete_conversation(cid)
    assert chatlog.list_conversations() == []
    assert chatlog.recent(conv_id=cid) == []


def test_migrates_flat_schema_to_conversations(tmp_data_dirs):
    import sqlite3

    from assistant import config
    config.CHAT_DB.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(config.CHAT_DB)  # old shape: messages, no conv_id
    con.execute("CREATE TABLE messages (id INTEGER PRIMARY KEY AUTOINCREMENT,"
                " ts REAL NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL)")
    con.execute("INSERT INTO messages (ts, role, content) VALUES (1, 'user', 'legacy')")
    con.commit()
    con.close()

    convs = chatlog.list_conversations()  # first connect runs the migration
    assert len(convs) == 1
    assert convs[0]["title"] == "Earlier chat"
    assert [m["content"] for m in chatlog.recent(conv_id=convs[0]["id"])] == ["legacy"]

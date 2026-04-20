"""Extended tests for memory subsystem — ConversationStore and WorkingMemory sessions."""

from __future__ import annotations

import pytest


# ── ConversationStore tests ─────────────────────────────────────

class TestConversationStore:
    def test_save_and_load_turns(self, tmp_path):
        from voca.memory.persistence import ConversationStore
        store = ConversationStore(db_path=tmp_path / "conv.db")
        store.save_turn("user", "Hello!", session_id="s1")
        store.save_turn("assistant", "Hi there!", session_id="s1", agent="companion")

        turns = store.load_turns(session_id="s1")
        assert len(turns) == 2
        assert turns[0]["role"] == "user"
        assert turns[0]["content"] == "Hello!"
        assert turns[1]["role"] == "assistant"
        assert turns[1]["agent"] == "companion"
        store.close()

    def test_load_turns_order(self, tmp_path):
        from voca.memory.persistence import ConversationStore
        store = ConversationStore(db_path=tmp_path / "conv.db")
        for i in range(5):
            store.save_turn("user", f"Message {i}", session_id="s1")

        turns = store.load_turns(session_id="s1", limit=3)
        assert len(turns) == 3
        assert turns[0]["content"] == "Message 2"
        assert turns[1]["content"] == "Message 3"
        assert turns[2]["content"] == "Message 4"
        store.close()

    def test_list_sessions(self, tmp_path):
        from voca.memory.persistence import ConversationStore
        store = ConversationStore(db_path=tmp_path / "conv.db")
        store.save_turn("user", "A", session_id="alpha")
        store.save_turn("user", "B", session_id="beta")
        store.save_turn("user", "C", session_id="alpha")

        sessions = store.list_sessions()
        assert "alpha" in sessions
        assert "beta" in sessions
        assert len(sessions) == 2
        store.close()

    def test_delete_session(self, tmp_path):
        from voca.memory.persistence import ConversationStore
        store = ConversationStore(db_path=tmp_path / "conv.db")
        store.save_turn("user", "A", session_id="to_delete")
        store.save_turn("user", "B", session_id="to_keep")

        count = store.delete_session("to_delete")
        assert count == 1
        assert store.load_turns(session_id="to_delete") == []
        assert len(store.load_turns(session_id="to_keep")) == 1
        store.close()

    def test_prune_old_turns(self, tmp_path):
        from voca.memory.persistence import ConversationStore
        store = ConversationStore(db_path=tmp_path / "conv.db")
        store.save_turn("user", "Recent", session_id="s1")

        count = store.prune(max_age_days=0)
        assert count >= 1
        assert store.load_turns(session_id="s1") == []
        store.close()

    def test_close_works(self, tmp_path):
        from voca.memory.persistence import ConversationStore
        store = ConversationStore(db_path=tmp_path / "conv.db")
        store.save_turn("user", "test")
        store.close()

    def test_metadata_roundtrip(self, tmp_path):
        from voca.memory.persistence import ConversationStore
        store = ConversationStore(db_path=tmp_path / "conv.db")
        store.save_turn("user", "Hello", metadata={"intent": "greeting", "score": 0.95})
        turns = store.load_turns()
        assert turns[0]["metadata"] == {"intent": "greeting", "score": 0.95}
        store.close()

    def test_default_session_id(self, tmp_path):
        from voca.memory.persistence import ConversationStore
        store = ConversationStore(db_path=tmp_path / "conv.db")
        store.save_turn("user", "Hello")
        turns = store.load_turns(session_id="default")
        assert len(turns) == 1
        store.close()


# ── WorkingMemory session tests ─────────────────────────────────

class TestWorkingMemorySessions:
    def test_add_to_session(self):
        from voca.memory.working import WorkingMemory
        wm = WorkingMemory(max_turns=10)
        wm.add("user", "Hello", session_id="s1")
        wm.add("assistant", "Hi!", session_id="s1")
        ctx = wm.get_context(session_id="s1")
        assert len(ctx) == 2
        assert ctx[0]["content"] == "Hello"

    def test_session_trimming(self):
        from voca.memory.working import WorkingMemory
        wm = WorkingMemory(max_turns=3)
        for i in range(5):
            wm.add("user", f"Msg {i}", session_id="s1")
        ctx = wm.get_context(session_id="s1")
        assert len(ctx) == 3
        assert ctx[0]["content"] == "Msg 2"

    def test_get_recent_with_session(self):
        from voca.memory.working import WorkingMemory
        wm = WorkingMemory(max_turns=10)
        for i in range(5):
            wm.add("user", f"Msg {i}", session_id="s1")
        recent = wm.get_recent(n=2, session_id="s1")
        assert len(recent) == 2
        assert recent[0].content == "Msg 3"
        assert recent[1].content == "Msg 4"

    def test_clear_session_only(self):
        from voca.memory.working import WorkingMemory
        wm = WorkingMemory(max_turns=10)
        wm.add("user", "A", session_id="s1")
        wm.add("user", "B", session_id="s2")
        wm.clear(session_id="s1")
        assert wm.get_context(session_id="s1") == []
        assert len(wm.get_context(session_id="s2")) == 1

    def test_remove_session(self):
        from voca.memory.working import WorkingMemory
        wm = WorkingMemory(max_turns=10)
        wm.add("user", "A", session_id="s1")
        wm.add("user", "B", session_id="s2")
        wm.remove_session("s1")
        assert wm.session_count == 1

    def test_session_count_property(self):
        from voca.memory.working import WorkingMemory
        wm = WorkingMemory(max_turns=10)
        assert wm.session_count == 0
        wm.add("user", "A", session_id="s1")
        wm.add("user", "B", session_id="s2")
        assert wm.session_count == 2

    def test_turn_count_property(self):
        from voca.memory.working import WorkingMemory
        wm = WorkingMemory(max_turns=10)
        assert wm.turn_count == 0
        wm.add("user", "A")
        wm.add("user", "B")
        assert wm.turn_count == 2

    def test_get_last_agent_with_session(self):
        from voca.memory.working import WorkingMemory
        wm = WorkingMemory(max_turns=10)
        wm.add("user", "hello", session_id="s1")
        wm.add("assistant", "hi", agent="companion", session_id="s1")
        wm.add("assistant", "done", agent="operator", session_id="s1")
        assert wm.get_last_agent(session_id="s1") == "operator"

    def test_clear_all_sessions(self):
        from voca.memory.working import WorkingMemory
        wm = WorkingMemory(max_turns=10)
        wm.add("user", "A", session_id="s1")
        wm.add("user", "B", session_id="s2")
        wm.add("user", "C")
        wm.clear()
        assert len(wm) == 0
        assert wm.session_count == 0

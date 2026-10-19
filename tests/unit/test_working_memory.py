"""Unit tests for working memory (issue #46 coverage drive).

Covers vera/memory/working.py — the short-term conversation
context store, previously at 0% coverage with no dedicated unit
test file. Pins the contract the brain relies on: turns are
kept in order and trimmed to max_turns, session-tagged turns
land in both the session list and the global list, context is
exported in LLM message format, and clear/remove_session have
exactly the blast radius their callers expect.
"""

from __future__ import annotations

import pytest

from vera.memory.working import Turn, WorkingMemory


@pytest.fixture
def mem() -> WorkingMemory:
    return WorkingMemory()


class TestTurn:
    def test_defaults(self):
        turn = Turn(role="user", content="hello")
        assert turn.agent is None
        assert turn.metadata is None
        assert turn.timestamp > 0

    def test_explicit_fields(self):
        turn = Turn(role="assistant", content="hi", agent="vera", metadata={"k": 1})
        assert turn.agent == "vera"
        assert turn.metadata == {"k": 1}


class TestAddAndTrim:
    def test_add_appends_in_order(self, mem):
        mem.add("user", "one")
        mem.add("assistant", "two")
        assert mem.turn_count == 2
        assert len(mem) == 2
        assert [t.content for t in mem.get_recent(2)] == ["one", "two"]

    def test_global_list_trims_to_max_turns(self):
        mem = WorkingMemory(max_turns=3)
        for i in range(5):
            mem.add("user", f"msg-{i}")
        assert mem.turn_count == 3
        assert [t.content for t in mem.get_recent(3)] == ["msg-2", "msg-3", "msg-4"]

    def test_session_list_trims_to_max_turns(self):
        mem = WorkingMemory(max_turns=2)
        for i in range(4):
            mem.add("user", f"s-{i}", session_id="s1")
        ctx = mem.get_context(session_id="s1")
        assert [m["content"] for m in ctx] == ["s-2", "s-3"]

    def test_session_add_also_lands_in_global_list(self, mem):
        mem.add("user", "shared", session_id="s1")
        assert mem.turn_count == 1
        assert mem.session_count == 1
        assert mem.get_context() == [{"role": "user", "content": "shared"}]


class TestGetContext:
    def test_context_is_llm_message_format(self, mem):
        mem.add("user", "q", agent="ignored-in-export")
        mem.add("assistant", "a")
        assert mem.get_context() == [
            {"role": "user", "content": "q"},
            {"role": "assistant", "content": "a"},
        ]

    def test_context_for_session_returns_only_that_session(self, mem):
        mem.add("user", "global-only")
        mem.add("user", "in-s1", session_id="s1")
        mem.add("user", "in-s2", session_id="s2")
        assert [m["content"] for m in mem.get_context(session_id="s1")] == ["in-s1"]
        assert [m["content"] for m in mem.get_context(session_id="s2")] == ["in-s2"]

    def test_context_for_unknown_session_falls_back_to_global(self, mem):
        mem.add("user", "global")
        assert mem.get_context(session_id="nope") == [{"role": "user", "content": "global"}]


class TestGetRecent:
    def test_recent_defaults_to_five(self, mem):
        for i in range(8):
            mem.add("user", f"m{i}")
        recent = mem.get_recent()
        assert [t.content for t in recent] == ["m3", "m4", "m5", "m6", "m7"]

    def test_recent_respects_n_and_session(self, mem):
        mem.add("user", "g")
        mem.add("user", "a", session_id="s1")
        mem.add("user", "b", session_id="s1")
        assert [t.content for t in mem.get_recent(1, session_id="s1")] == ["b"]
        # Session adds also land in the global list, so the global
        # tail is the session's latest turn too.
        assert [t.content for t in mem.get_recent(1)] == ["b"]
        assert [t.content for t in mem.get_recent(3)] == ["g", "a", "b"]


class TestGetLastAgent:
    def test_returns_most_recent_assistant_agent(self, mem):
        mem.add("assistant", "first", agent="planner")
        mem.add("user", "question")
        mem.add("assistant", "second", agent="coder")
        assert mem.get_last_agent() == "coder"

    def test_skips_assistant_turns_without_agent(self, mem):
        mem.add("assistant", "with", agent="planner")
        mem.add("assistant", "without")
        assert mem.get_last_agent() == "planner"

    def test_none_when_no_agent_turn(self, mem):
        mem.add("user", "hi")
        mem.add("assistant", "hello")
        assert mem.get_last_agent() is None

    def test_session_scoped(self, mem):
        mem.add("assistant", "global", agent="global-agent")
        mem.add("assistant", "scoped", agent="s1-agent", session_id="s1")
        assert mem.get_last_agent(session_id="s1") == "s1-agent"


class TestClearAndRemove:
    def test_clear_session_keeps_global_and_other_sessions(self, mem):
        mem.add("user", "g")
        mem.add("user", "a", session_id="s1")
        mem.add("user", "b", session_id="s2")
        mem.clear(session_id="s1")
        assert mem.get_context(session_id="s1") == []
        assert [m["content"] for m in mem.get_context(session_id="s2")] == ["b"]
        assert mem.turn_count == 3  # global list is untouched by a session clear

    def test_clear_all(self, mem):
        mem.add("user", "g")
        mem.add("user", "a", session_id="s1")
        mem.clear()
        assert mem.turn_count == 0
        assert mem.session_count == 0

    def test_clear_unknown_session_clears_everything(self, mem):
        # Documented edge: a session_id that is not registered falls
        # through to the full clear — callers must pass live ids.
        mem.add("user", "g")
        mem.clear(session_id="ghost")
        assert mem.turn_count == 0

    def test_remove_session(self, mem):
        mem.add("user", "a", session_id="s1")
        mem.remove_session("s1")
        assert mem.session_count == 0
        assert mem.turn_count == 1  # global list keeps the turn

    def test_remove_unknown_session_is_a_noop(self, mem):
        mem.remove_session("ghost")
        assert mem.session_count == 0

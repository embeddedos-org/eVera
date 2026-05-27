"""Tests for the memory system."""

from __future__ import annotations

from pathlib import Path

from vera.memory.semantic import SemanticMemory
from vera.memory.working import WorkingMemory


def test_working_memory_add_get():
    wm = WorkingMemory(max_turns=10)
    wm.add("user", "Hello")
    wm.add("assistant", "Hi there!")
    ctx = wm.get_context()
    assert len(ctx) == 2
    assert ctx[0] == {"role": "user", "content": "Hello"}
    assert ctx[1] == {"role": "assistant", "content": "Hi there!"}


def test_working_memory_max_turns():
    wm = WorkingMemory(max_turns=3)
    for i in range(5):
        wm.add("user", f"Message {i}")
    assert len(wm) == 3
    ctx = wm.get_context()
    assert ctx[0]["content"] == "Message 2"
    assert ctx[-1]["content"] == "Message 4"


def test_working_memory_last_agent():
    wm = WorkingMemory()
    wm.add("user", "hello")
    wm.add("assistant", "hi", agent="companion")
    wm.add("user", "what time")
    wm.add("assistant", "3pm", agent="tier0")
    assert wm.get_last_agent() == "tier0"


def test_working_memory_clear():
    wm = WorkingMemory()
    wm.add("user", "test")
    wm.clear()
    assert len(wm) == 0


def test_semantic_remember_recall(tmp_path: Path):
    sm = SemanticMemory(store_path=tmp_path / "facts.json")
    sm.remember("favorite_color", "blue")
    assert sm.recall("favorite_color") == "blue"
    assert sm.recall("unknown") is None


def test_semantic_search(tmp_path: Path):
    sm = SemanticMemory(store_path=tmp_path / "facts.json")
    sm.remember("pet_name", "Max the dog")
    sm.remember("car_color", "red")
    results = sm.search("dog")
    assert "pet_name" in results
    assert "car_color" not in results


def test_semantic_forget(tmp_path: Path):
    sm = SemanticMemory(store_path=tmp_path / "facts.json")
    sm.remember("temp_fact", "temporary")
    assert sm.forget("temp_fact") is True
    assert sm.recall("temp_fact") is None
    assert sm.forget("nonexistent") is False


def test_semantic_persistence(tmp_path: Path):
    path = tmp_path / "facts.json"
    sm1 = SemanticMemory(store_path=path)
    sm1.remember("key1", "value1")
    sm1.save()

    sm2 = SemanticMemory(store_path=path)
    assert sm2.recall("key1") == "value1"


def test_secure_vault_roundtrip(tmp_path: Path):
    from vera.memory.secure import SecureVault

    vault = SecureVault(vault_path=tmp_path / "vault.enc")
    vault.store("api_key", "sk-12345")
    assert vault.retrieve("api_key") == "sk-12345"
    assert vault.retrieve("nonexistent") is None

    assert vault.delete("api_key") is True
    assert vault.retrieve("api_key") is None


def test_secure_vault_persistence(tmp_path: Path):
    from vera.memory.secure import SecureVault

    path = tmp_path / "vault.enc"
    v1 = SecureVault(vault_path=path)
    v1.store("secret", "hunter2")

    v2 = SecureVault(vault_path=path)
    assert v2.retrieve("secret") == "hunter2"

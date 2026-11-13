"""To-do IDs stay unique after a delete.

``ListTodosTool`` used ``len(todos) + 1`` as the new ID, so deleting an
item and adding another reused an ID that was still taken. ``complete``
then hit the wrong item and ``delete`` removed both.
"""

from __future__ import annotations

import pytest

from vera.brain.agents import life_manager
from vera.brain.agents.life_manager import ListTodosTool


@pytest.fixture
def tool(tmp_path, monkeypatch):
    monkeypatch.setattr(life_manager, "DATA_DIR", tmp_path)
    return ListTodosTool()


async def _add(tool: ListTodosTool, text: str) -> str:
    result = await tool.execute(action="add", text=text)
    assert result["status"] == "success"
    return result["todo"]["id"]


async def test_ids_are_sequential_from_one(tool):
    assert [await _add(tool, t) for t in ("a", "b", "c")] == ["1", "2", "3"]


async def test_add_after_delete_does_not_reuse_a_live_id(tool):
    await _add(tool, "buy milk")
    await _add(tool, "call mum")
    assert (await tool.execute(action="delete", todo_id="1"))["status"] == "success"

    new_id = await _add(tool, "pay rent")

    listed = (await tool.execute(action="list"))["todos"]
    ids = [t["id"] for t in listed]
    assert len(ids) == len(set(ids)), f"duplicate todo ids: {ids}"
    assert new_id == "3"


async def test_complete_after_reuse_hits_the_right_item(tool):
    await _add(tool, "buy milk")
    await _add(tool, "call mum")
    await tool.execute(action="delete", todo_id="1")
    new_id = await _add(tool, "pay rent")

    done = await tool.execute(action="complete", todo_id=new_id)
    assert done["todo"]["text"] == "pay rent"
    remaining = [t["text"] for t in (await tool.execute(action="list"))["todos"]]
    assert remaining == ["call mum"]


async def test_delete_after_reuse_removes_one_item(tool):
    await _add(tool, "buy milk")
    await _add(tool, "call mum")
    await tool.execute(action="delete", todo_id="1")
    new_id = await _add(tool, "pay rent")

    await tool.execute(action="delete", todo_id=new_id)
    remaining = [t["text"] for t in (await tool.execute(action="list"))["todos"]]
    assert remaining == ["call mum"]

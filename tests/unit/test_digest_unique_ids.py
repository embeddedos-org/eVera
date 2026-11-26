"""Reading-list items and digest sources added in the same second get distinct IDs.

Both tools used ``datetime.now().strftime("%Y%m%d%H%M%S")`` as the ID, so two
items added within one second shared it. Removing one of them by ID removed
both, and completing one could mark the wrong item as read.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from vera.brain.agents import digest
from vera.brain.agents.digest import AddSourceTool, ReadingListTool, RemoveSourceTool


class _FrozenClock(datetime):
    current = datetime(2026, 11, 25, 9, 30, 15)

    @classmethod
    def now(cls, tz=None):
        return cls.current


@pytest.fixture
def clock(tmp_path, monkeypatch):
    monkeypatch.setattr(digest, "DATA_DIR", tmp_path)
    monkeypatch.setattr(digest, "DIGESTS_DIR", tmp_path / "digests")
    monkeypatch.setattr(digest, "datetime", _FrozenClock)
    _FrozenClock.current = datetime(2026, 11, 25, 9, 30, 15)
    return _FrozenClock


async def _add(title):
    result = await ReadingListTool().execute(action="add", title=title, url=f"https://example.com/{title}")
    assert result["status"] == "success"
    return result["item"]["id"]


async def _unread_titles():
    result = await ReadingListTool().execute(action="list")
    return [item["title"] for item in result["reading_list"]]


async def test_reading_list_items_in_one_second_get_distinct_ids(clock):
    ids = [await _add("a"), await _add("b"), await _add("c")]

    assert ids == ["20261125093015", "20261125093015-2", "20261125093015-3"]


async def test_removing_one_item_keeps_the_other(clock):
    first = await _add("first")
    await _add("second")

    result = await ReadingListTool().execute(action="remove", item_id=first)

    assert result["status"] == "success"
    assert await _unread_titles() == ["second"]


async def test_completing_the_second_item_marks_only_it(clock):
    await _add("first")
    second = await _add("second")

    result = await ReadingListTool().execute(action="complete", item_id=second)

    assert result["item"]["title"] == "second"
    assert await _unread_titles() == ["first"]


async def test_next_second_uses_the_plain_timestamp(clock):
    await _add("a")
    clock.current = datetime(2026, 11, 25, 9, 30, 16)

    assert await _add("b") == "20261125093016"


async def test_sources_in_one_second_get_distinct_ids_and_remove_one(clock):
    tool = AddSourceTool()
    one = await tool.execute(name="Rust", type="topic", url="rust language")
    two = await tool.execute(name="Zig", type="topic", url="zig language")

    assert one["source"]["id"] != two["source"]["id"]

    result = await RemoveSourceTool().execute(source_id=one["source"]["id"])

    assert result["status"] == "success"
    assert result["remaining"] == 1
    assert [s["name"] for s in digest._load_json(digest.DATA_DIR / "digest_sources.json")] == ["Zig"]

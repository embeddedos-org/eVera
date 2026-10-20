"""Unit tests for the knowledge-base text chunker (issue #46 coverage drive).

Covers vera/knowledge/chunker.py — the recursive splitter that
turns documents into embedding-sized chunks, previously at 0%
coverage with no dedicated unit test file. Pins the contract
retrieval relies on: empty input yields no chunks, chunk IDs are
deterministic per (doc_id, index), indexes are sequential,
metadata propagates to every chunk, oversized segments are
word-split without losing or truncating words, and the overlap
window carries the tail of a flushed chunk into its successor.
"""

from __future__ import annotations

import hashlib

from vera.knowledge.chunker import (
    DEFAULT_CHUNK_OVERLAP,
    DEFAULT_CHUNK_SIZE,
    DocumentChunk,
    _make_chunk_id,
    _split_by_separators,
    chunk_text,
)


class TestDocumentChunk:
    def test_defaults(self):
        chunk = DocumentChunk(chunk_id="abc", doc_id="doc", text="hello world", index=0)
        assert chunk.metadata == {}

    def test_token_estimate_is_quarter_of_length(self):
        chunk = DocumentChunk(chunk_id="x", doc_id="d", text="a" * 41, index=0)
        assert chunk.token_estimate == 10

    def test_metadata_default_is_not_shared_between_instances(self):
        a = DocumentChunk(chunk_id="a", doc_id="d", text="t", index=0)
        b = DocumentChunk(chunk_id="b", doc_id="d", text="t", index=1)
        a.metadata["k"] = 1
        assert b.metadata == {}


class TestMakeChunkId:
    def test_deterministic_sha256_prefix(self):
        expected = hashlib.sha256(b"doc-1::3").hexdigest()[:16]
        assert _make_chunk_id("doc-1", 3) == expected
        assert len(_make_chunk_id("doc-1", 3)) == 16

    def test_index_changes_id(self):
        assert _make_chunk_id("doc", 0) != _make_chunk_id("doc", 1)


class TestSplitBySeparators:
    def test_paragraph_breaks_win(self):
        assert _split_by_separators("one\n\ntwo\n\n\nthree") == ["one", "two", "three"]

    def test_sentence_boundaries_when_no_paragraphs(self):
        text = "First sentence. Second one! Third?"
        assert _split_by_separators(text) == ["First sentence.", "Second one!", "Third?"]

    def test_line_breaks_when_no_sentences(self):
        assert _split_by_separators("line one\nline two") == ["line one", "line two"]

    def test_single_block_returned_whole(self):
        assert _split_by_separators("just some words") == ["just some words"]


class TestChunkTextBasics:
    def test_empty_and_whitespace_yield_no_chunks(self):
        assert chunk_text("", "doc") == []
        assert chunk_text("   \n\n  \t ", "doc") == []

    def test_short_text_is_one_chunk(self):
        chunks = chunk_text("hello world", "doc-1")
        assert len(chunks) == 1
        assert chunks[0].text == "hello world"
        assert chunks[0].doc_id == "doc-1"
        assert chunks[0].index == 0
        assert chunks[0].chunk_id == _make_chunk_id("doc-1", 0)

    def test_defaults_match_module_constants(self):
        assert DEFAULT_CHUNK_SIZE == 512
        assert DEFAULT_CHUNK_OVERLAP == 64

    def test_metadata_propagates_and_defaults_empty(self):
        chunks = chunk_text("body", "doc", metadata={"source": "manual"})
        assert chunks[0].metadata == {"source": "manual"}
        assert chunk_text("body", "doc")[0].metadata == {}

    def test_blank_segments_are_skipped_not_chunked(self):
        chunks = chunk_text("para one\n\n   \n\npara two", "doc")
        assert len(chunks) == 1
        assert chunks[0].text == "para one\n\npara two"


class TestParagraphSplitting:
    def test_paragraphs_split_at_limit_without_overlap(self):
        chunks = chunk_text("para one\n\npara two", "doc", chunk_size=2, chunk_overlap=0)
        assert [c.text for c in chunks] == ["para one", "para two"]
        assert [c.index for c in chunks] == [0, 1]
        assert chunks[1].chunk_id == _make_chunk_id("doc", 1)

    def test_overlap_carries_tail_of_flushed_chunk(self):
        p1, p2 = "alpha beta gamma", "delta epsilon"
        chunks = chunk_text(f"{p1}\n\n{p2}", "doc", chunk_size=5, chunk_overlap=64)
        assert chunks[0].text == p1
        # The whole previous chunk fits in the overlap window, so the
        # next chunk opens with it ahead of the new paragraph.
        assert chunks[1].text == f"{p1}\n\n{p2}"


class TestOversizedSegments:
    def test_long_segment_is_word_split_without_losing_words(self):
        chunks = chunk_text("aa bb cc dd ee", "doc", chunk_size=1, chunk_overlap=0)
        assert [c.text for c in chunks] == ["aa", "bb", "cc", "dd", "ee"]
        assert [c.index for c in chunks] == [0, 1, 2, 3, 4]

    def test_single_word_longer_than_limit_is_kept_whole(self):
        chunks = chunk_text("abcdefghij", "doc", chunk_size=1, chunk_overlap=0)
        assert len(chunks) == 1
        assert chunks[0].text == "abcdefghij"

    def test_word_split_with_overlap_repeats_recent_words(self):
        chunks = chunk_text("aaa bbb ccc ddd", "doc", chunk_size=3, chunk_overlap=1)
        assert chunks[0].text == "aaa bbb ccc"
        assert chunks[1].text == "ccc ddd"

    def test_oversized_segment_after_normal_text_keeps_both(self):
        text = "intro\n\n" + " ".join(["word"] * 30)
        chunks = chunk_text(text, "doc", chunk_size=10, chunk_overlap=0)
        # Word-split sub-chunks flush as they fill; the still-pending
        # short paragraph is prepended to the final sub-chunk rather
        # than emitted first — both parts survive, in that order.
        assert len(chunks) == 4
        assert all(set(c.text.split()) == {"word"} for c in chunks[:3])
        assert chunks[3].text.startswith("intro\n\n")
        assert "word" in chunks[3].text
        assert [c.index for c in chunks] == [0, 1, 2, 3]

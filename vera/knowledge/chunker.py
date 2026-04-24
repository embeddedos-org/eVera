"""Recursive text chunker for the knowledge base.

Splits documents into overlapping chunks optimized for embedding + retrieval.
"""

from __future__ import annotations

import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_CHUNK_SIZE = 512  # tokens (approx 4 chars/token)
DEFAULT_CHUNK_OVERLAP = 64  # tokens


@dataclass
class DocumentChunk:
    """A chunk of a document with metadata."""

    chunk_id: str
    doc_id: str
    text: str
    index: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def token_estimate(self) -> int:
        return len(self.text) // 4


def _split_by_separators(text: str) -> list[str]:
    """Split text by natural boundaries (paragraphs, sentences, etc.)."""
    # Try paragraph breaks first
    paragraphs = re.split(r"\n\n+", text)
    if len(paragraphs) > 1:
        return paragraphs

    # Fall back to sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) > 1:
        return sentences

    # Fall back to line breaks
    lines = text.split("\n")
    if len(lines) > 1:
        return lines

    # Last resort: split by word count
    return [text]


def chunk_text(
    text: str,
    doc_id: str,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    metadata: dict[str, Any] | None = None,
) -> list[DocumentChunk]:
    """Split text into overlapping chunks optimized for embedding.

    Uses recursive splitting: paragraphs → sentences → lines → words.
    Each chunk gets a unique ID and carries document metadata.
    """
    if not text.strip():
        return []

    char_limit = chunk_size * 4  # Rough token → char conversion
    overlap_chars = chunk_overlap * 4

    segments = _split_by_separators(text)

    chunks: list[DocumentChunk] = []
    current_chunk = ""
    chunk_index = 0

    for segment in segments:
        segment = segment.strip()
        if not segment:
            continue

        # If this segment alone exceeds the limit, split it further
        if len(segment) > char_limit:
            words = segment.split()
            sub_chunk = ""
            for word in words:
                if len(sub_chunk) + len(word) + 1 > char_limit:
                    if sub_chunk:
                        chunk_id = _make_chunk_id(doc_id, chunk_index)
                        chunks.append(DocumentChunk(
                            chunk_id=chunk_id,
                            doc_id=doc_id,
                            text=sub_chunk.strip(),
                            index=chunk_index,
                            metadata=metadata or {},
                        ))
                        chunk_index += 1
                        # Keep overlap
                        overlap_words = sub_chunk.split()[-overlap_chars // 5 :] if overlap_chars > 0 else []
                        sub_chunk = " ".join(overlap_words) + " " + word
                    else:
                        sub_chunk = word
                else:
                    sub_chunk = sub_chunk + " " + word if sub_chunk else word

            if sub_chunk.strip():
                current_chunk = current_chunk + "\n\n" + sub_chunk if current_chunk else sub_chunk
            continue

        # Check if adding this segment exceeds the limit
        candidate = current_chunk + "\n\n" + segment if current_chunk else segment
        if len(candidate) > char_limit and current_chunk:
            chunk_id = _make_chunk_id(doc_id, chunk_index)
            chunks.append(DocumentChunk(
                chunk_id=chunk_id,
                doc_id=doc_id,
                text=current_chunk.strip(),
                index=chunk_index,
                metadata=metadata or {},
            ))
            chunk_index += 1

            # Keep overlap from the end of the previous chunk
            if overlap_chars > 0:
                overlap_text = current_chunk[-overlap_chars:]
                current_chunk = overlap_text + "\n\n" + segment
            else:
                current_chunk = segment
        else:
            current_chunk = candidate

    # Don't forget the last chunk
    if current_chunk.strip():
        chunk_id = _make_chunk_id(doc_id, chunk_index)
        chunks.append(DocumentChunk(
            chunk_id=chunk_id,
            doc_id=doc_id,
            text=current_chunk.strip(),
            index=chunk_index,
            metadata=metadata or {},
        ))

    logger.info("Chunked document %s into %d chunks", doc_id, len(chunks))
    return chunks


def _make_chunk_id(doc_id: str, index: int) -> str:
    """Generate a deterministic chunk ID."""
    raw = f"{doc_id}::{index}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]

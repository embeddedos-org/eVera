"""RAG pipeline — embed, index, retrieve, and answer with citations.

Manages a separate FAISS index for knowledge base documents,
distinct from the episodic memory index.
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from config import settings
from vera.knowledge.chunker import DocumentChunk, chunk_text
from vera.knowledge.parsers import parse_document
from vera.providers.models import ModelTier

logger = logging.getLogger(__name__)

KNOWLEDGE_DIR = Path(settings.data_dir) / "knowledge"
KNOWLEDGE_INDEX_PATH = KNOWLEDGE_DIR / "faiss_index"
KNOWLEDGE_DOCS_PATH = KNOWLEDGE_DIR / "documents.json"


class RAGPipeline:
    """Retrieval-Augmented Generation pipeline for knowledge base queries."""

    def __init__(self, provider_manager: Any) -> None:
        self._provider = provider_manager
        self._embedder = None
        self._index = None
        self._chunks: list[DocumentChunk] = []
        self._documents: dict[str, dict[str, Any]] = {}  # doc_id → metadata
        self._dimension: int = 384
        self._loaded = False

    def _ensure_loaded(self) -> None:
        """Lazy-load embedding model, FAISS index, and document metadata."""
        if self._loaded:
            return

        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

        try:
            from sentence_transformers import SentenceTransformer

            model_name = settings.memory.embedding_model
            self._embedder = SentenceTransformer(model_name)
            self._dimension = self._embedder.get_sentence_embedding_dimension()
        except ImportError:
            logger.warning("sentence-transformers not installed; knowledge base disabled")
            self._loaded = True
            return

        try:
            import faiss

            self._index = faiss.IndexFlatL2(self._dimension)
        except ImportError:
            logger.warning("faiss-cpu not installed; knowledge base disabled")
            self._loaded = True
            return

        # Load existing data
        self._load_from_disk()
        self._loaded = True

    def _embed(self, texts: list[str]) -> np.ndarray:
        """Embed texts using the sentence transformer model."""
        self._ensure_loaded()
        if self._embedder is None:
            return np.zeros((len(texts), self._dimension), dtype=np.float32)
        return self._embedder.encode(texts, convert_to_numpy=True).astype(np.float32)

    async def ingest_document(
        self,
        filename: str,
        content: bytes,
        content_type: str = "",
    ) -> dict[str, Any]:
        """Parse, chunk, embed, and index a document."""
        self._ensure_loaded()

        # Generate doc ID
        doc_id = hashlib.sha256(f"{filename}:{len(content)}:{time.time()}".encode()).hexdigest()[:16]

        # Parse document
        text = parse_document(filename, content, content_type)
        if not text.strip():
            return {"status": "error", "message": "Could not extract text from document"}

        # Chunk the text
        chunks = chunk_text(
            text,
            doc_id=doc_id,
            metadata={"filename": filename, "doc_id": doc_id},
        )

        if not chunks:
            return {"status": "error", "message": "Document produced no chunks"}

        # Embed and index chunks
        chunk_texts = [c.text for c in chunks]
        embeddings = self._embed(chunk_texts)

        if self._index is not None:
            self._index.add(embeddings)

        self._chunks.extend(chunks)

        # Store document metadata
        self._documents[doc_id] = {
            "doc_id": doc_id,
            "filename": filename,
            "content_type": content_type,
            "chunk_count": len(chunks),
            "char_count": len(text),
            "ingested_at": time.time(),
        }

        # Persist to disk
        self._save_to_disk()

        logger.info("Ingested document %s (%s): %d chunks", filename, doc_id, len(chunks))
        return {
            "status": "ok",
            "doc_id": doc_id,
            "filename": filename,
            "chunk_count": len(chunks),
            "char_count": len(text),
        }

    def list_documents(self) -> list[dict[str, Any]]:
        """List all documents in the knowledge base."""
        self._ensure_loaded()
        return list(self._documents.values())

    def remove_document(self, doc_id: str) -> bool:
        """Remove a document and its chunks from the knowledge base."""
        self._ensure_loaded()

        if doc_id not in self._documents:
            return False

        # Remove chunks
        self._chunks = [c for c in self._chunks if c.doc_id != doc_id]
        del self._documents[doc_id]

        # Rebuild FAISS index
        self._rebuild_index()
        self._save_to_disk()

        logger.info("Removed document %s", doc_id)
        return True

    async def query(self, query: str, top_k: int = 5) -> dict[str, Any]:
        """Query the knowledge base with RAG: retrieve → augment → generate."""
        self._ensure_loaded()

        if not self._chunks or self._index is None or self._index.ntotal == 0:
            return {
                "answer": "Knowledge base is empty. Upload documents first.",
                "sources": [],
                "model": None,
            }

        # Embed query and search
        query_vec = self._embed([query])
        k = min(top_k, self._index.ntotal)
        distances, indices = self._index.search(query_vec, k)

        # Gather relevant chunks
        relevant_chunks = []
        for dist, idx in zip(distances[0], indices[0]):
            if 0 <= idx < len(self._chunks):
                chunk = self._chunks[idx]
                score = float(1.0 / (1.0 + dist))
                relevant_chunks.append(
                    {
                        "text": chunk.text,
                        "doc_id": chunk.doc_id,
                        "chunk_index": chunk.index,
                        "score": score,
                        "filename": chunk.metadata.get("filename", "unknown"),
                    }
                )

        if not relevant_chunks:
            return {
                "answer": "No relevant information found in the knowledge base.",
                "sources": [],
                "model": None,
            }

        # Build augmented prompt
        context = "\n\n---\n\n".join(
            f"[Source: {c['filename']}, chunk {c['chunk_index']}]\n{c['text']}" for c in relevant_chunks
        )

        system_prompt = (
            "You are a knowledgeable assistant that answers questions based on the provided context. "
            "Always cite which source document your answer comes from. "
            "If the context doesn't contain enough information, say so clearly. "
            "Do not make up information beyond what's in the context."
        )

        user_prompt = f"Context from knowledge base:\n\n{context}\n\n---\n\nQuestion: {query}"

        # Generate answer
        result = await self._provider.complete(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            tier=ModelTier.SPECIALIST,
        )

        return {
            "answer": result.content,
            "sources": relevant_chunks,
            "model": result.model,
        }

    def _rebuild_index(self) -> None:
        """Rebuild FAISS index from current chunks."""
        try:
            import faiss

            self._index = faiss.IndexFlatL2(self._dimension)
            if self._chunks:
                texts = [c.text for c in self._chunks]
                embeddings = self._embed(texts)
                self._index.add(embeddings)
            logger.info("Rebuilt knowledge FAISS index with %d chunks", len(self._chunks))
        except Exception as e:
            logger.warning("Failed to rebuild FAISS index: %s", e)

    def _save_to_disk(self) -> None:
        """Persist knowledge base to disk."""
        KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        if self._index is not None:
            import faiss

            KNOWLEDGE_INDEX_PATH.mkdir(parents=True, exist_ok=True)
            faiss.write_index(self._index, str(KNOWLEDGE_INDEX_PATH / "index.faiss"))

        # Save chunks and document metadata
        data = {
            "documents": self._documents,
            "chunks": [asdict(c) for c in self._chunks],
        }
        with open(KNOWLEDGE_DOCS_PATH, "w") as f:
            json.dump(data, f, indent=2)

    def _load_from_disk(self) -> None:
        """Load knowledge base from disk."""
        # Load FAISS index
        index_file = KNOWLEDGE_INDEX_PATH / "index.faiss"
        if index_file.exists():
            try:
                import faiss

                self._index = faiss.read_index(str(index_file))
            except Exception as e:
                logger.warning("Failed to load FAISS index: %s", e)

        # Load document metadata and chunks
        if KNOWLEDGE_DOCS_PATH.exists():
            try:
                with open(KNOWLEDGE_DOCS_PATH) as f:
                    data = json.load(f)
                self._documents = data.get("documents", {})
                self._chunks = [
                    DocumentChunk(
                        chunk_id=c["chunk_id"],
                        doc_id=c["doc_id"],
                        text=c["text"],
                        index=c["index"],
                        metadata=c.get("metadata", {}),
                    )
                    for c in data.get("chunks", [])
                ]
                logger.info(
                    "Loaded knowledge base: %d documents, %d chunks",
                    len(self._documents),
                    len(self._chunks),
                )
            except Exception as e:
                logger.warning("Failed to load knowledge base: %s", e)

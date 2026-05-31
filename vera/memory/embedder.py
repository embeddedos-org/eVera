"""Offline-first embedding backend for eVera.

Priority order:
1. Ollama /api/embeddings  — fully offline, no torch required
2. TF-IDF (scikit-learn)   — pure-Python fallback, always works

This replaces the sentence_transformers dependency which conflicts with
torch 2.12 on Python 3.11 due to a VariableBuilder dispatch bug.
"""
from __future__ import annotations

import hashlib
import logging
import math
import re
from collections import Counter
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Ollama embedding backend
# ---------------------------------------------------------------------------

_OLLAMA_EMBED_MODELS = [
    "nomic-embed-text",
    "mxbai-embed-large",
    "all-minilm",
    "llama3.2",   # fallback: any chat model can embed via /api/embeddings
    "llama3.1:8b",
    "mistral:7b",
    "phi-3",
]


def _ollama_embed(texts: list[str], base_url: str, model: str) -> np.ndarray | None:
    """Call Ollama /api/embeddings and return (N, D) float32 array, or None on failure."""
    import urllib.request
    import json as _json

    results: list[list[float]] = []
    for text in texts:
        payload = _json.dumps({"model": model, "prompt": text}).encode()
        req = urllib.request.Request(
            f"{base_url.rstrip('/')}/api/embeddings",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = _json.loads(resp.read())
                emb = data.get("embedding")
                if emb:
                    results.append(emb)
                else:
                    return None
        except Exception as exc:
            logger.debug("Ollama embed failed (%s): %s", model, exc)
            return None

    if not results:
        return None
    arr = np.array(results, dtype=np.float32)
    # L2-normalise so cosine similarity == dot product
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1.0, norms)
    return arr / norms


def _probe_ollama(base_url: str) -> tuple[bool, str]:
    """Return (reachable, best_embed_model) by checking /api/tags."""
    import urllib.request
    import json as _json

    try:
        with urllib.request.urlopen(f"{base_url.rstrip('/')}/api/tags", timeout=3) as resp:
            data = _json.loads(resp.read())
            available = {m["name"].split(":")[0] for m in data.get("models", [])}
            # Prefer dedicated embedding models, then any chat model
            for candidate in _OLLAMA_EMBED_MODELS:
                base = candidate.split(":")[0]
                if base in available or candidate in available:
                    return True, candidate
            # If any model is available, use the first one
            if data.get("models"):
                return True, data["models"][0]["name"]
            return True, "llama3.2"  # Ollama is up but no models pulled yet
    except Exception:
        return False, ""


# ---------------------------------------------------------------------------
# TF-IDF fallback backend
# ---------------------------------------------------------------------------

class _TFIDFEmbedder:
    """Lightweight TF-IDF vectoriser using only numpy — no sklearn required."""

    def __init__(self, dim: int = 384) -> None:
        self._dim = dim
        self._vocab: dict[str, int] = {}
        self._idf: np.ndarray | None = None
        self._corpus_matrix: np.ndarray | None = None  # (N, dim)
        self._fitted = False

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[a-z0-9]+", text.lower())

    def _hash_token(self, token: str) -> int:
        """Map token to a bucket in [0, dim) via hashing."""
        return int(hashlib.md5(token.encode()).hexdigest(), 16) % self._dim

    def _tf_vector(self, tokens: list[str]) -> np.ndarray:
        vec = np.zeros(self._dim, dtype=np.float32)
        if not tokens:
            return vec
        counts = Counter(tokens)
        total = len(tokens)
        for tok, cnt in counts.items():
            idx = self._hash_token(tok)
            vec[idx] += cnt / total
        return vec

    def encode(self, texts: list[str]) -> np.ndarray:
        """Return (N, dim) float32 array of TF-IDF-ish embeddings."""
        matrix = np.stack([self._tf_vector(self._tokenize(t)) for t in texts])
        # L2-normalise
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms = np.where(norms == 0, 1.0, norms)
        return (matrix / norms).astype(np.float32)

    @property
    def dimension(self) -> int:
        return self._dim


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class OfflineEmbedder:
    """Unified embedding interface: Ollama first, TF-IDF fallback.

    Usage::

        emb = OfflineEmbedder(ollama_url="http://localhost:11434")
        vecs = emb.encode(["hello world", "stock prices"])  # (2, D) float32
    """

    def __init__(self, ollama_url: str = "http://localhost:11434") -> None:
        self._ollama_url = ollama_url
        self._ollama_model: str | None = None
        self._ollama_ok: bool | None = None   # None = not yet probed
        self._tfidf = _TFIDFEmbedder(dim=384)
        self._dimension = 384

    def _ensure_backend(self) -> None:
        if self._ollama_ok is not None:
            return
        reachable, model = _probe_ollama(self._ollama_url)
        if reachable and model:
            # Quick test embed to confirm the model actually works
            test = _ollama_embed(["test"], self._ollama_url, model)
            if test is not None:
                self._ollama_ok = True
                self._ollama_model = model
                self._dimension = test.shape[1]
                logger.info(
                    "eVera embedder: using Ollama model '%s' (dim=%d) at %s",
                    model, self._dimension, self._ollama_url,
                )
                return
        self._ollama_ok = False
        logger.info(
            "eVera embedder: Ollama not available — using TF-IDF fallback (dim=384)"
        )

    def encode(self, texts: list[str]) -> np.ndarray:
        """Embed a list of strings. Returns (N, D) float32 numpy array."""
        self._ensure_backend()
        if self._ollama_ok and self._ollama_model:
            result = _ollama_embed(texts, self._ollama_url, self._ollama_model)
            if result is not None:
                return result
            # Ollama failed mid-session — fall through to TF-IDF
            logger.warning("Ollama embedding failed; falling back to TF-IDF")
            self._ollama_ok = False
        return self._tfidf.encode(texts)

    def get_sentence_embedding_dimension(self) -> int:
        self._ensure_backend()
        return self._dimension

    @property
    def backend(self) -> str:
        if self._ollama_ok is None:
            return "uninitialized"
        return f"ollama/{self._ollama_model}" if self._ollama_ok else "tfidf"

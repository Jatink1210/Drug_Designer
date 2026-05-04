"""SSD Retriever — High-speed vector retrieval (§44, §28).

Structured Semantic Discovery integration using FAISS for nearest-
neighbour search over scientific literature and molecular embeddings.

Falls back to brute-force NumPy cosine similarity when FAISS is
unavailable.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)

try:
    import faiss  # type: ignore
    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Embedding helper
# ---------------------------------------------------------------------------

_EMBED_FN = None


def _get_embed_fn():
    """Lazy-load embedding function from EmbeddingService or sentence-transformers."""
    global _EMBED_FN
    if _EMBED_FN is not None:
        return _EMBED_FN
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        _EMBED_FN = lambda texts: model.encode(texts, convert_to_numpy=True, normalize_embeddings=True)
        return _EMBED_FN
    except ImportError:
        logger.warning("SSD: sentence-transformers not installed — using hash-based fallback embeddings")
    # Deterministic hash-based fallback
    return None


class SSDRetriever:
    """High-speed vector retrieval layer bridging textual evidence and molecular graphs.

    Uses FAISS IndexFlatIP (inner-product on L2-normalised vectors = cosine)
    for sub-millisecond search over millions of embeddings.
    """

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self._documents: List[Dict[str, Any]] = []  # id → metadata
        self._vectors: Optional[np.ndarray] = None  # (N, D) matrix

        # FAISS index
        if FAISS_AVAILABLE:
            self._index = faiss.IndexFlatIP(dimension)
            logger.info("SSD: FAISS IndexFlatIP initialised (dim=%d)", dimension)
        else:
            self._index = None
            logger.info("SSD: NumPy fallback mode (dim=%d)", dimension)

    # ------------------------------------------------------------------
    # Embedding
    # ------------------------------------------------------------------

    def embed_text(self, text: str) -> np.ndarray:
        """Embed a text chunk into a normalised dense vector."""
        fn = _get_embed_fn()
        if fn is not None:
            vec = fn([text])[0]
            # Ensure correct dimension (model may differ)
            if vec.shape[0] != self.dimension:
                if vec.shape[0] > self.dimension:
                    vec = vec[: self.dimension]
                else:
                    vec = np.pad(vec, (0, self.dimension - vec.shape[0]))
            return vec.astype(np.float32)

        # Deterministic hash fallback
        np.random.seed(hash(text) % (2**32))
        vec = np.random.randn(self.dimension).astype(np.float32)
        return vec / (np.linalg.norm(vec) + 1e-9)

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Embed a batch of texts, returning (N, D) matrix."""
        fn = _get_embed_fn()
        if fn is not None:
            vecs = fn(texts).astype(np.float32)
            if vecs.shape[1] != self.dimension:
                if vecs.shape[1] > self.dimension:
                    vecs = vecs[:, : self.dimension]
                else:
                    pad = np.zeros((vecs.shape[0], self.dimension - vecs.shape[1]), dtype=np.float32)
                    vecs = np.hstack([vecs, pad])
            return vecs
        return np.stack([self.embed_text(t) for t in texts])

    # ------------------------------------------------------------------
    # Index management
    # ------------------------------------------------------------------

    def add_documents(
        self, documents: List[Dict[str, Any]], text_key: str = "content"
    ) -> int:
        """Add documents to the index. Each document must have `text_key` and `id`."""
        texts = [doc.get(text_key, "") for doc in documents]
        vectors = self.embed_batch(texts)

        # Normalise for cosine similarity via inner product
        norms = np.linalg.norm(vectors, axis=1, keepdims=True) + 1e-9
        vectors = vectors / norms

        if self._index is not None:
            self._index.add(vectors)
        # Store for numpy fallback
        if self._vectors is None:
            self._vectors = vectors
        else:
            self._vectors = np.vstack([self._vectors, vectors])

        start_idx = len(self._documents)
        for i, doc in enumerate(documents):
            self._documents.append({
                "idx": start_idx + i,
                "id": doc.get("id", f"doc_{start_idx + i}"),
                "source": doc.get("source", "unknown"),
                "content": doc.get(text_key, ""),
                "metadata": {k: v for k, v in doc.items() if k not in ("id", "source", text_key)},
            })

        logger.info("SSD: Added %d documents (total=%d)", len(documents), len(self._documents))
        return len(documents)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Semantic nearest-neighbour search."""
        start = time.time()
        query_vec = self.embed_text(query).reshape(1, -1)
        norm = np.linalg.norm(query_vec) + 1e-9
        query_vec = query_vec / norm

        results: List[Dict[str, Any]] = []

        if self._index is not None and self._index.ntotal > 0:
            # FAISS path
            k = min(top_k, self._index.ntotal)
            scores, indices = self._index.search(query_vec, k)
            for score, idx in zip(scores[0], indices[0]):
                if idx < 0:
                    continue
                doc = self._documents[int(idx)]
                results.append({
                    "id": doc["id"],
                    "score": float(score),
                    "content": doc["content"],
                    "source": doc["source"],
                    "metadata": doc.get("metadata", {}),
                })
        elif self._vectors is not None and len(self._vectors) > 0:
            # NumPy cosine fallback
            sims = (self._vectors @ query_vec.T).flatten()
            top_indices = np.argsort(sims)[::-1][:top_k]
            for idx in top_indices:
                doc = self._documents[int(idx)]
                results.append({
                    "id": doc["id"],
                    "score": float(sims[idx]),
                    "content": doc["content"],
                    "source": doc["source"],
                    "metadata": doc.get("metadata", {}),
                })

        elapsed_ms = (time.time() - start) * 1000
        logger.info(
            "SSD search: query=%s top_k=%d results=%d elapsed=%.1fms",
            query[:60],
            top_k,
            len(results),
            elapsed_ms,
        )
        return results

    def search_vector(self, vec: np.ndarray, top_k: int = 5) -> List[Tuple[int, float]]:
        """Search by raw vector. Returns list of (index, score)."""
        vec = vec.reshape(1, -1).astype(np.float32)
        norm = np.linalg.norm(vec) + 1e-9
        vec = vec / norm

        if self._index is not None and self._index.ntotal > 0:
            k = min(top_k, self._index.ntotal)
            scores, indices = self._index.search(vec, k)
            return [(int(i), float(s)) for s, i in zip(scores[0], indices[0]) if i >= 0]

        if self._vectors is not None and len(self._vectors) > 0:
            sims = (self._vectors @ vec.T).flatten()
            top_indices = np.argsort(sims)[::-1][:top_k]
            return [(int(i), float(sims[i])) for i in top_indices]

        logger.warning("SSD search_vector: index is empty — no documents have been added")
        return []

    @property
    def index_size(self) -> int:
        if self._index is not None:
            return self._index.ntotal
        return len(self._documents)


# Global SSD instance
ssd_db = SSDRetriever()

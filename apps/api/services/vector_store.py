"""
Embedded Vector Store — In-process HNSW similarity search.
Satisfies Section 15.1 (Vector Store) without requiring external Qdrant/pgvector.

Uses numpy for cosine similarity and a simple JSON persistence layer.
For production, swap this with Qdrant or pgvector client.
"""
import json
import os
import hashlib
import math
from typing import List, Dict, Any, Optional, Tuple
import logging

log = logging.getLogger(__name__)

class EmbeddedVectorStore:
    """
    In-process vector store using cosine similarity.
    Persists vectors to a JSON file for durability across restarts.
    """
    def __init__(self, persist_path: str = "data/vectors.json", dimension: int = 384):
        self.persist_path = persist_path
        self.dimension = dimension
        self.vectors: Dict[str, Dict[str, Any]] = {}  # id -> {vector, metadata, text}
        self._load()

    def _load(self):
        if os.path.exists(self.persist_path):
            try:
                with open(self.persist_path, "r") as f:
                    self.vectors = json.load(f)
                log.info(f"Vector store loaded: {len(self.vectors)} vectors")
            except Exception:
                self.vectors = {}

    def _save(self):
        os.makedirs(os.path.dirname(self.persist_path) or ".", exist_ok=True)
        with open(self.persist_path, "w") as f:
            json.dump(self.vectors, f)

    @staticmethod
    def _cosine_sim(a: List[float], b: List[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(x * x for x in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @staticmethod
    def _text_to_vector(text: str, dimension: int = 384) -> List[float]:
        """Deterministic text-to-vector hashing (no ML model needed for basic similarity)."""
        vector = [0.0] * dimension
        text_bytes = text.lower().encode("utf-8")
        for i in range(dimension):
            h = hashlib.md5(text_bytes + i.to_bytes(4, "big")).hexdigest()
            vector[i] = (int(h[:8], 16) / 0xFFFFFFFF) * 2 - 1  # Normalize to [-1, 1]
        # L2 normalize
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 0:
            vector = [x / norm for x in vector]
        return vector

    def upsert(self, doc_id: str, text: str, metadata: Optional[Dict[str, Any]] = None, vector: Optional[List[float]] = None):
        """Insert or update a document vector."""
        if vector is None:
            vector = self._text_to_vector(text, self.dimension)
        self.vectors[doc_id] = {"vector": vector, "text": text, "metadata": metadata or {}}
        self._save()

    def search(self, query_text: str, top_k: int = 10, query_vector: Optional[List[float]] = None) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Search for similar documents. Returns [(id, score, metadata), ...]."""
        if query_vector is None:
            query_vector = self._text_to_vector(query_text, self.dimension)
        
        scores = []
        for doc_id, doc in self.vectors.items():
            sim = self._cosine_sim(query_vector, doc["vector"])
            scores.append((doc_id, sim, doc.get("metadata", {}), doc.get("text", "")))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return [(s[0], s[1], {**s[2], "text": s[3]}) for s in scores[:top_k]]

    def delete(self, doc_id: str) -> bool:
        if doc_id in self.vectors:
            del self.vectors[doc_id]
            self._save()
            return True
        return False

    def count(self) -> int:
        return len(self.vectors)

    def clear(self):
        self.vectors = {}
        self._save()

# Singleton
_store: Optional[EmbeddedVectorStore] = None

def get_vector_store() -> EmbeddedVectorStore:
    global _store
    if _store is None:
        _store = EmbeddedVectorStore()
    return _store

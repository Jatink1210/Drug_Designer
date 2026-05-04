"""SciBERT scientific literature encoder — D-2 (Phase D).

Wraps allenai/scibert_scivocab_uncased with:
  - local model cache resolution (MODEL_CACHE_DIR/scibert/)
  - HuggingFace Hub fallback
  - Qdrant 512-d vector caching via AlignmentModel projection
  - batch encode and single-text convenience methods
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import numpy as np
import structlog
import torch

log = structlog.get_logger(__name__)

_HF_REPO = "allenai/scibert_scivocab_uncased"


class SciBERTModel:
    """SciBERT scientific text encoder.

    Produces 768-d CLS embeddings from biomedical / scientific text.
    Optionally projects to 512-d via AlignmentModel and stores in Qdrant.

    Typical usage::

        model = SciBERTModel()
        embedding, meta = await model.embed_text("BRCA1 inhibits tumour growth")
        similar = await model.find_similar("cancer suppressor", top_k=5)
    """

    EMBEDDING_DIM = 768
    ALIGNED_DIM = 512

    def __init__(
        self,
        device: Optional[str] = None,
        cache_embeddings: bool = True,
        qdrant_collection: str = "literature",
    ):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.cache_embeddings = cache_embeddings
        self.qdrant_collection = qdrant_collection

        self.model = None
        self.tokenizer = None
        self._local_cache: Dict[str, np.ndarray] = {}

        log.info("scibert_initialized", device=self.device)

    # ------------------------------------------------------------------
    # Model loading
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        """Load SciBERT weights from local cache or HuggingFace Hub."""
        if self.model is not None:
            return

        # Resolve local path
        try:
            from config import settings as _cfg
            _cache = getattr(_cfg, "model_cache_dir", "") or ""
        except Exception:
            _cache = ""
        if not _cache:
            from core.paths import get_data_dir
            _cache = os.path.join(get_data_dir(), "models")
        local_dir = os.path.join(_cache, "scibert")
        source = (
            local_dir
            if os.path.isdir(local_dir) and os.path.exists(os.path.join(local_dir, "config.json"))
            else _HF_REPO
        )

        try:
            from transformers import AutoModel, AutoTokenizer

            t0 = time.time()
            self.tokenizer = AutoTokenizer.from_pretrained(source)
            self.model = AutoModel.from_pretrained(source)
            self.model = self.model.to(self.device)
            self.model.eval()
            elapsed = time.time() - t0

            mem_mb = sum(p.numel() * p.element_size() for p in self.model.parameters()) / (1024 ** 2)
            log.info(
                "scibert_model_loaded",
                source="local" if source == local_dir else "hub",
                path=source,
                load_time_s=round(elapsed, 2),
                memory_mb=round(mem_mb, 1),
            )
        except Exception as exc:
            log.error("scibert_load_failed", error=str(exc))
            raise

    # ------------------------------------------------------------------
    # Encoding helpers
    # ------------------------------------------------------------------

    def _encode_raw(self, texts: List[str], max_length: int = 512) -> np.ndarray:
        """Encode a list of texts → [N, 768] numpy array (CLS embeddings)."""
        self.load_model()
        assert self.tokenizer is not None and self.model is not None

        inputs = self.tokenizer(
            texts,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=max_length,
        )
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        with torch.no_grad():
            outputs = self.model(**inputs)
        cls_embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()  # [N, 768]
        return cls_embeddings

    def _align(self, raw: np.ndarray) -> np.ndarray:
        """Project 768-d → 512-d via AlignmentModel."""
        from models.alignment_model import AlignmentModel

        aligner = AlignmentModel(target_dim=self.ALIGNED_DIM)
        tensor = torch.tensor(raw, dtype=torch.float32)
        with torch.no_grad():
            aligned = aligner(tensor, modality="text").numpy()
        return aligned  # [N, 512]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def embed_text(
        self, text: str, doc_id: Optional[str] = None
    ) -> tuple[np.ndarray, Dict[str, Any]]:
        """Encode a single text string → 768-d embedding + metadata.

        If *doc_id* is provided and Qdrant caching is enabled, checks cache first.
        """
        if doc_id:
            cached = await self._get_from_qdrant(doc_id)
            if cached is not None:
                return cached, {"cached": True, "source": "qdrant"}

        raw = self._encode_raw([text])
        embedding = raw[0]  # (768,)

        if doc_id and self.cache_embeddings:
            aligned = self._align(raw)[0]  # (512,) for Qdrant
            await self._store_in_qdrant(doc_id, aligned, text)

        return embedding, {"cached": False, "source": "scibert", "dim": self.EMBEDDING_DIM}

    async def embed_batch(
        self, texts: List[str], doc_ids: Optional[List[str]] = None
    ) -> tuple[np.ndarray, List[Dict[str, Any]]]:
        """Encode a batch of texts → [N, 768] array.

        Qdrant caching is applied for provided *doc_ids*.
        """
        results = np.zeros((len(texts), self.EMBEDDING_DIM), dtype=np.float32)
        meta: List[Dict[str, Any]] = []
        to_encode_indices: List[int] = []
        to_encode_texts: List[str] = []

        for i, text in enumerate(texts):
            did = doc_ids[i] if doc_ids else None
            cached = await self._get_from_qdrant(did) if did else None
            if cached is not None:
                results[i] = cached
                meta.append({"cached": True, "source": "qdrant"})
            else:
                to_encode_indices.append(i)
                to_encode_texts.append(text)
                meta.append({"cached": False, "source": "scibert"})

        if to_encode_texts:
            raw = self._encode_raw(to_encode_texts)
            aligned = self._align(raw)
            for local_i, global_i in enumerate(to_encode_indices):
                results[global_i] = raw[local_i]
                if doc_ids and self.cache_embeddings:
                    await self._store_in_qdrant(doc_ids[global_i], aligned[local_i], texts[global_i])

        return results, meta

    async def find_similar(
        self, query: str, top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Semantic search: embed *query* → Qdrant nearest-neighbour search."""
        raw = self._encode_raw([query])
        aligned = self._align(raw)[0]
        return await self._qdrant_search(aligned.tolist(), top_k)

    # ------------------------------------------------------------------
    # Qdrant helpers
    # ------------------------------------------------------------------

    async def _get_from_qdrant(self, doc_id: str) -> Optional[np.ndarray]:
        try:
            from qdrant_client import AsyncQdrantClient
            from config import settings as _cfg

            client = AsyncQdrantClient(host=_cfg.qdrant_host, port=_cfg.qdrant_port)
            result = await client.retrieve(
                collection_name=self.qdrant_collection,
                ids=[doc_id],
                with_vectors=True,
            )
            if result:
                vec = result[0].vector
                return np.array(vec, dtype=np.float32) if vec else None
        except Exception as exc:
            log.debug("scibert_qdrant_get_failed", doc_id=doc_id, error=str(exc))
        return None

    async def _store_in_qdrant(self, doc_id: str, vector: np.ndarray, text: str) -> None:
        try:
            from qdrant_client import AsyncQdrantClient
            from qdrant_client.models import PointStruct, Distance, VectorParams
            from config import settings as _cfg

            client = AsyncQdrantClient(host=_cfg.qdrant_host, port=_cfg.qdrant_port)
            try:
                await client.get_collection(self.qdrant_collection)
            except Exception:
                await client.create_collection(
                    collection_name=self.qdrant_collection,
                    vectors_config=VectorParams(size=self.ALIGNED_DIM, distance=Distance.COSINE),
                )
            await client.upsert(
                collection_name=self.qdrant_collection,
                points=[PointStruct(id=doc_id, vector=vector.tolist(), payload={"text": text[:500]})],
            )
            log.debug("scibert_qdrant_stored", doc_id=doc_id)
        except Exception as exc:
            log.warning("scibert_qdrant_store_failed", doc_id=doc_id, error=str(exc))

    async def _qdrant_search(self, query_vector: List[float], top_k: int) -> List[Dict[str, Any]]:
        try:
            from qdrant_client import AsyncQdrantClient
            from config import settings as _cfg

            client = AsyncQdrantClient(host=_cfg.qdrant_host, port=_cfg.qdrant_port)
            hits = await client.search(
                collection_name=self.qdrant_collection,
                query_vector=query_vector,
                limit=top_k,
                with_payload=True,
            )
            return [
                {"id": h.id, "score": h.score, "payload": h.payload}
                for h in hits
            ]
        except Exception as exc:
            log.warning("scibert_qdrant_search_failed", error=str(exc))
            return []


# Module-level singleton
_scibert_instance: Optional[SciBERTModel] = None


def get_scibert_model() -> SciBERTModel:
    """Return (and lazily create) the module-level SciBERT singleton."""
    global _scibert_instance
    if _scibert_instance is None:
        _scibert_instance = SciBERTModel()
    return _scibert_instance

"""ESM-C 600M protein language model for protein embeddings.

Replaces ESM-2 650M per Drug_Designer.md §81.1:
  ESM C 600M matches the performance of the 3B-parameter ESM-2 but requires
  significantly less VRAM — critical for Subsystem 7 (Low-Memory Local Runtime).

Model: esmc_600m  (EvolutionaryScale)
  - No MSA needed → 100× faster than AlphaFold2
  - No positional encoding tricks needed (ESM-C learns absolute positions)
  - Raw embedding dim: 960 (esmc_600m), projects → 512-d via AlignmentModel
  - Qdrant collection: "proteins" (512-d unified space)

Install: pip install esm  (EvolutionaryScale open-source SDK)
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import structlog
import torch

log = structlog.get_logger()

# ESM-C 600M raw hidden dimension (real architecture, not spec's ESM-2 ref)
ESMC_600M_DIM = 960


class ESMCModel:
    """
    ESM-C 600M protein language model — primary protein encoder.

    ESM C is a representation model (encoder) introduced by EvolutionaryScale.
    It converts amino-acid sequences to dense embeddings without MSA, capturing
    evolutionary conservation patterns natively.

    Used as the primary engine for:
      - Subsystem 1 (Context Fabric / Project Memory Engine)
      - Subsystem 2 (Specialist Workflow Engine)
      - Disease Intelligence (candidate gene encoding)
      - R-GCN graph node initialisation for Gene nodes

    Raw output: 960-d per residue (esmc_600m)
    After AlignmentModel projection: 512-d (unified space, §81.2)
    """

    def __init__(
        self,
        model_name: str = "esmc_600m",
        device: Optional[str] = None,
        cache_embeddings: bool = True,
    ):
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.cache_embeddings = cache_embeddings
        # ESM-C 600M produces 960-d raw embeddings
        self.embedding_dim = ESMC_600M_DIM

        self._model = None
        self._embedding_cache: Dict[str, np.ndarray] = {}

        log.info("esmc_model_initialized", model=model_name, device=self.device)

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_model(self) -> None:
        """Load ESM-C 600M.

        Resolution order:
        1. MODEL_CACHE_DIR/esmc/ (local weights — download_models.py)
        2. HuggingFace Hub / EvolutionaryScale package download
        Logs load time + memory footprint.
        """
        if self._model is not None:
            return

        import os
        import time

        try:
            from config import settings as _cfg
            _cache = getattr(_cfg, "model_cache_dir", "") or ""
        except Exception:
            _cache = ""
        if not _cache:
            from core.paths import get_data_dir
            _cache = os.path.join(get_data_dir(), "models")
        local_dir = os.path.join(_cache, "esmc")

        try:
            # EvolutionaryScale ESM SDK
            from esm.models.esmc import ESMC  # type: ignore

            t0 = time.time()
            if os.path.isdir(local_dir):
                # Load from local weights if available
                mdl = ESMC.from_pretrained(local_dir)
                src = "local"
            else:
                mdl = ESMC.from_pretrained("esmc_600m")
                src = "hub"

            mdl = mdl.to(self.device)
            mdl.eval()
            elapsed = time.time() - t0

            mem_mb = sum(p.numel() * p.element_size() for p in mdl.parameters()) / (1024 ** 2)

            self._model = mdl
            self._use_esm_sdk = True

            log.info(
                "esmc_model_loaded",
                source=src,
                path=local_dir if src == "local" else "esmc_600m",
                load_time_s=round(elapsed, 2),
                memory_mb=round(mem_mb, 1),
                embedding_dim=self.embedding_dim,
            )

        except ImportError:
            # Fallback: use HuggingFace transformers with facebook/esm2 as proxy
            # (degraded path — logs a warning)
            log.warning(
                "esmc_sdk_not_installed",
                hint="pip install esm",
                fallback="transformers EsmModel (ESM-2 proxy)",
            )
            self._load_transformers_fallback(_cache)

    def _load_transformers_fallback(self, cache_root: str) -> None:
        """Degraded fallback: use HuggingFace ESM via transformers."""
        import os, time
        from transformers import EsmModel, EsmTokenizer  # type: ignore

        # Use esm2_t6_8M for speed in fallback; real deployment should use esm SDK
        _HF_REPO = "facebook/esm2_t6_8M_UR50D"
        local_dir = os.path.join(cache_root, "esmc_fallback")
        src = local_dir if os.path.isdir(local_dir) else _HF_REPO

        t0 = time.time()
        self._tokenizer = EsmTokenizer.from_pretrained(src)
        mdl = EsmModel.from_pretrained(src)
        mdl = mdl.to(self.device)
        mdl.eval()
        elapsed = time.time() - t0

        # ESM-2 t6 8M dim = 320; override embedding_dim
        self.embedding_dim = mdl.config.hidden_size
        self._model = mdl
        self._use_esm_sdk = False

        log.warning(
            "esmc_using_transformers_fallback",
            source=src,
            hidden_size=self.embedding_dim,
            load_time_s=round(elapsed, 2),
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _seq_hash(self, seq: str) -> str:
        return hashlib.sha256(seq.encode()).hexdigest()[:16]

    # ------------------------------------------------------------------
    # Embedding generation
    # ------------------------------------------------------------------

    async def embed_protein(
        self,
        sequence: str,
        protein_id: Optional[str] = None,
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """Generate a 960-d embedding for a single protein sequence.

        Returns:
            (embedding_array, metadata_dict)
        """
        self.load_model()

        seq_hash = self._seq_hash(sequence)
        if seq_hash in self._embedding_cache:
            return self._embedding_cache[seq_hash], {"cached": True}

        if self.cache_embeddings and protein_id:
            cached = await self._get_from_qdrant(protein_id)
            if cached is not None:
                self._embedding_cache[seq_hash] = cached
                return cached, {"cached": True, "source": "qdrant"}

        try:
            embedding = self._run_inference(sequence)
            self._embedding_cache[seq_hash] = embedding

            if self.cache_embeddings and protein_id:
                await self._store_in_qdrant(protein_id, embedding, sequence)

            meta = {
                "cached": False,
                "sequence_length": len(sequence),
                "embedding_dim": int(embedding.shape[-1]),
                "model": self.model_name,
            }
            log.info("esmc_embedding_generated", protein_id=protein_id, seq_len=len(sequence))
            return embedding, meta

        except Exception as e:
            log.error("esmc_embedding_failed", protein_id=protein_id, error=str(e))
            raise

    def _run_inference(self, sequence: str) -> np.ndarray:
        """Run ESM-C 600M inference and return mean-pooled 960-d embedding."""
        if self._use_esm_sdk:
            from esm.sdk.api import ESMProtein  # type: ignore
            protein = ESMProtein(sequence=sequence)
            with torch.no_grad():
                output = self._model.encode(protein)
            # output.embeddings: shape [L, 960] — mean pool over L
            emb = output.embeddings  # Tensor [L, D]
            if isinstance(emb, torch.Tensor):
                return emb.mean(dim=0).cpu().float().numpy()
            else:
                return np.array(emb).mean(axis=0)
        else:
            # Transformers fallback
            enc = self._tokenizer(
                sequence,
                return_tensors="pt",
                truncation=True,
                max_length=1024,
            ).to(self.device)
            with torch.no_grad():
                out = self._model(**enc)
            # Mean-pool over token dimension (excluding [CLS] and [EOS])
            hidden = out.last_hidden_state[0, 1:-1, :]  # [L, D]
            return hidden.mean(0).cpu().float().numpy()

    async def embed_proteins_batch(
        self,
        sequences: List[Tuple[str, str]],
        batch_size: int = 32,
    ) -> List[Tuple[np.ndarray, Dict[str, Any]]]:
        """Batch embedding for multiple (protein_id, sequence) tuples.

        Returns list of (embedding, metadata) tuples in same order as input.
        """
        self.load_model()
        results: List[Optional[Tuple[np.ndarray, Dict[str, Any]]]] = []

        for i in range(0, len(sequences), batch_size):
            batch = sequences[i : i + batch_size]

            uncached: List[Tuple[int, str, str]] = []  # (result_idx, pid, seq)
            for pid, seq in batch:
                sh = self._seq_hash(seq)
                if sh in self._embedding_cache:
                    results.append((self._embedding_cache[sh], {"cached": True}))
                else:
                    uncached.append((len(results), pid, seq))
                    results.append(None)  # placeholder

            for out_idx, pid, seq in uncached:
                try:
                    emb = self._run_inference(seq)
                    sh = self._seq_hash(seq)
                    self._embedding_cache[sh] = emb
                    if self.cache_embeddings:
                        await self._store_in_qdrant(pid, emb, seq)
                    results[out_idx] = (
                        emb,
                        {"cached": False, "sequence_length": len(seq),
                         "embedding_dim": int(emb.shape[-1]), "model": self.model_name},
                    )
                except Exception as e:
                    log.error("esmc_batch_item_failed", protein_id=pid, error=str(e))
                    results[out_idx] = (None, {"error": str(e)})  # type: ignore

            log.info("esmc_batch_processed", batch_size=len(uncached))

        return results  # type: ignore

    # ------------------------------------------------------------------
    # Qdrant cache helpers
    # ------------------------------------------------------------------

    async def _get_from_qdrant(self, protein_id: str) -> Optional[np.ndarray]:
        try:
            from core.vector_store import get_vector_store
            vs = get_vector_store()
            r = await vs.search(
                collection_name="protein_embeddings_esmc",
                query_filter={"protein_id": protein_id},
                limit=1,
            )
            if r:
                return np.array(r[0]["vector"])
        except Exception as e:
            log.warning("qdrant_get_failed", protein_id=protein_id, error=str(e))
        return None

    async def _store_in_qdrant(
        self, protein_id: str, embedding: np.ndarray, sequence: str
    ) -> None:
        try:
            from core.vector_store import get_vector_store
            vs = get_vector_store()
            await vs.create_collection(
                collection_name="protein_embeddings_esmc",
                vector_size=int(embedding.shape[-1]),
            )
            await vs.upsert(
                collection_name="protein_embeddings_esmc",
                points=[{
                    "id": protein_id,
                    "vector": embedding.tolist(),
                    "payload": {
                        "protein_id": protein_id,
                        "sequence_length": len(sequence),
                        "model": self.model_name,
                        "embedding_dim": int(embedding.shape[-1]),
                    },
                }],
            )
        except Exception as e:
            log.warning("qdrant_store_failed", protein_id=protein_id, error=str(e))

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def compute_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        n1, n2 = np.linalg.norm(a), np.linalg.norm(b)
        if n1 == 0 or n2 == 0:
            return 0.0
        return float(np.dot(a, b) / (n1 * n2))

    async def find_similar_proteins(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        min_similarity: float = 0.7,
    ) -> List[Dict[str, Any]]:
        try:
            from core.vector_store import get_vector_store
            vs = get_vector_store()
            return await vs.search(
                collection_name="protein_embeddings_esmc",
                query_vector=query_embedding.tolist(),
                limit=top_k,
                score_threshold=min_similarity,
            )
        except Exception as e:
            log.error("similar_proteins_search_failed", error=str(e))
            return []

    def clear_cache(self) -> None:
        self._embedding_cache.clear()
        log.info("esmc_cache_cleared")


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

_esmc_instance: Optional[ESMCModel] = None


def get_esmc_model(device: Optional[str] = None) -> ESMCModel:
    """Return (or create) the module-level ESM-C 600M singleton."""
    global _esmc_instance
    if _esmc_instance is None:
        _esmc_instance = ESMCModel(device=device)
    return _esmc_instance

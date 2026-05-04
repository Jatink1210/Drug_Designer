"""ESM-2 protein language model for protein embeddings."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import structlog
import torch

log = structlog.get_logger()


class ESM2Model:
    """
    ESM-2 (Evolutionary Scale Modeling) protein language model.
    
    ESM-2 is a transformer-based protein language model trained on millions of
    protein sequences. It generates high-quality embeddings for protein sequences
    that capture evolutionary and structural information.
    
    Model: facebook/esm2_t33_650M_UR50D (650M parameters)
    Embedding dimension: 1280
    """
    
    def __init__(
        self,
        model_name: str = "esm2_t33_650M_UR50D",
        device: Optional[str] = None,
        cache_embeddings: bool = True
    ):
        """
        Initialize ESM-2 model.
        
        Args:
            model_name: ESM-2 model variant
            device: Device to run model on (cuda/cpu)
            cache_embeddings: Whether to cache embeddings in Qdrant
        """
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.cache_embeddings = cache_embeddings
        self.embedding_dim = 1280
        
        self.model = None
        self.alphabet = None
        self.batch_converter = None
        self._embedding_cache: Dict[str, np.ndarray] = {}
        
        log.info("esm2_model_initialized", model=model_name, device=self.device)
    
    def load_model(self) -> None:
        """Load ESM-2 model and tokenizer.

        Resolution order:
        1. MODEL_CACHE_DIR/esm2/ (local weights downloaded by scripts/download_models.py)
        2. HuggingFace Hub (facebook/esm2_t33_650M_UR50D) — requires internet
        Logs load time and memory footprint.
        """
        if self.model is not None:
            return

        import os
        import time

        _HF_REPO = "facebook/esm2_t33_650M_UR50D"

        # Resolve local model dir from config
        try:
            from config import settings as _cfg
            _cache = getattr(_cfg, "model_cache_dir", "") or ""
        except Exception:
            _cache = ""
        if not _cache:
            from core.paths import get_data_dir
            _cache = os.path.join(get_data_dir(), "models")
        local_dir = os.path.join(_cache, "esm2")
        source = local_dir if os.path.isdir(local_dir) and os.path.exists(
            os.path.join(local_dir, "config.json")
        ) else _HF_REPO

        try:
            from transformers import EsmModel, EsmTokenizer  # type: ignore

            t0 = time.time()
            tok = EsmTokenizer.from_pretrained(source)
            mdl = EsmModel.from_pretrained(source)
            mdl = mdl.to(self.device)
            mdl.eval()
            elapsed = time.time() - t0

            # Memory footprint
            mem_mb = sum(p.numel() * p.element_size() for p in mdl.parameters()) / (1024 ** 2)

            # Wrap into the legacy (model, alphabet) interface expected by embed_protein
            self.model = mdl
            self.alphabet = tok          # tokenizer stored as alphabet for compatibility
            self.batch_converter = None  # not used in transformers path
            self._use_transformers = True

            log.info(
                "esm2_model_loaded",
                source="local" if source == local_dir else "hub",
                path=source,
                load_time_s=round(elapsed, 2),
                memory_mb=round(mem_mb, 1),
            )
        except Exception as e:
            log.error("esm2_model_load_failed", source=source, error=str(e))
            raise
    
    def _get_sequence_hash(self, sequence: str) -> str:
        """Generate hash for sequence caching."""
        return hashlib.sha256(sequence.encode()).hexdigest()[:16]
    
    async def embed_protein(
        self,
        sequence: str,
        protein_id: Optional[str] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Generate embedding for a single protein sequence.
        
        Args:
            sequence: Protein amino acid sequence
            protein_id: Optional protein identifier
            
        Returns:
            Tuple of (embedding vector, metadata)
        """
        self.load_model()
        
        # Check cache
        seq_hash = self._get_sequence_hash(sequence)
        if seq_hash in self._embedding_cache:
            log.debug("esm2_cache_hit", protein_id=protein_id)
            return self._embedding_cache[seq_hash], {"cached": True}
        
        # Check Qdrant cache if enabled
        if self.cache_embeddings and protein_id:
            cached_embedding = await self._get_from_qdrant(protein_id)
            if cached_embedding is not None:
                self._embedding_cache[seq_hash] = cached_embedding
                return cached_embedding, {"cached": True, "source": "qdrant"}
        
        # Generate embedding
        try:
            data = [(protein_id or "protein", sequence)]
            batch_labels, batch_strs, batch_tokens = self.batch_converter(data)
            batch_tokens = batch_tokens.to(self.device)
            
            with torch.no_grad():
                results = self.model(batch_tokens, repr_layers=[33])
                token_representations = results["representations"][33]
            
            # Use mean pooling over sequence length
            embedding = token_representations[0, 1:len(sequence)+1].mean(0).cpu().numpy()
            
            # Cache embedding
            self._embedding_cache[seq_hash] = embedding
            
            # Store in Qdrant if enabled
            if self.cache_embeddings and protein_id:
                await self._store_in_qdrant(protein_id, embedding, sequence)
            
            metadata = {
                "cached": False,
                "sequence_length": len(sequence),
                "embedding_dim": self.embedding_dim,
                "model": self.model_name
            }
            
            log.info("esm2_embedding_generated", protein_id=protein_id, seq_len=len(sequence))
            return embedding, metadata
            
        except Exception as e:
            log.error("esm2_embedding_failed", protein_id=protein_id, error=str(e))
            raise
    
    async def embed_proteins_batch(
        self,
        sequences: List[Tuple[str, str]],
        batch_size: int = 32
    ) -> List[Tuple[np.ndarray, Dict[str, Any]]]:
        """
        Generate embeddings for multiple protein sequences.
        
        Args:
            sequences: List of (protein_id, sequence) tuples
            batch_size: Batch size for processing
            
        Returns:
            List of (embedding, metadata) tuples
        """
        self.load_model()
        
        results = []
        
        for i in range(0, len(sequences), batch_size):
            batch = sequences[i:i+batch_size]
            
            # Check cache for each sequence
            batch_to_process = []
            batch_indices = []
            
            for idx, (protein_id, sequence) in enumerate(batch):
                seq_hash = self._get_sequence_hash(sequence)
                if seq_hash in self._embedding_cache:
                    results.append((self._embedding_cache[seq_hash], {"cached": True}))
                else:
                    batch_to_process.append((protein_id, sequence))
                    batch_indices.append(len(results))
                    results.append(None)  # Placeholder
            
            if not batch_to_process:
                continue
            
            # Process batch
            try:
                batch_labels, batch_strs, batch_tokens = self.batch_converter(batch_to_process)
                batch_tokens = batch_tokens.to(self.device)
                
                with torch.no_grad():
                    batch_results = self.model(batch_tokens, repr_layers=[33])
                    token_representations = batch_results["representations"][33]
                
                # Extract embeddings
                for j, (protein_id, sequence) in enumerate(batch_to_process):
                    seq_len = len(sequence)
                    embedding = token_representations[j, 1:seq_len+1].mean(0).cpu().numpy()
                    
                    # Cache
                    seq_hash = self._get_sequence_hash(sequence)
                    self._embedding_cache[seq_hash] = embedding
                    
                    # Store in Qdrant
                    if self.cache_embeddings:
                        await self._store_in_qdrant(protein_id, embedding, sequence)
                    
                    metadata = {
                        "cached": False,
                        "sequence_length": seq_len,
                        "embedding_dim": self.embedding_dim,
                        "model": self.model_name
                    }
                    
                    results[batch_indices[j]] = (embedding, metadata)
                
                log.info("esm2_batch_processed", batch_size=len(batch_to_process))
                
            except Exception as e:
                log.error("esm2_batch_failed", error=str(e))
                # Fill placeholders with None
                for idx in batch_indices:
                    if results[idx] is None:
                        results[idx] = (None, {"error": str(e)})
        
        return results
    
    async def _get_from_qdrant(self, protein_id: str) -> Optional[np.ndarray]:
        """Retrieve embedding from Qdrant cache."""
        try:
            from core.vector_store import get_vector_store
            
            vector_store = get_vector_store()
            collection_name = "protein_embeddings_esm2"
            
            # Search for exact protein ID match
            results = await vector_store.search(
                collection_name=collection_name,
                query_filter={"protein_id": protein_id},
                limit=1
            )
            
            if results and len(results) > 0:
                return np.array(results[0]["vector"])
            
            return None
            
        except Exception as e:
            log.warning("qdrant_get_failed", protein_id=protein_id, error=str(e))
            return None
    
    async def _store_in_qdrant(
        self,
        protein_id: str,
        embedding: np.ndarray,
        sequence: str
    ) -> None:
        """Store embedding in Qdrant cache."""
        try:
            from core.vector_store import get_vector_store
            
            vector_store = get_vector_store()
            collection_name = "protein_embeddings_esm2"
            
            # Ensure collection exists
            await vector_store.create_collection(
                collection_name=collection_name,
                vector_size=self.embedding_dim
            )
            
            # Store embedding
            await vector_store.upsert(
                collection_name=collection_name,
                points=[{
                    "id": protein_id,
                    "vector": embedding.tolist(),
                    "payload": {
                        "protein_id": protein_id,
                        "sequence_length": len(sequence),
                        "model": self.model_name,
                        "embedding_dim": self.embedding_dim
                    }
                }]
            )
            
            log.debug("qdrant_store_success", protein_id=protein_id)
            
        except Exception as e:
            log.warning("qdrant_store_failed", protein_id=protein_id, error=str(e))
    
    def compute_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray
    ) -> float:
        """
        Compute cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
            
        Returns:
            Cosine similarity score (0-1)
        """
        dot_product = np.dot(embedding1, embedding2)
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    async def find_similar_proteins(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        min_similarity: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Find similar proteins using Qdrant vector search.
        
        Args:
            query_embedding: Query protein embedding
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of similar proteins with scores
        """
        try:
            from core.vector_store import get_vector_store
            
            vector_store = get_vector_store()
            collection_name = "protein_embeddings_esm2"
            
            results = await vector_store.search(
                collection_name=collection_name,
                query_vector=query_embedding.tolist(),
                limit=top_k,
                score_threshold=min_similarity
            )
            
            return results
            
        except Exception as e:
            log.error("similar_proteins_search_failed", error=str(e))
            return []
    
    def clear_cache(self) -> None:
        """Clear in-memory embedding cache."""
        self._embedding_cache.clear()
        log.info("esm2_cache_cleared")

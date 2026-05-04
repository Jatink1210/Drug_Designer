"""MolFormer molecule transformer for molecular embeddings."""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import structlog
import torch

log = structlog.get_logger()


class MolFormerModel:
    """
    MolFormer molecule transformer for molecular embeddings and property prediction.
    
    MolFormer is a transformer-based model trained on millions of molecules using
    SMILES representations. It generates embeddings that capture molecular structure
    and properties.
    
    Embedding dimension: 768
    """
    
    def __init__(
        self,
        model_name: str = "ibm/MolFormer-XL-both-10pct",
        device: Optional[str] = None,
        cache_embeddings: bool = True
    ):
        """
        Initialize MolFormer model.
        
        Args:
            model_name: MolFormer model variant
            device: Device to run model on (cuda/cpu)
            cache_embeddings: Whether to cache embeddings in Qdrant
        """
        self.model_name = model_name
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.cache_embeddings = cache_embeddings
        self.embedding_dim = 768
        
        self.model = None
        self.tokenizer = None
        self._embedding_cache: Dict[str, np.ndarray] = {}
        
        log.info("molformer_model_initialized", model=model_name, device=self.device)
    
    def load_model(self) -> None:
        """Load MolFormer model and tokenizer.

        Resolution order:
        1. MODEL_CACHE_DIR/molformer/ (local weights downloaded by scripts/download_models.py)
        2. HuggingFace Hub (ibm/MolFormer-XL-both-10pct) — requires internet
        Logs load time and memory footprint.
        """
        if self.model is not None:
            return

        import os
        import time

        _HF_REPO = "ibm/MolFormer-XL-both-10pct"

        # Resolve local model dir from config
        try:
            from config import settings as _cfg
            _cache = getattr(_cfg, "model_cache_dir", "") or ""
        except Exception:
            _cache = ""
        if not _cache:
            from core.paths import get_data_dir
            _cache = os.path.join(get_data_dir(), "models")
        local_dir = os.path.join(_cache, "molformer")
        source = local_dir if os.path.isdir(local_dir) and os.path.exists(
            os.path.join(local_dir, "config.json")
        ) else _HF_REPO

        try:
            from transformers import AutoModel, AutoTokenizer

            t0 = time.time()
            self.tokenizer = AutoTokenizer.from_pretrained(source, trust_remote_code=True)
            self.model = AutoModel.from_pretrained(source, trust_remote_code=True)
            self.model = self.model.to(self.device)
            self.model.eval()
            elapsed = time.time() - t0

            # Memory footprint
            mem_mb = sum(p.numel() * p.element_size() for p in self.model.parameters()) / (1024 ** 2)

            log.info(
                "molformer_model_loaded",
                source="local" if source == local_dir else "hub",
                path=source,
                load_time_s=round(elapsed, 2),
                memory_mb=round(mem_mb, 1),
            )
        except Exception as e:
            log.error("molformer_model_load_failed", source=source, error=str(e))
            raise
    
    def _get_smiles_hash(self, smiles: str) -> str:
        """Generate hash for SMILES caching."""
        return hashlib.sha256(smiles.encode()).hexdigest()[:16]
    
    async def embed_molecule(
        self,
        smiles: str,
        molecule_id: Optional[str] = None
    ) -> Tuple[np.ndarray, Dict[str, Any]]:
        """
        Generate embedding for a single molecule.
        
        Args:
            smiles: SMILES string representation
            molecule_id: Optional molecule identifier
            
        Returns:
            Tuple of (embedding vector, metadata)
        """
        self.load_model()
        
        # Check cache
        smiles_hash = self._get_smiles_hash(smiles)
        if smiles_hash in self._embedding_cache:
            log.debug("molformer_cache_hit", molecule_id=molecule_id)
            return self._embedding_cache[smiles_hash], {"cached": True}
        
        # Check Qdrant cache if enabled
        if self.cache_embeddings and molecule_id:
            cached_embedding = await self._get_from_qdrant(molecule_id)
            if cached_embedding is not None:
                self._embedding_cache[smiles_hash] = cached_embedding
                return cached_embedding, {"cached": True, "source": "qdrant"}
        
        # Generate embedding
        try:
            # Tokenize SMILES
            inputs = self.tokenizer(smiles, return_tensors="pt", padding=True, truncation=True)
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                # Use [CLS] token embedding
                embedding = outputs.last_hidden_state[:, 0, :].squeeze().cpu().numpy()
            
            # Cache embedding
            self._embedding_cache[smiles_hash] = embedding
            
            # Store in Qdrant if enabled
            if self.cache_embeddings and molecule_id:
                await self._store_in_qdrant(molecule_id, embedding, smiles)
            
            metadata = {
                "cached": False,
                "smiles_length": len(smiles),
                "embedding_dim": self.embedding_dim,
                "model": self.model_name
            }
            
            log.info("molformer_embedding_generated", molecule_id=molecule_id, smiles_len=len(smiles))
            return embedding, metadata
            
        except Exception as e:
            log.error("molformer_embedding_failed", molecule_id=molecule_id, error=str(e))
            raise
    
    async def embed_molecules_batch(
        self,
        molecules: List[Tuple[str, str]],
        batch_size: int = 32
    ) -> List[Tuple[np.ndarray, Dict[str, Any]]]:
        """
        Generate embeddings for multiple molecules.
        
        Args:
            molecules: List of (molecule_id, smiles) tuples
            batch_size: Batch size for processing
            
        Returns:
            List of (embedding, metadata) tuples
        """
        self.load_model()
        
        results = []
        
        for i in range(0, len(molecules), batch_size):
            batch = molecules[i:i+batch_size]
            
            # Check cache for each molecule
            batch_to_process = []
            batch_indices = []
            
            for idx, (molecule_id, smiles) in enumerate(batch):
                smiles_hash = self._get_smiles_hash(smiles)
                if smiles_hash in self._embedding_cache:
                    results.append((self._embedding_cache[smiles_hash], {"cached": True}))
                else:
                    batch_to_process.append((molecule_id, smiles))
                    batch_indices.append(len(results))
                    results.append(None)  # Placeholder
            
            if not batch_to_process:
                continue
            
            # Process batch
            try:
                smiles_list = [smiles for _, smiles in batch_to_process]
                inputs = self.tokenizer(smiles_list, return_tensors="pt", padding=True, truncation=True)
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    outputs = self.model(**inputs)
                    embeddings = outputs.last_hidden_state[:, 0, :].cpu().numpy()
                
                # Extract embeddings
                for j, (molecule_id, smiles) in enumerate(batch_to_process):
                    embedding = embeddings[j]
                    
                    # Cache
                    smiles_hash = self._get_smiles_hash(smiles)
                    self._embedding_cache[smiles_hash] = embedding
                    
                    # Store in Qdrant
                    if self.cache_embeddings:
                        await self._store_in_qdrant(molecule_id, embedding, smiles)
                    
                    metadata = {
                        "cached": False,
                        "smiles_length": len(smiles),
                        "embedding_dim": self.embedding_dim,
                        "model": self.model_name
                    }
                    
                    results[batch_indices[j]] = (embedding, metadata)
                
                log.info("molformer_batch_processed", batch_size=len(batch_to_process))
                
            except Exception as e:
                log.error("molformer_batch_failed", error=str(e))
                # Fill placeholders with None
                for idx in batch_indices:
                    if results[idx] is None:
                        results[idx] = (None, {"error": str(e)})
        
        return results
    
    async def _get_from_qdrant(self, molecule_id: str) -> Optional[np.ndarray]:
        """Retrieve embedding from Qdrant cache."""
        try:
            from core.vector_store import get_vector_store
            
            vector_store = get_vector_store()
            collection_name = "molecule_embeddings_molformer"
            
            results = await vector_store.search(
                collection_name=collection_name,
                query_filter={"molecule_id": molecule_id},
                limit=1
            )
            
            if results and len(results) > 0:
                return np.array(results[0]["vector"])
            
            return None
            
        except Exception as e:
            log.warning("qdrant_get_failed", molecule_id=molecule_id, error=str(e))
            return None
    
    async def _store_in_qdrant(
        self,
        molecule_id: str,
        embedding: np.ndarray,
        smiles: str
    ) -> None:
        """Store embedding in Qdrant cache."""
        try:
            from core.vector_store import get_vector_store
            
            vector_store = get_vector_store()
            collection_name = "molecule_embeddings_molformer"
            
            # Ensure collection exists
            await vector_store.create_collection(
                collection_name=collection_name,
                vector_size=self.embedding_dim
            )
            
            # Store embedding
            await vector_store.upsert(
                collection_name=collection_name,
                points=[{
                    "id": molecule_id,
                    "vector": embedding.tolist(),
                    "payload": {
                        "molecule_id": molecule_id,
                        "smiles": smiles,
                        "smiles_length": len(smiles),
                        "model": self.model_name,
                        "embedding_dim": self.embedding_dim
                    }
                }]
            )
            
            log.debug("qdrant_store_success", molecule_id=molecule_id)
            
        except Exception as e:
            log.warning("qdrant_store_failed", molecule_id=molecule_id, error=str(e))
    
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
    
    async def find_similar_molecules(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        min_similarity: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Find similar molecules using Qdrant vector search.
        
        Args:
            query_embedding: Query molecule embedding
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of similar molecules with scores
        """
        try:
            from core.vector_store import get_vector_store
            
            vector_store = get_vector_store()
            collection_name = "molecule_embeddings_molformer"
            
            results = await vector_store.search(
                collection_name=collection_name,
                query_vector=query_embedding.tolist(),
                limit=top_k,
                score_threshold=min_similarity
            )
            
            return results
            
        except Exception as e:
            log.error("similar_molecules_search_failed", error=str(e))
            return []
    
    def clear_cache(self) -> None:
        """Clear in-memory embedding cache."""
        self._embedding_cache.clear()
        log.info("molformer_cache_cleared")

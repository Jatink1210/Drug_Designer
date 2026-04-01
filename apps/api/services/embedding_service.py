"""Embedding Service for Protein, Molecule, and Text generation."""

import logging
import torch
import gc
from typing import List
from transformers import AutoModel, AutoTokenizer

log = logging.getLogger(__name__)


class EmbeddingService:
    """Manages HuggingFace model caching and batch inference."""

    # Model registry
    MODELS = {
        "protein": {"name": "facebook/esm2_t6_8M_UR50D", "type": "esm"},
        "molecule": {"name": "ibm/MoLFormer-XL-both-10pct", "type": "molformer"},
        "text": {"name": "dmis-lab/biobert-base-cased-v1.2", "type": "bert"}
    }

    def __init__(self, device: str = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._cache = {}

    def _load(self, domain: str):
        if domain not in self._cache:
            model_info = self.MODELS.get(domain)
            if not model_info:
                raise ValueError(f"Unknown domain for embedding: {domain}")
            
            log.info(f"Loading {domain} model: {model_info['name']} onto {self.device}")
            tokenizer = AutoTokenizer.from_pretrained(model_info["name"], trust_remote_code=True)
            model = AutoModel.from_pretrained(model_info["name"], trust_remote_code=True).to(self.device)
            model.eval()
            self._cache[domain] = {"tokenizer": tokenizer, "model": model, "type": model_info["type"]}
        return self._cache[domain]

    @torch.no_grad()
    def embed_proteins(self, sequences: List[str]) -> torch.Tensor:
        """Embed protein sequences using ESM-2."""
        if not sequences:
            return torch.empty((0, 320))
            
        components = self._load("protein")
        tok, mod = components["tokenizer"], components["model"]
        
        inputs = tok(sequences, return_tensors="pt", padding=True, truncation=True, max_length=1024).to(self.device)
        outputs = mod(**inputs)
        # Average pooling over sequence length
        embeddings = outputs.last_hidden_state.mean(dim=1).cpu()
        return embeddings

    @torch.no_grad()
    def embed_molecules(self, smiles: List[str]) -> torch.Tensor:
        """Embed SMILES using MolFormer."""
        if not smiles:
            return torch.empty((0, 768))

        components = self._load("molecule")
        tok, mod = components["tokenizer"], components["model"]
        
        inputs = tok(smiles, return_tensors="pt", padding=True, truncation=True, max_length=512).to(self.device)
        outputs = mod(**inputs)
        # Assuming MolFormer outputs pooler_output or we mean pool
        if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
             embeddings = outputs.pooler_output.cpu()
        else:
             embeddings = outputs.last_hidden_state.mean(dim=1).cpu()
        return embeddings

    @torch.no_grad()
    def embed_text(self, texts: List[str]) -> torch.Tensor:
        """Embed natural language (Pathways, GWAS, Pubs) using SciBERT."""
        if not texts:
            return torch.empty((0, 768))
            
        components = self._load("text")
        tok, mod = components["tokenizer"], components["model"]
        
        inputs = tok(texts, return_tensors="pt", padding=True, truncation=True, max_length=512).to(self.device)
        outputs = mod(**inputs)
        embeddings = outputs.last_hidden_state[:, 0, :].cpu()  # CLS token
        return embeddings

    def clear_cache(self):
        self._cache.clear()
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

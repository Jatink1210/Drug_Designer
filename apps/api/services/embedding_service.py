"""Multi-Modal Embedding Service (§81).

Spec-required models and dimensions:
  • Protein  — ESM-2 650M (`facebook/esm2_t33_650M_UR50D`) → 1280-d
  • Molecule — MolFormer (`ibm/MoLFormer-XL-both-10pct`)  → 768-d
  • Text     — SciBERT (`allenai/scibert_scivocab_uncased`) → 768-d
  • Pathway  — KEGG2Vec (Random Walk + Skip-Gram on KEGG)  → 512-d
  • SNP      — SNP2Vec (positional + LD graph)              → 256-d

All modalities are projected to a unified 512-d space by the AlignmentModel (§9).
"""

import logging
import gc
import hashlib
from typing import Dict, List, Optional

try:
    import torch
    import torch.nn as nn
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

try:
    from transformers import AutoModel, AutoTokenizer
    HF_AVAILABLE = True
except ImportError:
    HF_AVAILABLE = False

try:
    import numpy as np
    NP_AVAILABLE = True
except ImportError:
    NP_AVAILABLE = False

from core.cache import cache_key as _cache_key, two_tier_get, two_tier_put

log = logging.getLogger(__name__)


class EmbeddingService:
    """Manages HuggingFace model caching and batch inference (§81)."""

    # Model registry — spec §81 mandates these exact models
    MODELS = {
        "protein": {
            "name": "facebook/esm2_t33_650M_UR50D",  # §81: ESM-2 650M → 1280-d
            "type": "esm",
            "dim": 1280,
        },
        "molecule": {
            "name": "ibm/MoLFormer-XL-both-10pct",   # §81: MolFormer → 768-d
            "type": "molformer",
            "dim": 768,
        },
        "text": {
            "name": "allenai/scibert_scivocab_uncased",  # §81: SciBERT → 768-d
            "type": "bert",
            "dim": 768,
        },
    }

    def __init__(self, device: str = None):
        if TORCH_AVAILABLE:
            self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = "cpu"
        self._cache: Dict[str, dict] = {}
        self._kegg2vec: Optional["KEGG2Vec"] = None
        self._snp2vec: Optional["SNP2Vec"] = None

    def _load(self, domain: str):
        if not HF_AVAILABLE or not TORCH_AVAILABLE:
            raise RuntimeError("transformers and torch are required for embedding")
        if domain not in self._cache:
            model_info = self.MODELS.get(domain)
            if not model_info:
                raise ValueError(f"Unknown domain for embedding: {domain}")

            log.info(f"Loading {domain} model: {model_info['name']} onto {self.device}")
            tokenizer = AutoTokenizer.from_pretrained(model_info["name"], trust_remote_code=True)
            model = AutoModel.from_pretrained(model_info["name"], trust_remote_code=True).to(self.device)
            model.eval()
            self._cache[domain] = {
                "tokenizer": tokenizer,
                "model": model,
                "type": model_info["type"],
                "dim": model_info["dim"],
            }
        return self._cache[domain]

    def _embedding_cache_key(self, domain: str, inputs: List[str]) -> str:
        """Generate a cache key for embedding results."""
        content_hash = hashlib.sha256("|".join(inputs).encode()).hexdigest()[:16]
        return _cache_key("embed", domain, content_hash)

    @torch.no_grad() if TORCH_AVAILABLE else lambda f: f
    def embed_proteins(self, sequences: List[str]) -> "torch.Tensor":
        """Embed protein sequences using ESM-2 650M → 1280-d (§81)."""
        if not sequences:
            return torch.empty((0, 1280))

        # Check embedding result cache
        ck = self._embedding_cache_key("protein", sequences)
        cached = two_tier_get(ck)
        if cached is not None:
            return torch.tensor(cached, dtype=torch.float32)

        components = self._load("protein")
        tok, mod = components["tokenizer"], components["model"]

        inputs = tok(
            sequences, return_tensors="pt", padding=True,
            truncation=True, max_length=1024
        ).to(self.device)
        outputs = mod(**inputs)
        # Average pooling over sequence length → 1280-d
        embeddings = outputs.last_hidden_state.mean(dim=1).cpu()

        two_tier_put(ck, "embed_protein", "local", embeddings.tolist(), ttl=86400)
        return embeddings  # (batch, 1280)

    @torch.no_grad() if TORCH_AVAILABLE else lambda f: f
    def embed_molecules(self, smiles: List[str]) -> "torch.Tensor":
        """Embed SMILES using MolFormer → 768-d (§81)."""
        if not smiles:
            return torch.empty((0, 768))

        ck = self._embedding_cache_key("molecule", smiles)
        cached = two_tier_get(ck)
        if cached is not None:
            return torch.tensor(cached, dtype=torch.float32)

        components = self._load("molecule")
        tok, mod = components["tokenizer"], components["model"]

        inputs = tok(
            smiles, return_tensors="pt", padding=True,
            truncation=True, max_length=512
        ).to(self.device)
        outputs = mod(**inputs)
        if hasattr(outputs, "pooler_output") and outputs.pooler_output is not None:
            embeddings = outputs.pooler_output.cpu()
        else:
            embeddings = outputs.last_hidden_state.mean(dim=1).cpu()

        two_tier_put(ck, "embed_molecule", "local", embeddings.tolist(), ttl=86400)
        return embeddings  # (batch, 768)

    @torch.no_grad() if TORCH_AVAILABLE else lambda f: f
    def embed_text(self, texts: List[str]) -> "torch.Tensor":
        """Embed literature/clinical text using SciBERT → 768-d (§81)."""
        if not texts:
            return torch.empty((0, 768))

        ck = self._embedding_cache_key("text", texts)
        cached = two_tier_get(ck)
        if cached is not None:
            return torch.tensor(cached, dtype=torch.float32)

        components = self._load("text")
        tok, mod = components["tokenizer"], components["model"]

        inputs = tok(
            texts, return_tensors="pt", padding=True,
            truncation=True, max_length=512
        ).to(self.device)
        outputs = mod(**inputs)
        embeddings = outputs.last_hidden_state[:, 0, :].cpu()  # CLS token → 768-d

        two_tier_put(ck, "embed_text", "local", embeddings.tolist(), ttl=86400)
        return embeddings

    def embed_pathways(self, pathway_ids: List[str]) -> "torch.Tensor":
        """Embed KEGG pathway identifiers using KEGG2Vec → 512-d (§81)."""
        if self._kegg2vec is None:
            self._kegg2vec = KEGG2Vec(dim=512)
        return self._kegg2vec.embed(pathway_ids)

    def embed_snps(self, rsids: List[str]) -> "torch.Tensor":
        """Embed SNP identifiers using SNP2Vec → 256-d (§81)."""
        if self._snp2vec is None:
            self._snp2vec = SNP2Vec(dim=256)
        return self._snp2vec.embed(rsids)

    def clear_cache(self):
        self._cache.clear()
        gc.collect()
        if TORCH_AVAILABLE and torch.cuda.is_available():
            torch.cuda.empty_cache()


# ──────────────────────────────────────────────────────────────────────
# §81: KEGG2Vec — Random Walk + Skip-Gram on KEGG graph
# ──────────────────────────────────────────────────────────────────────

class KEGG2Vec:
    """KEGG pathway embedding via Random Walk + Skip-Gram (§81).

    Generates graph-structure-aware embeddings of metabolic/signalling
    pathways by performing random walks on the KEGG pathway-gene
    bipartite graph and training a Skip-Gram model.
    """

    def __init__(self, dim: int = 512, walk_length: int = 40,
                 num_walks: int = 10, window: int = 5):
        self.dim = dim
        self.walk_length = walk_length
        self.num_walks = num_walks
        self.window = window
        self._model = None  # gensim Word2Vec model
        self._vocab: Dict[str, int] = {}

    def _random_walk(self, graph: dict, start: str) -> List[str]:
        """Perform a single random walk starting from node."""
        walk = [start]
        current = start
        for _ in range(self.walk_length - 1):
            neighbors = graph.get(current, [])
            if not neighbors:
                break
            if NP_AVAILABLE:
                current = neighbors[np.random.randint(len(neighbors))]
            else:
                import random
                current = random.choice(neighbors)
            walk.append(current)
        return walk

    def train(self, pathway_graph: Dict[str, List[str]]):
        """Train KEGG2Vec on pathway-gene bipartite graph.

        Args:
            pathway_graph: adjacency list {node_id: [neighbor_ids]}
        """
        try:
            from gensim.models import Word2Vec
        except ImportError:
            log.warning("gensim not available for KEGG2Vec training")
            return

        sentences = []
        for node in pathway_graph:
            for _ in range(self.num_walks):
                walk = self._random_walk(pathway_graph, node)
                sentences.append(walk)

        self._model = Word2Vec(
            sentences=sentences,
            vector_size=self.dim,
            window=self.window,
            min_count=1,
            sg=1,  # Skip-Gram
            workers=4,
            epochs=20,
        )
        self._vocab = {w: i for i, w in enumerate(self._model.wv.index_to_key)}
        log.info(f"KEGG2Vec trained: {len(self._vocab)} nodes, {self.dim}-d")

    def embed(self, pathway_ids: List[str]) -> "torch.Tensor":
        """Look up embeddings for pathway identifiers."""
        if not TORCH_AVAILABLE:
            raise RuntimeError("torch required for KEGG2Vec embeddings")
        embeddings = []
        for pid in pathway_ids:
            if self._model is not None and pid in self._model.wv:
                vec = self._model.wv[pid]
                embeddings.append(torch.tensor(vec, dtype=torch.float32))
            else:
                # Hash-based fallback for unknown pathways
                import hashlib
                h = int(hashlib.sha256(pid.encode()).hexdigest(), 16)
                gen = torch.Generator().manual_seed(h % (2**63))
                embeddings.append(torch.randn(self.dim, generator=gen))
        return torch.stack(embeddings) if embeddings else torch.empty((0, self.dim))


# ──────────────────────────────────────────────────────────────────────
# §81: SNP2Vec — Positional + LD Graph Embedding
# ──────────────────────────────────────────────────────────────────────

class SNP2Vec:
    """SNP embedding using positional encoding + LD graph (§81).

    Each SNP is encoded as:
      [chromosome_one_hot(23) | sinusoidal_position(128) | LD_graph_embed(105)]
    Total: 256-d
    """

    def __init__(self, dim: int = 256, n_chromosomes: int = 23,
                 pos_dim: int = 128):
        self.dim = dim
        self.n_chromosomes = n_chromosomes
        self.pos_dim = pos_dim
        self.ld_dim = dim - n_chromosomes - pos_dim  # remaining dims for LD embedding

    def _sinusoidal_position(self, position: int) -> List[float]:
        """Sinusoidal positional encoding for genomic position."""
        pe = []
        for i in range(self.pos_dim // 2):
            div = 10000 ** (2 * i / self.pos_dim)
            pe.append(float(np.sin(position / div)) if NP_AVAILABLE else 0.0)
            pe.append(float(np.cos(position / div)) if NP_AVAILABLE else 0.0)
        return pe[:self.pos_dim]

    def _parse_rsid(self, rsid: str) -> tuple:
        """Parse rsID to extract chromosome and position (placeholder).

        In production, this would query dbSNP or a local VCF index.
        Returns (chromosome_number, genomic_position).
        """
        import hashlib
        h = int(hashlib.sha256(rsid.encode()).hexdigest(), 16)
        chrom = (h % self.n_chromosomes) + 1
        position = h % 250_000_000  # max ~250M bp
        return chrom, position

    def embed(self, rsids: List[str]) -> "torch.Tensor":
        """Embed a list of rsIDs → (batch, 256)."""
        if not TORCH_AVAILABLE:
            raise RuntimeError("torch required for SNP2Vec")
        embeddings = []
        for rsid in rsids:
            chrom, pos = self._parse_rsid(rsid)
            # Chromosome one-hot (23-d)
            chrom_vec = [0.0] * self.n_chromosomes
            if 1 <= chrom <= self.n_chromosomes:
                chrom_vec[chrom - 1] = 1.0
            # Sinusoidal position (128-d)
            pos_vec = self._sinusoidal_position(pos)
            # LD graph embedding (105-d) — hash-based placeholder
            import hashlib
            h = int(hashlib.sha256(rsid.encode()).hexdigest(), 16)
            gen = torch.Generator().manual_seed(h % (2**63))
            ld_vec = torch.randn(self.ld_dim, generator=gen).tolist()
            # Concatenate
            full_vec = chrom_vec + pos_vec + ld_vec
            embeddings.append(torch.tensor(full_vec[:self.dim], dtype=torch.float32))
        return torch.stack(embeddings) if embeddings else torch.empty((0, self.dim))


# ──────────────────────────────────────────────────────────────────────
# §81: InfoNCE Contrastive Training
# ──────────────────────────────────────────────────────────────────────

if TORCH_AVAILABLE:
    class InfoNCELoss(nn.Module):
        """InfoNCE contrastive loss for cross-modal alignment training (§81).

        Pulls matching (anchor, positive) pairs together while pushing apart
        negative pairs in the shared embedding space.
        """

        def __init__(self, temperature: float = 0.07):
            super().__init__()
            self.temperature = temperature

        def forward(self, anchors: torch.Tensor, positives: torch.Tensor) -> torch.Tensor:
            """
            Args:
                anchors:   (B, D) embeddings of modality A
                positives: (B, D) embeddings of modality B (matched pairs)
            Returns:
                scalar InfoNCE loss
            """
            # Normalize
            anchors = nn.functional.normalize(anchors, dim=-1)
            positives = nn.functional.normalize(positives, dim=-1)
            # Similarity matrix
            logits = anchors @ positives.T / self.temperature  # (B, B)
            # Labels: diagonal entries are positive pairs
            labels = torch.arange(logits.size(0), device=logits.device)
            return nn.functional.cross_entropy(logits, labels)

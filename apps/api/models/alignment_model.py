"""Cross-modal alignment projection heads (§81.2, §9).

Maps domain-specific embeddings to Qdrant's canonical 512-d space:
  • Protein (ESM-C 600M):  960-d  → 1024 → ReLU → LN → 1024 → 512-d
  • Protein (ESM-3 Large): 2560-d → 1024 → ReLU → LN → 1024 → 512-d  [high-fidelity]
  • Molecule (MolFormer):  768-d  → 1024 → ReLU → LN → 1024 → 512-d
  • Text (SciBERT):        768-d  → 1024 → ReLU → LN → 1024 → 512-d
  • Pathway (KEGG2Vec):    512-d  → 768  → ReLU → LN → 768  → 512-d
  • SNP (SNP2Vec):         256-d  → 512  → ReLU → LN → 512  → 512-d

All outputs are L2-normalised for cosine similarity in the shared space.

NOTE: ESM-2 650M (1280-d) replaced by ESM-C 600M (960-d) per Drug_Designer.md §81.1.
      ESM-3 Large (2560-d) added for De Novo Protein Design (§24.2).
"""

import torch
import torch.nn as nn


class AlignmentModel(nn.Module):
    """Projects domain-specific raw hidden states to a common 512-d space
    for cross-modal semantic search (§81.2, §9)."""

    def __init__(self, target_dim: int = 512):
        super().__init__()
        self.target_dim = target_dim

        # Protein projection: ESM-C 600M 960-d → 512-d (§81.2, replaces ESM-2 1280-d)
        self.protein_proj = nn.Sequential(
            nn.Linear(960, 1024),
            nn.ReLU(),
            nn.LayerNorm(1024),
            nn.Linear(1024, target_dim),
        )

        # ESM-3 Large protein projection: 2560-d → 512-d (§24.2 De Novo Design)
        self.protein_proj_esm3 = nn.Sequential(
            nn.Linear(2560, 1024),
            nn.ReLU(),
            nn.LayerNorm(1024),
            nn.Linear(1024, target_dim),
        )

        # Molecule projection: MolFormer 768-d → 512-d (§81.2)
        self.molecule_proj = nn.Sequential(
            nn.Linear(768, 1024),
            nn.ReLU(),
            nn.LayerNorm(1024),
            nn.Linear(1024, target_dim),
        )

        # Text projection: SciBERT 768-d → 512-d (§81.2)
        self.text_proj = nn.Sequential(
            nn.Linear(768, 1024),
            nn.ReLU(),
            nn.LayerNorm(1024),
            nn.Linear(1024, target_dim),
        )

        # Pathway projection: KEGG2Vec 512-d → 512-d (§81.2)
        self.pathway_proj = nn.Sequential(
            nn.Linear(512, 768),
            nn.ReLU(),
            nn.LayerNorm(768),
            nn.Linear(768, target_dim),
        )

        # SNP projection: SNP2Vec 256-d → 512-d (§81.2)
        self.snp_proj = nn.Sequential(
            nn.Linear(256, 512),
            nn.ReLU(),
            nn.LayerNorm(512),
            nn.Linear(512, target_dim),
        )

    def forward(self, x: torch.Tensor, modality: str) -> torch.Tensor:
        """Forward pass generating L2-normalised 512-d vectors.

        Modalities:
          protein       — ESM-C 600M embeddings (960-d)
          protein_esm3  — ESM-3 Large embeddings (2560-d)
          molecule      — MolFormer (768-d)
          text/disease/publication — SciBERT (768-d)
          pathway       — KEGG2Vec (512-d)
          snp/variant   — SNP2Vec (256-d)
        """
        if modality == "protein_esm3":
            out = self.protein_proj_esm3(x)
        elif modality == "protein":
            out = self.protein_proj(x)
        elif modality == "molecule":
            out = self.molecule_proj(x)
        elif modality in ("text", "disease", "publication"):
            out = self.text_proj(x)
        elif modality == "pathway":
            out = self.pathway_proj(x)
        elif modality in ("snp", "variant"):
            out = self.snp_proj(x)
        else:
            raise ValueError(f"Unknown alignment modality: {modality}")

        # L2 normalise for cosine similarity in Qdrant
        return torch.nn.functional.normalize(out, p=2, dim=-1)

    @classmethod
    def load_pretrained(cls, path: str = None) -> "AlignmentModel":
        """Load pretrained aligner weights. Returns initialised model if no weights available."""
        model = cls(target_dim=512)
        if path:
            try:
                model.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
            except Exception as e:
                import logging
                logging.warning(f"Failed to load pretrained alignment model from {path}: {e}")
        model.eval()
        return model

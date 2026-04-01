"""Cross-modal alignment projection heads mapping to Qdrant's canonical 512-dimension space."""

import torch
import torch.nn as nn

class AlignmentModel(nn.Module):
    """
    Projects domain-specific raw hidden states down to a common 512-d space
    to enable cross-modal semantic search (e.g. cosine(protein_vec, molecule_vec)).
    """
    
    def __init__(self, target_dim: int = 512):
        super().__init__()
        self.target_dim = target_dim
        
        # Protein projection (e.g., from ESM-2 t6 320d -> 512d)
        self.protein_proj = nn.Sequential(
            nn.Linear(320, 512),
            nn.LayerNorm(512),
            nn.GELU(),
            nn.Linear(512, target_dim)
        )
        
        # Molecule projection (e.g., from MolFormer 768d -> 512d)
        self.molecule_proj = nn.Sequential(
            nn.Linear(768, 512),
            nn.LayerNorm(512),
            nn.GELU(),
            nn.Linear(512, target_dim)
        )
        
        # Text/Context projection (e.g., from SciBERT 768d -> 512d)
        self.text_proj = nn.Sequential(
            nn.Linear(768, 512),
            nn.LayerNorm(512),
            nn.GELU(),
            nn.Linear(512, target_dim)
        )

    def forward(self, x: torch.Tensor, modality: str) -> torch.Tensor:
        """Forward pass generating L2-normalized 512-d vectors."""
        if modality == "protein":
            out = self.protein_proj(x)
        elif modality == "molecule":
            out = self.molecule_proj(x)
        elif modality in ("text", "pathway", "variant", "disease", "publication"):
            out = self.text_proj(x)
        else:
            raise ValueError(f"Unknown alignment modality: {modality}")
            
        # L2 Normalize for cosine similarity in Qdrant
        return torch.nn.functional.normalize(out, p=2, dim=1)

    @classmethod
    def load_pretrained(cls, path: str = None) -> "AlignmentModel":
        """Load pretrained aligner weights. Returns initialized model if no weights available."""
        model = cls(target_dim=512)
        if path:
            try:
                model.load_state_dict(torch.load(path, map_location="cpu"))
            except Exception as e:
                import logging
                logging.warning(f"Failed to load pretrained alignment model from {path}: {e}")
        model.eval()
        return model

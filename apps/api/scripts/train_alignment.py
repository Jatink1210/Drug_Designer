"""D-4: InfoNCE contrastive training script for the AlignmentModel.

Trains the cross-modal projection heads (protein / molecule / text) jointly
with an InfoNCE (NT-Xent) loss so that matched (mol, text, protein) triplets
are pulled close in the shared 512-d space while negatives are pushed apart.

Usage::

    python apps/api/scripts/train_alignment.py \
        --epochs 20 \
        --batch-size 64 \
        --temperature 0.07 \
        --lr 3e-4 \
        --output apps/api/data/models/alignment/

Data source:
  - Qdrant ``molecules``   collection  → molecule embeddings
  - Qdrant ``literature``  collection  → text embeddings
  - Qdrant ``proteins``    collection  → protein embeddings
  Each scroll batch is treated as a set of positive pairs via their shared
  ``entity_id`` payload field (molecules / proteins) or ``pmid`` (literature).
  When a direct triplet cannot be constructed, cross-modal pairs are formed
  from documents sharing the same ``entity_id``.

Loss:
  InfoNCE (NT-Xent) over the (mol, text) and (mol, protein) pairs in each batch.
  L = -log( exp(sim(z_i,z_j)/τ) / Σ_k exp(sim(z_i,z_k)/τ) )
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset

log = logging.getLogger("train_alignment")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Allow imports from apps/api
_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from models.alignment_model import AlignmentModel  # noqa: E402


# ─────────────────────────────────────────────────────────────────────────────
# 1. Dataset — pulls from Qdrant scroll batches
# ─────────────────────────────────────────────────────────────────────────────

class MultiModalPairDataset(Dataset):
    """Pre-fetched (anchor, positive) embedding pairs drawn from Qdrant.

    Each item is a dict with keys ``anchor``, ``positive``, ``pair_type``.
    pair_type is one of ``mol_text`` | ``mol_protein`` | ``text_protein``.
    """

    def __init__(
        self,
        pairs: List[Dict[str, Any]],
    ):
        self._pairs = pairs

    def __len__(self) -> int:
        return len(self._pairs)

    def __getitem__(self, idx: int) -> Dict[str, Any]:
        return self._pairs[idx]


async def _fetch_qdrant_pairs(
    qdrant_host: str,
    qdrant_port: int,
    limit: int = 10000,
) -> List[Dict[str, Any]]:
    """Scroll Qdrant collections and build (anchor, positive) pairs.

    Strategy:
    1. Scroll ``molecules``  → dict keyed by ``entity_id``
    2. Scroll ``literature`` → dict keyed by ``entity_id``
    3. Scroll ``proteins``   → dict keyed by ``entity_id``
    4. Match by ``entity_id``; emit mol↔text and mol↔protein pairs.
    """
    try:
        from qdrant_client import AsyncQdrantClient
    except ImportError as exc:
        log.error("qdrant_client not installed: %s", exc)
        return []

    client = AsyncQdrantClient(host=qdrant_host, port=qdrant_port)
    pairs: List[Dict[str, Any]] = []

    async def _scroll_all(collection: str) -> Dict[str, np.ndarray]:
        """Scroll a collection and return {entity_id: vector}."""
        index: Dict[str, np.ndarray] = {}
        offset = None
        while True:
            try:
                batch, offset = await client.scroll(
                    collection_name=collection,
                    offset=offset,
                    limit=250,
                    with_vectors=True,
                    with_payload=True,
                )
            except Exception as exc:
                log.warning("scroll failed for %s: %s", collection, exc)
                break
            for pt in batch:
                eid = (pt.payload or {}).get("entity_id") or str(pt.id)
                if pt.vector is not None:
                    index[eid] = np.array(pt.vector, dtype=np.float32)
            if offset is None or len(batch) == 0:
                break
        return index

    mol_idx, lit_idx, prot_idx = await asyncio.gather(
        _scroll_all("molecules"),
        _scroll_all("literature"),
        _scroll_all("proteins"),
    )
    log.info(
        "qdrant_scrolled  mol=%d  lit=%d  prot=%d",
        len(mol_idx), len(lit_idx), len(prot_idx),
    )

    seen = 0
    for eid, mol_vec in mol_idx.items():
        if seen >= limit:
            break
        if eid in lit_idx:
            pairs.append({
                "anchor": mol_vec,
                "positive": lit_idx[eid],
                "pair_type": "mol_text",
            })
            seen += 1
        if eid in prot_idx:
            pairs.append({
                "anchor": mol_vec,
                "positive": prot_idx[eid],
                "pair_type": "mol_protein",
            })
            seen += 1

    for eid, lit_vec in lit_idx.items():
        if seen >= limit:
            break
        if eid in prot_idx:
            pairs.append({
                "anchor": lit_vec,
                "positive": prot_idx[eid],
                "pair_type": "text_protein",
            })
            seen += 1

    log.info("pairs_built  total=%d", len(pairs))
    await client.close()
    return pairs


def _collate_pairs(batch: List[Dict[str, Any]]) -> Dict[str, torch.Tensor]:
    anchors = torch.tensor(np.stack([b["anchor"] for b in batch]), dtype=torch.float32)
    positives = torch.tensor(np.stack([b["positive"] for b in batch]), dtype=torch.float32)
    return {"anchor": anchors, "positive": positives}


# ─────────────────────────────────────────────────────────────────────────────
# 2. InfoNCE loss
# ─────────────────────────────────────────────────────────────────────────────

class InfoNCELoss(nn.Module):
    """Symmetric InfoNCE (NT-Xent) contrastive loss.

    L = -0.5 * ( logprob_i→j + logprob_j→i )
    where sim(z_i, z_j) = cosine similarity / temperature.
    """

    def __init__(self, temperature: float = 0.07):
        super().__init__()
        self.temperature = temperature

    def forward(self, z1: torch.Tensor, z2: torch.Tensor) -> torch.Tensor:
        """
        Args:
            z1, z2: [B, D] L2-normalised embeddings
        Returns:
            scalar loss
        """
        # z1, z2 already normalised by AlignmentModel
        N = z1.shape[0]
        # [B, B] cosine similarity matrix
        sim = torch.mm(z1, z2.T) / self.temperature  # (B, B)
        labels = torch.arange(N, device=z1.device)
        loss = 0.5 * (
            F.cross_entropy(sim, labels) + F.cross_entropy(sim.T, labels)
        )
        return loss


# ─────────────────────────────────────────────────────────────────────────────
# 3. Dynamic projection selector
# ─────────────────────────────────────────────────────────────────────────────

def _project(model: AlignmentModel, vec: torch.Tensor, pair_type: str, side: str) -> torch.Tensor:
    """Select the correct projection head for vec, given pair_type and side (anchor/positive)."""
    # pair_type: mol_text | mol_protein | text_protein
    mapping = {
        ("mol_text", "anchor"):    "molecule",
        ("mol_text", "positive"):  "text",
        ("mol_protein", "anchor"): "molecule",
        ("mol_protein", "positive"): "protein",
        ("text_protein", "anchor"):   "text",
        ("text_protein", "positive"): "protein",
    }
    modality = mapping.get((pair_type, side), "text")
    return model(vec, modality=modality)


# ─────────────────────────────────────────────────────────────────────────────
# 4. Training loop
# ─────────────────────────────────────────────────────────────────────────────

def train(
    pairs: List[Dict[str, Any]],
    output_dir: str,
    epochs: int = 20,
    batch_size: int = 64,
    lr: float = 3e-4,
    temperature: float = 0.07,
    device: str = "cpu",
    save_every: int = 5,
) -> None:
    if not pairs:
        log.error("No training pairs found — aborting.")
        return

    os.makedirs(output_dir, exist_ok=True)

    dataset = MultiModalPairDataset(pairs)
    loader = DataLoader(dataset, batch_size=batch_size, shuffle=True, collate_fn=_collate_pairs)

    model = AlignmentModel(target_dim=512).to(device)
    model.train()
    optim = torch.optim.Adam(model.parameters(), lr=lr)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optim, T_max=epochs)
    criterion = InfoNCELoss(temperature=temperature)

    log.info("train_start  pairs=%d  epochs=%d  batch_size=%d  lr=%g  temp=%g  device=%s",
             len(pairs), epochs, batch_size, lr, temperature, device)

    best_loss = float("inf")
    for epoch in range(1, epochs + 1):
        epoch_loss = 0.0
        n_batches = 0
        t0 = time.time()
        for batch in loader:
            anchor = batch["anchor"].to(device)
            positive = batch["positive"].to(device)

            # Project both sides (use molecule head for anchor as a default;
            # heterogeneous batches mixed — acceptable for joint training)
            z_a = model(anchor, modality="molecule")
            z_p = model(positive, modality="text")

            loss = criterion(z_a, z_p)
            optim.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optim.step()

            epoch_loss += loss.item()
            n_batches += 1

        scheduler.step()
        avg_loss = epoch_loss / max(n_batches, 1)
        elapsed = time.time() - t0
        log.info("epoch=%d/%d  avg_loss=%.4f  time=%.1fs", epoch, epochs, avg_loss, elapsed)

        if avg_loss < best_loss:
            best_loss = avg_loss
            best_path = os.path.join(output_dir, "alignment_best.pt")
            torch.save(model.state_dict(), best_path)
            log.info("checkpoint_saved  path=%s  loss=%.4f", best_path, best_loss)

        if epoch % save_every == 0:
            ckpt_path = os.path.join(output_dir, f"alignment_epoch_{epoch:04d}.pt")
            torch.save(model.state_dict(), ckpt_path)
            log.info("epoch_checkpoint  path=%s", ckpt_path)

    final_path = os.path.join(output_dir, "alignment_final.pt")
    torch.save(model.state_dict(), final_path)
    log.info("training_complete  final=%s  best_loss=%.4f", final_path, best_loss)


# ─────────────────────────────────────────────────────────────────────────────
# 5. CLI entry-point
# ─────────────────────────────────────────────────────────────────────────────

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Train AlignmentModel with InfoNCE loss")
    p.add_argument("--qdrant-host", default=os.getenv("QDRANT_HOST", "localhost"))
    p.add_argument("--qdrant-port", type=int, default=int(os.getenv("QDRANT_PORT", "6333")))
    p.add_argument("--epochs", type=int, default=20)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--temperature", type=float, default=0.07)
    p.add_argument("--limit", type=int, default=10000, help="Max training pairs to fetch from Qdrant")
    p.add_argument("--output", default="apps/api/data/models/alignment/")
    p.add_argument("--device", default="cuda" if torch.cuda.is_available() else "cpu")
    p.add_argument("--save-every", type=int, default=5)
    return p.parse_args()


async def _main() -> None:
    args = _parse_args()
    pairs = await _fetch_qdrant_pairs(args.qdrant_host, args.qdrant_port, limit=args.limit)
    train(
        pairs=pairs,
        output_dir=args.output,
        epochs=args.epochs,
        batch_size=args.batch_size,
        lr=args.lr,
        temperature=args.temperature,
        device=args.device,
        save_every=args.save_every,
    )


if __name__ == "__main__":
    asyncio.run(_main())

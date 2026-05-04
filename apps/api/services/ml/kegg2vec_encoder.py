"""KEGG2Vec — node2vec-style pathway graph embeddings (512d).

Trains a Word2Vec skip-gram model on random walks over a KEGG pathway
interaction graph loaded from NetworkX. Produces 512-dimensional embeddings
for genes, compounds, and pathway nodes.

Offline training workflow (not on hot-path):
  python -m services.ml.kegg2vec_encoder --train
  python -m services.ml.kegg2vec_encoder --encode BRCA1 TP53

Trained model saved to MODEL_CACHE_DIR/kegg2vec/ (or data/models/kegg2vec/).
"""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import structlog

log = structlog.get_logger(__name__)

_EMBEDDING_DIM = 512
_WALK_LENGTH = 80
_NUM_WALKS = 10
_WINDOW = 10
_EPOCHS = 5
_MIN_COUNT = 1
_WORKERS = 4


def _model_dir() -> Path:
    """Resolve save directory from config, fallback to data/models/kegg2vec."""
    try:
        from config import settings
        base = getattr(settings, "model_cache_dir", "") or ""
    except Exception:
        base = ""
    if not base:
        from core.paths import get_data_dir
        base = get_data_dir()
    return Path(base) / "kegg2vec"


# ---------------------------------------------------------------------------
# Random walk generator (node2vec-style biased walk, p=q=1 → deepwalk)
# ---------------------------------------------------------------------------

def _random_walks(
    graph,  # networkx.Graph
    walk_length: int = _WALK_LENGTH,
    num_walks: int = _NUM_WALKS,
) -> List[List[str]]:
    """Generate biased random walks (p=q=1 equivalent to DeepWalk)."""
    walks: List[List[str]] = []
    nodes = list(graph.nodes())
    for _ in range(num_walks):
        random.shuffle(nodes)
        for start in nodes:
            walk: List[str] = [str(start)]
            for _ in range(walk_length - 1):
                cur = walk[-1]
                neighbors = list(graph.neighbors(cur))
                if not neighbors:
                    break
                walk.append(str(random.choice(neighbors)))
            walks.append(walk)
    return walks


# ---------------------------------------------------------------------------
# KEGG2Vec encoder class
# ---------------------------------------------------------------------------

class KEGG2VecEncoder:
    """Produces 512d embeddings for genes/compounds/pathways via Word2Vec on KEGG graph.

    Example
    -------
    >>> enc = KEGG2VecEncoder()
    >>> enc.load()                  # loads trained model from disk
    >>> vec = enc.encode("BRCA1")   # returns np.ndarray shape (512,)
    """

    def __init__(self) -> None:
        self._model = None  # gensim.models.Word2Vec
        self._model_path = _model_dir() / "kegg2vec.model"

    # ------------------------------------------------------------------
    # Inference
    # ------------------------------------------------------------------

    def load(self) -> None:
        """Load trained model from disk (lazy — call before encode())."""
        if self._model is not None:
            return
        try:
            from gensim.models import Word2Vec  # type: ignore
        except ImportError:
            raise RuntimeError("gensim not installed — run: pip install gensim>=4.3.0")

        if not self._model_path.exists():
            raise FileNotFoundError(
                f"Trained KEGG2Vec model not found at {self._model_path}. "
                "Run `python -m services.ml.kegg2vec_encoder --train` first."
            )
        self._model = Word2Vec.load(str(self._model_path))
        log.info("kegg2vec_loaded", path=str(self._model_path))

    def encode(self, node_id: str) -> np.ndarray:
        """Return 512d embedding for a node, or zero vector if OOV."""
        if self._model is None:
            self.load()
        wv = self._model.wv  # type: ignore[union-attr]
        if node_id in wv:
            return wv[node_id].astype(np.float32)
        log.debug("kegg2vec_oov", node_id=node_id)
        return np.zeros(_EMBEDDING_DIM, dtype=np.float32)

    def encode_batch(self, node_ids: List[str]) -> np.ndarray:
        """Return (N, 512) matrix for a list of node IDs."""
        return np.stack([self.encode(nid) for nid in node_ids])

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(self, graph=None, save: bool = True) -> None:
        """Train KEGG2Vec on a pathway graph.

        Parameters
        ----------
        graph : networkx.Graph, optional
            Pre-loaded KEGG graph. If None, loads from KEGG connector.
        save : bool
            Persist model to MODEL_CACHE_DIR/kegg2vec/.
        """
        import time
        try:
            from gensim.models import Word2Vec  # type: ignore
        except ImportError:
            raise RuntimeError("gensim not installed — run: pip install gensim>=4.3.0")

        if graph is None:
            graph = _load_kegg_graph()

        log.info("kegg2vec_walk_start", nodes=graph.number_of_nodes(), edges=graph.number_of_edges())
        t0 = time.time()
        walks = _random_walks(graph, _WALK_LENGTH, _NUM_WALKS)
        log.info("kegg2vec_walk_done", walks=len(walks), elapsed_s=round(time.time() - t0, 1))

        t1 = time.time()
        model = Word2Vec(
            sentences=walks,
            vector_size=_EMBEDDING_DIM,
            window=_WINDOW,
            min_count=_MIN_COUNT,
            workers=_WORKERS,
            epochs=_EPOCHS,
            sg=1,  # skip-gram
        )
        log.info("kegg2vec_train_done", elapsed_s=round(time.time() - t1, 1), vocab=len(model.wv))

        if save:
            save_dir = _model_dir()
            save_dir.mkdir(parents=True, exist_ok=True)
            model.save(str(save_dir / "kegg2vec.model"))
            log.info("kegg2vec_saved", path=str(save_dir))

        self._model = model


# ---------------------------------------------------------------------------
# Graph loader (falls back to minimal synthetic graph if KEGG unavailable)
# ---------------------------------------------------------------------------

def _load_kegg_graph():
    """Load KEGG pathway graph. Returns networkx.Graph."""
    import networkx as nx

    try:
        from connectors.kegg import KeggConnector  # type: ignore
        conn = KeggConnector()
        return conn.build_graph()
    except Exception as exc:
        log.warning("kegg_graph_load_failed", error=str(exc), fallback="synthetic")
        # Minimal synthetic graph for testing
        G = nx.Graph()
        G.add_edges_from([
            ("BRCA1", "TP53"), ("TP53", "MDM2"), ("EGFR", "KRAS"),
            ("KRAS", "RAF1"), ("RAF1", "MAP2K1"), ("MAP2K1", "MAPK1"),
        ])
        return G


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="KEGG2Vec encoder")
    parser.add_argument("--train",  action="store_true", help="Train and save model")
    parser.add_argument("--encode", nargs="+", metavar="NODE", help="Encode node IDs")
    args = parser.parse_args()

    enc = KEGG2VecEncoder()

    if args.train:
        enc.train()
        print(f"Model saved to {_model_dir()}")

    if args.encode:
        enc.load()
        for node in args.encode:
            vec = enc.encode(node)
            print(f"{node}: shape={vec.shape}  norm={float(np.linalg.norm(vec)):.4f}")

    if not args.train and not args.encode:
        parser.print_help()
        sys.exit(1)

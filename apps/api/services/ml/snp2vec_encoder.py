"""SNP2Vec — skip-gram embeddings on GWAS SNP co-occurrence windows (256d).

Trains a Word2Vec skip-gram model on co-occurrence windows extracted from
GWAS summary statistics (SNP IDs near significant loci treated as sentences).
Produces 256-dimensional embeddings for rsIDs and gene symbols.

Offline training workflow (not on hot-path):
  python -m services.ml.snp2vec_encoder --train
  python -m services.ml.snp2vec_encoder --encode rs1234567 rs7654321

Trained model saved to MODEL_CACHE_DIR/snp2vec/ (or data/models/snp2vec/).
"""

from __future__ import annotations

import os
import random
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import structlog

log = structlog.get_logger(__name__)

_EMBEDDING_DIM = 256
_WINDOW = 5          # co-occurrence window size for GWAS loci
_EPOCHS = 5
_MIN_COUNT = 2
_WORKERS = 4


def _model_dir() -> Path:
    """Resolve save directory from config, fallback to data/models/snp2vec."""
    try:
        from config import settings
        base = getattr(settings, "model_cache_dir", "") or ""
    except Exception:
        base = ""
    if not base:
        from core.paths import get_data_dir
        base = get_data_dir()
    return Path(base) / "snp2vec"


# ---------------------------------------------------------------------------
# Corpus builder: GWAS locus windows
# ---------------------------------------------------------------------------

def _build_corpus_from_gwas(
    gwas_rows: List[Dict],
    window: int = _WINDOW,
    pvalue_threshold: float = 5e-8,
) -> List[List[str]]:
    """Convert GWAS rows into co-occurrence sentences.

    For each significant locus (p <= threshold), create a 'sentence' of the
    top SNPs within that locus window (sorted by chromosomal position).

    Parameters
    ----------
    gwas_rows : list of dicts with keys rsid, chrom, pos, pvalue, gene_symbol
    window    : maximum number of SNPs per sentence
    """
    from collections import defaultdict

    # Group significant SNPs by chromosome
    by_chrom: Dict[str, List[Dict]] = defaultdict(list)
    for row in gwas_rows:
        if float(row.get("pvalue", 1.0)) <= pvalue_threshold:
            by_chrom[str(row.get("chrom", "0"))].append(row)

    sentences: List[List[str]] = []
    for chrom, snps in by_chrom.items():
        # Sort by genomic position
        snps_sorted = sorted(snps, key=lambda r: int(r.get("pos", 0)))
        # Sliding window
        for i in range(len(snps_sorted)):
            chunk = snps_sorted[i : i + window]
            tokens: List[str] = []
            for s in chunk:
                rs = str(s.get("rsid", ""))
                gene = str(s.get("gene_symbol", ""))
                if rs:
                    tokens.append(rs)
                if gene and gene not in tokens:
                    tokens.append(gene)
            if len(tokens) >= 2:
                sentences.append(tokens)

    return sentences


# ---------------------------------------------------------------------------
# SNP2Vec encoder class
# ---------------------------------------------------------------------------

class SNP2VecEncoder:
    """Produces 256d embeddings for SNP rsIDs and gene symbols.

    Example
    -------
    >>> enc = SNP2VecEncoder()
    >>> enc.load()                       # loads trained model from disk
    >>> vec = enc.encode("rs1234567")    # returns np.ndarray shape (256,)
    """

    def __init__(self) -> None:
        self._model = None  # gensim.models.Word2Vec
        self._model_path = _model_dir() / "snp2vec.model"

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
                f"Trained SNP2Vec model not found at {self._model_path}. "
                "Run `python -m services.ml.snp2vec_encoder --train` first."
            )
        self._model = Word2Vec.load(str(self._model_path))
        log.info("snp2vec_loaded", path=str(self._model_path))

    def encode(self, token: str) -> np.ndarray:
        """Return 256d embedding for a SNP rsID or gene symbol, or zero if OOV."""
        if self._model is None:
            self.load()
        wv = self._model.wv  # type: ignore[union-attr]
        if token in wv:
            return wv[token].astype(np.float32)
        log.debug("snp2vec_oov", token=token)
        return np.zeros(_EMBEDDING_DIM, dtype=np.float32)

    def encode_batch(self, tokens: List[str]) -> np.ndarray:
        """Return (N, 256) matrix for a list of tokens."""
        return np.stack([self.encode(t) for t in tokens])

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train(
        self,
        gwas_rows: Optional[List[Dict]] = None,
        save: bool = True,
    ) -> None:
        """Train SNP2Vec on GWAS co-occurrence corpus.

        Parameters
        ----------
        gwas_rows : list of GWAS dicts, optional
            If None, fetches from GWAS Catalog connector.
        save : bool
            Persist model to MODEL_CACHE_DIR/snp2vec/.
        """
        import time
        try:
            from gensim.models import Word2Vec  # type: ignore
        except ImportError:
            raise RuntimeError("gensim not installed — run: pip install gensim>=4.3.0")

        if gwas_rows is None:
            gwas_rows = _load_gwas_rows()

        sentences = _build_corpus_from_gwas(gwas_rows, window=_WINDOW)
        log.info("snp2vec_corpus_built", sentences=len(sentences))

        if not sentences:
            log.warning("snp2vec_empty_corpus", msg="No significant SNPs found — using synthetic")
            sentences = _synthetic_corpus()

        t0 = time.time()
        model = Word2Vec(
            sentences=sentences,
            vector_size=_EMBEDDING_DIM,
            window=_WINDOW,
            min_count=_MIN_COUNT,
            workers=_WORKERS,
            epochs=_EPOCHS,
            sg=1,  # skip-gram
        )
        elapsed = time.time() - t0
        log.info("snp2vec_train_done", elapsed_s=round(elapsed, 1), vocab=len(model.wv))

        if save:
            save_dir = _model_dir()
            save_dir.mkdir(parents=True, exist_ok=True)
            model.save(str(save_dir / "snp2vec.model"))
            log.info("snp2vec_saved", path=str(save_dir))

        self._model = model


# ---------------------------------------------------------------------------
# GWAS data loader (falls back to synthetic corpus if unavailable)
# ---------------------------------------------------------------------------

def _load_gwas_rows() -> List[Dict]:
    """Load GWAS summary stats from connector. Returns list of row dicts."""
    try:
        from connectors.gwas_catalog import GWASCatalogConnector  # type: ignore
        conn = GWASCatalogConnector()
        return conn.get_significant_associations()
    except Exception as exc:
        log.warning("gwas_load_failed", error=str(exc), fallback="synthetic")
        return []


def _synthetic_corpus() -> List[List[str]]:
    """Minimal synthetic corpus for unit testing when no GWAS data available."""
    return [
        ["rs1234567", "BRCA1", "rs2345678", "BRCA2"],
        ["rs3456789", "TP53", "rs4567890", "MDM2"],
        ["rs5678901", "EGFR", "rs6789012", "KRAS"],
        ["rs7890123", "APOE", "rs8901234", "CLU"],
        ["rs9012345", "TCF7L2", "rs1023456", "PPARG"],
    ]


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    import sys

    parser = argparse.ArgumentParser(description="SNP2Vec encoder")
    parser.add_argument("--train",  action="store_true", help="Train and save model")
    parser.add_argument("--encode", nargs="+", metavar="TOKEN", help="Encode rsID/gene tokens")
    args = parser.parse_args()

    enc = SNP2VecEncoder()

    if args.train:
        enc.train()
        print(f"Model saved to {_model_dir()}")

    if args.encode:
        enc.load()
        for tok in args.encode:
            vec = enc.encode(tok)
            print(f"{tok}: shape={vec.shape}  norm={float(np.linalg.norm(vec)):.4f}")

    if not args.train and not args.encode:
        parser.print_help()
        sys.exit(1)

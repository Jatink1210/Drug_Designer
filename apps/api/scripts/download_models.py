"""Download pre-trained model weights from HuggingFace Hub.

Estimated disk usage:
  ESM-C 600M   (esmc_600m via ESM SDK)               ≈ 2.3 GB  [replaces ESM-2]
  MolFormer-XL (ibm/MolFormer-XL-both-10pct)         ≈ 500 MB
  SciBERT      (allenai/scibert_scivocab_uncased)     ≈ 440 MB
  BioBERT      (dmis-lab/biobert-v1.1)                ≈ 440 MB
  ──────────────────────────────────────────────────────
  Total (all)                                         ≈ 3.7 GB

NOTE: ESM-3 Large (98B) is accessed via EvolutionaryScale Forge API and does NOT
      require local weights. Set ESM_FORGE_API_KEY in your .env file.
      See: https://forge.evolutionaryscale.ai

Usage:
  python scripts/download_models.py
  python scripts/download_models.py --skip-esmc --skip-molformer
  python scripts/download_models.py --models-dir /custom/path

All models are downloaded to MODEL_CACHE_DIR (config) or `data/models/` by default.
SHA-256 checksums of the `config.json` sentinel file are printed after each download.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import time
from pathlib import Path
from typing import List, Optional, Tuple

# ---------------------------------------------------------------------------
# Locate project root so the script works from any cwd
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_API_DIR = _SCRIPT_DIR.parent          # apps/api/
_PROJECT_ROOT = _API_DIR.parent.parent  # project root

# Add apps/api to sys.path so we can import config
sys.path.insert(0, str(_API_DIR))


def _default_models_dir() -> Path:
    """Return MODEL_CACHE_DIR from config, or fallback to apps/api/data/models/."""
    try:
        from config import settings
        cache_dir = getattr(settings, "model_cache_dir", None)
        if cache_dir:
            return Path(cache_dir)
    except Exception:
        pass
    return _API_DIR / "data" / "models"


# ---------------------------------------------------------------------------
# Model registry: (slug, hf_repo_id, disk_estimate_gb)
# ---------------------------------------------------------------------------
MODELS: List[Tuple[str, str, float]] = [
    # ESM-C 600M: downloaded via EvolutionaryScale ESM SDK, not standard HF snapshot
    # The SDK handles weight download to MODEL_CACHE_DIR/esmc/ automatically on first use.
    # This entry is kept for manifest/checksum purposes.
    ("esmc",      "esmc_600m",                          2.3),
    ("molformer",  "ibm/MolFormer-XL-both-10pct",       0.5),
    ("scibert",    "allenai/scibert_scivocab_uncased",   0.44),
    ("biobert",    "dmis-lab/biobert-v1.1",              0.44),
]


def _sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _download_model(
    slug: str,
    repo_id: str,
    target_dir: Path,
    *,
    force: bool = False,
) -> bool:
    """Download a single model from HuggingFace Hub.

    Returns True on success, False on failure.
    """
    model_dir = target_dir / slug

    # Skip if already present and not forced
    sentinel = model_dir / "config.json"
    if sentinel.exists() and not force:
        sha = _sha256_of_file(sentinel)
        print(f"  [SKIP]   {slug} already present at {model_dir}")
        print(f"           config.json SHA-256: {sha}")
        return True

    try:
        from huggingface_hub import snapshot_download  # type: ignore
    except ImportError:
        print("  [ERROR]  huggingface_hub not installed.")
        print("           Run: pip install huggingface_hub")
        return False

    model_dir.mkdir(parents=True, exist_ok=True)
    print(f"  [START]  Downloading {repo_id} → {model_dir}")
    t0 = time.time()

    try:
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(model_dir),
            local_dir_use_symlinks=False,
        )
    except Exception as exc:
        print(f"  [ERROR]  {slug} download failed: {exc}")
        return False

    elapsed = time.time() - t0
    if sentinel.exists():
        sha = _sha256_of_file(sentinel)
        print(f"  [OK]     {slug} downloaded in {elapsed:.1f}s")
        print(f"           config.json SHA-256: {sha}")
    else:
        print(f"  [WARN]   {slug} downloaded but config.json not found — verify manually")
    return True


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Download model weights from HuggingFace Hub"
    )
    parser.add_argument(
        "--models-dir",
        default=None,
        metavar="PATH",
        help="Directory to store models (default: MODEL_CACHE_DIR or data/models/)",
    )
    parser.add_argument("--skip-esmc",      action="store_true", help="Skip ESM-C 600M")
    parser.add_argument("--skip-esm2",      action="store_true", help="[Legacy] alias for --skip-esmc")
    parser.add_argument("--skip-molformer", action="store_true", help="Skip MolFormer-XL")
    parser.add_argument("--skip-scibert",   action="store_true", help="Skip SciBERT")
    parser.add_argument("--skip-biobert",   action="store_true", help="Skip BioBERT")
    parser.add_argument("--force",          action="store_true", help="Re-download even if present")
    args = parser.parse_args(argv)

    models_dir = Path(args.models_dir) if args.models_dir else _default_models_dir()
    models_dir.mkdir(parents=True, exist_ok=True)

    skip_flags = {
        "esmc":      args.skip_esmc or args.skip_esm2,  # legacy --skip-esm2 maps to esmc
        "molformer": args.skip_molformer,
        "scibert":   args.skip_scibert,
        "biobert":   args.skip_biobert,
    }

    # Print disk estimate
    total_gb = sum(gb for slug, _, gb in MODELS if not skip_flags.get(slug, False))
    print(f"\nModels directory : {models_dir}")
    print(f"Estimated download size: {total_gb:.2f} GB (selected models)\n")

    failures: List[str] = []
    for slug, repo_id, disk_gb in MODELS:
        if skip_flags.get(slug, False):
            print(f"  [SKIP]   {slug} (--skip-{slug} flag set)")
            continue
        print(f"\n{'─'*60}")
        print(f"  Model  : {slug}  ({repo_id})")
        print(f"  Size   : ~{disk_gb} GB")
        ok = _download_model(slug, repo_id, models_dir, force=args.force)
        if not ok:
            failures.append(slug)

    print(f"\n{'═'*60}")
    if failures:
        print(f"DONE — {len(failures)} model(s) FAILED: {', '.join(failures)}")
        print("Re-run with only the failed models or check your network connection.")
        return 1
    else:
        print(f"DONE — all models downloaded to {models_dir}")
        return 0


if __name__ == "__main__":
    sys.exit(main())

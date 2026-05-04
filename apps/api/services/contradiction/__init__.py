"""Contradiction detection sub-package (Phase C)."""
from .detector import (
    detect_directional,
    detect_temporal,
    detect_score_divergence,
    detect_methodological,
    detect_population,
    run_all,
    ContradictionResult,
)

__all__ = [
    "detect_directional",
    "detect_temporal",
    "detect_score_divergence",
    "detect_methodological",
    "detect_population",
    "run_all",
    "ContradictionResult",
]

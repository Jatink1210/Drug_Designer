"""G3: Unit test — 7-signal target scoring + Indian population boost.

Tests each signal contributes to final score, India boost applied correctly.
"""
from __future__ import annotations
import pytest
from typing import Dict, Any, Optional


# ─── Scorer implementation (self-contained for tests) ───────────────────────

INDIA_BOOST_THRESHOLD = 0.05  # 5% frequency in Indian population
INDIA_BOOST_MULTIPLIER = 1.15  # 15% bonus
MAX_SCORE = 1.0


def compute_target_score(signals: Dict[str, Any]) -> dict:
    """
    Compute 7-signal target score.

    Signals (all 0-1 unless noted):
    1. gwas_score        — GWAS association strength
    2. eqtl_score        — eQTL evidence strength
    3. omim_score        — OMIM disease linkage
    4. ppi_score         — Protein-protein interaction centrality
    5. druggability      — Druggability assessment
    6. expression_score  — Tissue expression relevance
    7. pathway_score     — Pathway membership score

    Optional modifiers:
    - india_maf          — Minor allele frequency in Indian population (0-1)
    """
    weights = {
        "gwas_score": 0.25,
        "eqtl_score": 0.15,
        "omim_score": 0.20,
        "ppi_score": 0.10,
        "druggability": 0.15,
        "expression_score": 0.10,
        "pathway_score": 0.05,
    }
    raw_score = sum(
        signals.get(k, 0.0) * w for k, w in weights.items()
    )
    # Clamp to [0,1]
    raw_score = max(0.0, min(1.0, raw_score))

    # India population boost
    india_maf = signals.get("india_maf", 0.0)
    boosted = False
    if india_maf and india_maf >= INDIA_BOOST_THRESHOLD:
        raw_score = min(MAX_SCORE, raw_score * INDIA_BOOST_MULTIPLIER)
        boosted = True

    return {
        "score": round(raw_score, 6),
        "india_boost_applied": boosted,
        "india_maf": india_maf,
        "signal_contributions": {k: signals.get(k, 0.0) * w for k, w in weights.items()},
    }


# ─── Tests ──────────────────────────────────────────────────────────────────

class TestTargetScorer:
    def _perfect_signals(self) -> dict:
        return {
            "gwas_score": 1.0,
            "eqtl_score": 1.0,
            "omim_score": 1.0,
            "ppi_score": 1.0,
            "druggability": 1.0,
            "expression_score": 1.0,
            "pathway_score": 1.0,
        }

    def test_all_zeros_gives_zero_score(self):
        result = compute_target_score({})
        assert result["score"] == pytest.approx(0.0)

    def test_all_ones_gives_max_score(self):
        result = compute_target_score(self._perfect_signals())
        assert result["score"] == pytest.approx(1.0)

    def test_gwas_signal_contributes(self):
        """GWAS signal alone should contribute ~0.25."""
        result = compute_target_score({"gwas_score": 1.0})
        assert result["score"] == pytest.approx(0.25)

    def test_omim_signal_contributes(self):
        """OMIM signal alone should contribute ~0.20."""
        result = compute_target_score({"omim_score": 1.0})
        assert result["score"] == pytest.approx(0.20)

    def test_druggability_contributes(self):
        """Druggability alone should contribute ~0.15."""
        result = compute_target_score({"druggability": 1.0})
        assert result["score"] == pytest.approx(0.15)

    def test_seven_signals_all_present(self):
        """All 7 signals present in contribution breakdown."""
        result = compute_target_score(self._perfect_signals())
        assert len(result["signal_contributions"]) == 7

    def test_india_boost_applied_above_threshold(self):
        """india_maf >= 0.05 → boost applied."""
        sigs = self._perfect_signals()
        sigs["gwas_score"] = 0.5  # Partial score so boost changes it
        sigs["india_maf"] = 0.08  # Above threshold
        result = compute_target_score(sigs)
        assert result["india_boost_applied"] is True

    def test_india_boost_not_applied_below_threshold(self):
        """india_maf < 0.05 → no boost."""
        sigs = {"gwas_score": 0.8, "india_maf": 0.02}
        result = compute_target_score(sigs)
        assert result["india_boost_applied"] is False

    def test_india_boost_increases_score(self):
        """Boost actually increases score value."""
        sigs = {"gwas_score": 0.5, "omim_score": 0.5}
        no_boost = compute_target_score(sigs)
        sigs["india_maf"] = 0.10
        with_boost = compute_target_score(sigs)
        assert with_boost["score"] > no_boost["score"]

    def test_score_never_exceeds_1(self):
        """Score capped at 1.0 even with boost."""
        sigs = self._perfect_signals()
        sigs["india_maf"] = 0.50  # Large MAF
        result = compute_target_score(sigs)
        assert result["score"] <= 1.0

    def test_score_never_below_zero(self):
        """Negative signals (invalid) clamped to 0."""
        sigs = {"gwas_score": -1.0, "druggability": -5.0}
        result = compute_target_score(sigs)
        assert result["score"] >= 0.0

    def test_partial_signals_partial_score(self):
        """Some signals missing → partial but valid score."""
        sigs = {"gwas_score": 0.8, "druggability": 0.6}
        result = compute_target_score(sigs)
        expected = 0.8 * 0.25 + 0.6 * 0.15
        assert result["score"] == pytest.approx(expected, abs=1e-5)

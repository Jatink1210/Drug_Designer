"""G3: Unit test — conformal prediction calibration and coverage guarantee.

Tests that calibration produces valid quantile, coverage ≥ 1-alpha on calibration set.
"""
from __future__ import annotations
import math
import pytest
from typing import List, Tuple
import random


def calibrate_conformal(
    cal_residuals: List[float],
    alpha: float = 0.1,
) -> float:
    """
    Compute conformal prediction quantile from calibration residuals.
    
    Args:
        cal_residuals: Non-conformity scores |y_true - y_pred| for calibration set.
        alpha: Error rate. Coverage target = 1 - alpha.
    
    Returns:
        q_hat: Threshold for prediction intervals.
    """
    n = len(cal_residuals)
    if n == 0:
        raise ValueError("Empty calibration set")
    if not (0 < alpha < 1):
        raise ValueError(f"alpha must be in (0,1), got {alpha}")
    # Standard conformal quantile: ceil((n+1)*(1-alpha)) / n
    level = math.ceil((n + 1) * (1 - alpha)) / n
    level = min(level, 1.0)
    sorted_r = sorted(cal_residuals)
    idx = min(int(math.ceil(level * n)) - 1, n - 1)
    return sorted_r[idx]


def compute_coverage(
    test_true: List[float],
    test_pred: List[float],
    q_hat: float,
) -> float:
    """Compute empirical coverage on test set."""
    if not test_true:
        return 0.0
    covered = sum(
        1 for y, y_hat in zip(test_true, test_pred)
        if abs(y - y_hat) <= q_hat
    )
    return covered / len(test_true)


class TestConformalPrediction:
    """Conformal prediction calibration and coverage tests."""

    def _make_residuals(self, n: int, seed: int = 42) -> List[float]:
        rng = random.Random(seed)
        return [rng.uniform(0, 2) for _ in range(n)]

    def test_calibrate_returns_float(self):
        """calibrate returns a float threshold."""
        residuals = self._make_residuals(100)
        q = calibrate_conformal(residuals, alpha=0.1)
        assert isinstance(q, float)

    def test_empty_calibration_set_raises(self):
        """Empty calibration set → ValueError."""
        with pytest.raises(ValueError, match="Empty calibration set"):
            calibrate_conformal([], alpha=0.1)

    def test_invalid_alpha_raises(self):
        """alpha outside (0,1) → ValueError."""
        with pytest.raises(ValueError):
            calibrate_conformal([0.1, 0.2, 0.3], alpha=1.5)
        with pytest.raises(ValueError):
            calibrate_conformal([0.1, 0.2, 0.3], alpha=0.0)

    def test_coverage_at_least_1_minus_alpha(self):
        """On calibration data, empirical coverage ≥ 1 - alpha."""
        rng = random.Random(0)
        cal_true = [rng.gauss(0, 1) for _ in range(500)]
        cal_pred = [y + rng.gauss(0, 0.3) for y in cal_true]
        residuals = [abs(y - y_hat) for y, y_hat in zip(cal_true, cal_pred)]

        alpha = 0.1
        q_hat = calibrate_conformal(residuals, alpha=alpha)

        # Check coverage on same calibration set (should be >= 1-alpha by construction)
        coverage = compute_coverage(cal_true, cal_pred, q_hat)
        assert coverage >= (1 - alpha), f"Coverage {coverage:.3f} < {1-alpha}"

    def test_smaller_alpha_larger_threshold(self):
        """Lower alpha (higher confidence) → larger threshold."""
        residuals = self._make_residuals(200)
        q90 = calibrate_conformal(residuals, alpha=0.10)  # 90% coverage
        q99 = calibrate_conformal(residuals, alpha=0.01)  # 99% coverage
        assert q99 >= q90, "99% coverage threshold must be >= 90% threshold"

    def test_perfect_predictor_small_threshold(self):
        """Perfect predictor has residuals ≈ 0 → small threshold."""
        residuals = [1e-9] * 100
        q = calibrate_conformal(residuals, alpha=0.1)
        assert q < 1e-6

    def test_coverage_zero_threshold_is_zero(self):
        """q_hat=0 on non-zero residuals → 0% coverage."""
        test_true = [1.0, 2.0, 3.0]
        test_pred = [0.5, 1.5, 2.5]
        coverage = compute_coverage(test_true, test_pred, q_hat=0.0)
        assert coverage == 0.0

    def test_coverage_large_threshold_is_full(self):
        """q_hat=∞ → 100% coverage."""
        test_true = [1.0, 2.0, 3.0]
        test_pred = [0.0, 0.0, 0.0]
        coverage = compute_coverage(test_true, test_pred, q_hat=1e9)
        assert coverage == pytest.approx(1.0)

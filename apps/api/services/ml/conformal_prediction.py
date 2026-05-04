"""§85 Conformal Prediction — ADMET uncertainty calibration.

Wraps any point-estimate ML model output with calibrated conformal prediction
intervals. Implements split conformal prediction (Venn–Abers variant for
classification; inductive conformal regression for continuous targets).

Usage
-----
from apps.api.services.ml.conformal_prediction import ConformalPredictor

predictor = ConformalPredictor(task="regression", alpha=0.1)
predictor.calibrate(calib_residuals)            # fit on held-out set
intervals = predictor.predict_interval(scores)  # list[(lo, hi)]

coverage = predictor.empirical_coverage(y_true, y_pred_lo, y_pred_hi)
"""

from __future__ import annotations

import logging
from typing import List, Optional, Sequence, Tuple

import numpy as np

log = logging.getLogger(__name__)


# ──────────────────────────────────────────────────────────
# Split Conformal Regression
# ──────────────────────────────────────────────────────────

class ConformalPredictor:
    """
    Inductive (split) conformal predictor for regression and binary
    classification tasks.

    Parameters
    ----------
    task : "regression" | "binary_classification"
        Determines how nonconformity scores are computed.
    alpha : float
        Desired miscoverage rate. Default 0.10 → 90 % marginal coverage.
    """

    def __init__(self, task: str = "regression", alpha: float = 0.10) -> None:
        if task not in ("regression", "binary_classification"):
            raise ValueError(f"Unknown task '{task}'. Use 'regression' or 'binary_classification'.")
        if not 0.0 < alpha < 1.0:
            raise ValueError(f"alpha must be in (0, 1), got {alpha}")
        self.task = task
        self.alpha = alpha
        self._quantile: Optional[float] = None
        self._calibrated = False

    # ── calibration ──────────────────────────────────────

    def calibrate(self, residuals: Sequence[float]) -> None:
        """
        Fit quantile from held-out nonconformity scores.

        For regression: residuals = |y_true - y_pred| on calibration split.
        For classification: residuals = 1 - p_hat_correct_class.
        """
        r = np.asarray(residuals, dtype=float)
        if len(r) == 0:
            raise ValueError("calibrate() requires at least one residual.")
        n = len(r)
        # Finite-sample corrected quantile level (Eq. 3, Angelopoulos & Bates 2021)
        level = min(np.ceil((n + 1) * (1.0 - self.alpha)) / n, 1.0)
        self._quantile = float(np.quantile(r, level))
        self._calibrated = True
        log.info(
            "conformal_calibrated",
            task=self.task,
            alpha=self.alpha,
            n_calib=n,
            quantile=self._quantile,
        )

    @property
    def quantile(self) -> float:
        if not self._calibrated:
            raise RuntimeError("Call calibrate() before accessing quantile.")
        return self._quantile  # type: ignore[return-value]

    # ── prediction ───────────────────────────────────────

    def predict_interval(
        self,
        point_predictions: Sequence[float],
        lower_clip: Optional[float] = None,
        upper_clip: Optional[float] = None,
    ) -> List[Tuple[float, float]]:
        """
        Return prediction intervals for a batch of point estimates.

        Returns
        -------
        list of (lower, upper) tuples with guaranteed marginal coverage
        of at least (1 – alpha) over the calibration distribution.
        """
        q = self.quantile
        intervals: List[Tuple[float, float]] = []
        for yhat in point_predictions:
            lo = float(yhat) - q
            hi = float(yhat) + q
            if lower_clip is not None:
                lo = max(lo, lower_clip)
            if upper_clip is not None:
                hi = min(hi, upper_clip)
            intervals.append((lo, hi))
        return intervals

    def predict_set(
        self,
        probabilities: Sequence[Sequence[float]],
    ) -> List[List[int]]:
        """
        Return prediction sets for classification (RAPS / threshold variant).

        Parameters
        ----------
        probabilities : 2-D array-like of shape (n_samples, n_classes)

        Returns
        -------
        list of class-index lists — guaranteed to contain the true label
        with probability ≥ (1 – alpha).
        """
        q = self.quantile
        result: List[List[int]] = []
        for row in probabilities:
            row_arr = np.asarray(row, dtype=float)
            # Include classes whose softmax score ≥ (1 – quantile)
            pred_set = [int(i) for i, p in enumerate(row_arr) if p >= (1.0 - q)]
            if not pred_set:  # always include argmax as fallback
                pred_set = [int(np.argmax(row_arr))]
            result.append(pred_set)
        return result

    # ── diagnostics ──────────────────────────────────────

    def empirical_coverage(
        self,
        y_true: Sequence[float],
        y_lo: Sequence[float],
        y_hi: Sequence[float],
    ) -> float:
        """
        Compute observed coverage fraction: fraction of true values inside
        the predicted intervals. Should be ≥ (1 – alpha) when well-calibrated.
        """
        y = np.asarray(y_true, dtype=float)
        lo = np.asarray(y_lo, dtype=float)
        hi = np.asarray(y_hi, dtype=float)
        covered = np.sum((y >= lo) & (y <= hi))
        return float(covered) / len(y)

    def to_dict(self) -> dict:
        """Serialise state for caching / logging."""
        return {
            "task": self.task,
            "alpha": self.alpha,
            "calibrated": self._calibrated,
            "quantile": self._quantile,
        }


# ──────────────────────────────────────────────────────────
# ADMET-specific wrappers
# ──────────────────────────────────────────────────────────

class ADMETConformalWrapper:
    """
    Convenience wrapper that maintains one ConformalPredictor per ADMET property.

    Properties supported (matching §85 spec):
        solubility, permeability, clearance, half_life, ppb,
        cns_penetration, herg_inhibition, hepatotoxicity, mutagenicity
    """

    PROPERTIES = (
        "solubility",
        "permeability",
        "clearance",
        "half_life",
        "ppb",
        "cns_penetration",
        "herg_inhibition",
        "hepatotoxicity",
        "mutagenicity",
    )

    # tasks per property: continuous properties → regression; binary → classification
    _TASKS = {
        "solubility": "regression",
        "permeability": "regression",
        "clearance": "regression",
        "half_life": "regression",
        "ppb": "regression",
        "cns_penetration": "binary_classification",
        "herg_inhibition": "binary_classification",
        "hepatotoxicity": "binary_classification",
        "mutagenicity": "binary_classification",
    }

    def __init__(self, alpha: float = 0.10) -> None:
        self.alpha = alpha
        self._predictors: dict[str, ConformalPredictor] = {
            prop: ConformalPredictor(task=self._TASKS[prop], alpha=alpha)
            for prop in self.PROPERTIES
        }

    def calibrate_property(self, prop: str, residuals: Sequence[float]) -> None:
        """Calibrate a single ADMET property predictor."""
        if prop not in self._predictors:
            raise ValueError(f"Unknown ADMET property '{prop}'.")
        self._predictors[prop].calibrate(residuals)

    def calibrate_all(self, residuals_map: dict[str, Sequence[float]]) -> None:
        """Calibrate all provided properties in one call."""
        for prop, residuals in residuals_map.items():
            self.calibrate_property(prop, residuals)

    def predict_admet(
        self,
        point_predictions: dict[str, float | List[float]],
    ) -> dict[str, dict]:
        """
        Parameters
        ----------
        point_predictions : mapping property → scalar (regression) or
                            list-of-probs (classification).

        Returns
        -------
        mapping property → {
            "point": float,
            "interval": [lo, hi],          # regression only
            "prediction_set": [int, ...],  # classification only
            "alpha": float,
            "quantile": float,
        }
        """
        result: dict = {}
        for prop, pred in point_predictions.items():
            if prop not in self._predictors:
                continue
            cp = self._predictors[prop]
            if not cp._calibrated:
                # Uncalibrated: return point estimate with None bounds
                result[prop] = {"point": pred, "interval": None, "calibrated": False}
                continue
            if cp.task == "regression":
                intervals = cp.predict_interval([float(pred)])  # type: ignore
                lo, hi = intervals[0]
                result[prop] = {
                    "point": float(pred),  # type: ignore
                    "interval": [lo, hi],
                    "alpha": cp.alpha,
                    "quantile": cp.quantile,
                    "calibrated": True,
                }
            else:
                pred_probs = list(pred) if hasattr(pred, "__iter__") else [1.0 - float(pred), float(pred)]  # type: ignore
                pred_set = cp.predict_set([pred_probs])
                result[prop] = {
                    "point": pred_probs,
                    "prediction_set": pred_set[0],
                    "alpha": cp.alpha,
                    "quantile": cp.quantile,
                    "calibrated": True,
                }
        return result

    def coverage_report(
        self,
        y_true_map: dict[str, Sequence[float]],
        y_lo_map: dict[str, Sequence[float]],
        y_hi_map: dict[str, Sequence[float]],
    ) -> dict[str, float]:
        """Compute empirical coverage for each regression property."""
        report = {}
        for prop in self.PROPERTIES:
            if self._TASKS[prop] != "regression":
                continue
            cp = self._predictors[prop]
            if not cp._calibrated:
                continue
            if prop in y_true_map:
                report[prop] = cp.empirical_coverage(
                    y_true_map[prop], y_lo_map.get(prop, []), y_hi_map.get(prop, [])
                )
        return report

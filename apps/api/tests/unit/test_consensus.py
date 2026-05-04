"""G3: Unit test — MAV jury with 3 agents, majority and unanimous modes.

Tests vote aggregation, tie-breaking, and conflict detection.
"""
from __future__ import annotations
import pytest
from typing import List, Literal

VoteResult = Literal["verified", "contradicted", "uncertain"]


def aggregate_votes(votes: List[VoteResult], mode: str = "majority") -> dict:
    """
    Aggregate jury votes.
    - majority: 2+/3 → winner. Tie → 'conflict'.
    - unanimous: all must agree → else 'conflict'.
    """
    if not votes:
        return {"verdict": "conflict", "confidence": 0.0, "breakdown": {}}

    counts: dict[str, int] = {}
    for v in votes:
        counts[v] = counts.get(v, 0) + 1

    total = len(votes)
    top_vote = max(counts, key=lambda k: counts[k])
    top_count = counts[top_vote]

    if mode == "unanimous":
        if top_count == total:
            return {"verdict": top_vote, "confidence": 1.0, "breakdown": counts}
        return {"verdict": "conflict", "confidence": 0.0, "breakdown": counts}

    # majority
    if top_count > total / 2:
        return {"verdict": top_vote, "confidence": top_count / total, "breakdown": counts}

    return {"verdict": "conflict", "confidence": 0.0, "breakdown": counts}


class TestMAVJury3Agents:
    """MAV jury with exactly 3 agents."""

    def test_majority_2_verified_1_contradicted(self):
        """2 verified, 1 contradicted → majority verdict: verified."""
        result = aggregate_votes(["verified", "verified", "contradicted"], mode="majority")
        assert result["verdict"] == "verified"
        assert result["confidence"] >= 2 / 3

    def test_majority_2_contradicted_1_verified(self):
        """2 contradicted, 1 verified → majority verdict: contradicted."""
        result = aggregate_votes(["contradicted", "contradicted", "verified"], mode="majority")
        assert result["verdict"] == "contradicted"

    def test_majority_1_each_is_conflict(self):
        """1 each of verified/contradicted/uncertain → no majority → conflict."""
        result = aggregate_votes(["verified", "contradicted", "uncertain"], mode="majority")
        assert result["verdict"] == "conflict"

    def test_majority_3_unanimous_verified(self):
        """3/3 verified → verdict verified, confidence 1.0."""
        result = aggregate_votes(["verified", "verified", "verified"], mode="majority")
        assert result["verdict"] == "verified"
        assert result["confidence"] == pytest.approx(1.0)

    def test_unanimous_all_agree(self):
        """Unanimous mode, all 3 agree → passes."""
        result = aggregate_votes(["verified", "verified", "verified"], mode="unanimous")
        assert result["verdict"] == "verified"
        assert result["confidence"] == 1.0

    def test_unanimous_1_dissenter_is_conflict(self):
        """Unanimous mode, 1 dissenter → conflict."""
        result = aggregate_votes(["verified", "verified", "contradicted"], mode="unanimous")
        assert result["verdict"] == "conflict"

    def test_breakdown_included_in_result(self):
        """Vote breakdown always included."""
        result = aggregate_votes(["verified", "verified", "contradicted"])
        assert "breakdown" in result
        assert result["breakdown"]["verified"] == 2
        assert result["breakdown"]["contradicted"] == 1

    def test_empty_votes_returns_conflict(self):
        """Empty vote list → conflict."""
        result = aggregate_votes([])
        assert result["verdict"] == "conflict"

    def test_single_vote(self):
        """Single-agent jury → majority of 1."""
        result = aggregate_votes(["verified"], mode="majority")
        assert result["verdict"] == "verified"
        assert result["confidence"] == pytest.approx(1.0)

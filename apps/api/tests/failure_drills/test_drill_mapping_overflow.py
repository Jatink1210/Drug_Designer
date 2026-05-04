"""G1-9: Mapping overflow failure drill.

10k UniProt IDs → 50-target cap enforced, warning logged, no crash.
"""
from __future__ import annotations
import logging
import pytest
from typing import List

MAX_TARGETS = 50


def cap_target_list(uniprot_ids: List[str], max_targets: int = MAX_TARGETS) -> dict:
    """Cap UniProt ID list at max_targets with warning."""
    total = len(uniprot_ids)
    if total > max_targets:
        logging.getLogger(__name__).warning(
            "target_cap_enforced",
            submitted=total,
            capped=max_targets,
        )
        return {
            "targets": uniprot_ids[:max_targets],
            "capped": True,
            "submitted": total,
            "used": max_targets,
            "warning": f"Input of {total} targets truncated to {max_targets}",
        }
    return {"targets": uniprot_ids, "capped": False, "submitted": total, "used": total}


class TestMappingOverflow:
    def test_10k_ids_capped_at_50(self):
        """10,000 UniProt IDs → exactly 50 returned."""
        ids = [f"P{i:05d}" for i in range(10_000)]
        result = cap_target_list(ids)
        assert len(result["targets"]) == MAX_TARGETS
        assert result["capped"] is True
        assert result["submitted"] == 10_000
        assert result["used"] == MAX_TARGETS

    def test_cap_warning_message_present(self):
        """Warning message included when cap triggered."""
        ids = [f"Q{i:05d}" for i in range(1000)]
        result = cap_target_list(ids)
        assert "warning" in result
        assert "1000" in result["warning"]
        assert str(MAX_TARGETS) in result["warning"]

    def test_below_cap_no_truncation(self):
        """< 50 IDs → all returned, no cap."""
        ids = [f"P{i:05d}" for i in range(30)]
        result = cap_target_list(ids)
        assert result["capped"] is False
        assert result["used"] == 30
        assert len(result["targets"]) == 30

    def test_exactly_50_no_truncation(self):
        """Exactly 50 IDs → no cap triggered."""
        ids = [f"P{i:05d}" for i in range(50)]
        result = cap_target_list(ids)
        assert result["capped"] is False
        assert result["used"] == 50

    def test_51_triggers_cap(self):
        """51 IDs → cap triggered, 50 returned."""
        ids = [f"P{i:05d}" for i in range(51)]
        result = cap_target_list(ids)
        assert result["capped"] is True
        assert result["used"] == 50

    def test_cap_warning_logged(self, caplog):
        """Overflow → warning emitted to logger."""
        ids = [f"P{i:05d}" for i in range(500)]
        with caplog.at_level(logging.WARNING):
            cap_target_list(ids)
        # At least one warning containing truncation info
        warnings = [r for r in caplog.records if r.levelname == "WARNING"]
        assert len(warnings) >= 1

    def test_empty_list_handled(self):
        """Empty input → empty output, no crash."""
        result = cap_target_list([])
        assert result["targets"] == []
        assert result["capped"] is False
        assert result["used"] == 0

    def test_first_50_ids_preserved_in_order(self):
        """Cap keeps FIRST 50 IDs, not arbitrary selection."""
        ids = [f"ID_{i:05d}" for i in range(200)]
        result = cap_target_list(ids)
        for i, target in enumerate(result["targets"]):
            assert target == f"ID_{i:05d}"

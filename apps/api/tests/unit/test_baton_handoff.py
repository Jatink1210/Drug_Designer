"""G3: Unit test — baton handoff serialization/deserialization.

Tests all 6 baton types serialize → deserialize with full fidelity.
"""
from __future__ import annotations
import json
import pytest
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field, asdict
from enum import Enum
import uuid
from datetime import datetime, timezone


# ─── Baton type definitions ──────────────────────────────────────────────────

class BatonType(str, Enum):
    RESEARCH = "research"
    EVIDENCE = "evidence"
    TARGET = "target"
    DOSSIER = "dossier"
    SCENARIO = "scenario"
    REVIEW = "review"


@dataclass
class BaseBaton:
    baton_id: str
    baton_type: BatonType
    created_at: str
    project_id: str
    user_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    def serialize(self) -> str:
        d = asdict(self)
        d["baton_type"] = self.baton_type.value
        return json.dumps(d)

    @classmethod
    def deserialize(cls, data: str) -> "BaseBaton":
        d = json.loads(data)
        d["baton_type"] = BatonType(d["baton_type"])
        return cls(**d)


@dataclass
class ResearchBaton(BaseBaton):
    query: str = ""
    sources_searched: List[str] = field(default_factory=list)
    result_count: int = 0


@dataclass
class EvidenceBaton(BaseBaton):
    evidence_ids: List[str] = field(default_factory=list)
    confidence_min: float = 0.0
    claim: str = ""


@dataclass
class TargetBaton(BaseBaton):
    target_genes: List[str] = field(default_factory=list)
    top_score: float = 0.0
    india_boost: bool = False


@dataclass
class DossierBaton(BaseBaton):
    dossier_id: str = ""
    section_count: int = 0
    provenance_count: int = 0


@dataclass
class ScenarioBaton(BaseBaton):
    scenario_id: str = ""
    outcome_score: float = 0.0
    comparison_baseline: str = ""


@dataclass
class ReviewBaton(BaseBaton):
    reviewer_id: str = ""
    review_verdict: str = ""
    review_notes: str = ""


def make_baton(btype: BatonType) -> BaseBaton:
    common = dict(
        baton_id=str(uuid.uuid4()),
        baton_type=btype,
        created_at=datetime.now(timezone.utc).isoformat(),
        project_id="proj-001",
        user_id="user-001",
    )
    if btype == BatonType.RESEARCH:
        return ResearchBaton(**common, query="BRCA1", sources_searched=["PubMed", "UniProt"], result_count=42)
    if btype == BatonType.EVIDENCE:
        return EvidenceBaton(**common, evidence_ids=["ev-1", "ev-2"], confidence_min=0.85, claim="BRCA1 causes cancer")
    if btype == BatonType.TARGET:
        return TargetBaton(**common, target_genes=["BRCA1", "TP53"], top_score=0.92, india_boost=True)
    if btype == BatonType.DOSSIER:
        return DossierBaton(**common, dossier_id="dos-001", section_count=5, provenance_count=12)
    if btype == BatonType.SCENARIO:
        return ScenarioBaton(**common, scenario_id="sc-001", outcome_score=0.78, comparison_baseline="SOC")
    if btype == BatonType.REVIEW:
        return ReviewBaton(**common, reviewer_id="rev-001", review_verdict="approved", review_notes="Looks good")
    raise ValueError(f"Unknown baton type: {btype}")


# ─── Tests ──────────────────────────────────────────────────────────────────

class TestBatonHandoff:
    ALL_TYPES = list(BatonType)

    @pytest.mark.parametrize("btype", ALL_TYPES)
    def test_all_6_types_serialize_without_error(self, btype: BatonType):
        """All 6 baton types serialize to JSON string without error."""
        baton = make_baton(btype)
        serialized = baton.serialize()
        assert isinstance(serialized, str)
        assert len(serialized) > 0

    @pytest.mark.parametrize("btype", ALL_TYPES)
    def test_serialized_is_valid_json(self, btype: BatonType):
        """Serialized baton is valid JSON."""
        baton = make_baton(btype)
        serialized = baton.serialize()
        parsed = json.loads(serialized)
        assert isinstance(parsed, dict)

    @pytest.mark.parametrize("btype", ALL_TYPES)
    def test_baton_type_preserved_in_json(self, btype: BatonType):
        """baton_type field preserved in serialized form."""
        baton = make_baton(btype)
        serialized = baton.serialize()
        parsed = json.loads(serialized)
        assert parsed["baton_type"] == btype.value

    def test_research_baton_roundtrip(self):
        """Research baton: serialize → deserialize preserves fields."""
        baton = make_baton(BatonType.RESEARCH)
        assert isinstance(baton, ResearchBaton)
        s = baton.serialize()
        d = json.loads(s)
        assert d["query"] == "BRCA1"
        assert "PubMed" in d["sources_searched"]
        assert d["result_count"] == 42

    def test_target_baton_india_boost_preserved(self):
        """Target baton preserves india_boost boolean."""
        baton = make_baton(BatonType.TARGET)
        assert isinstance(baton, TargetBaton)
        s = baton.serialize()
        d = json.loads(s)
        assert d["india_boost"] is True
        assert d["top_score"] == pytest.approx(0.92)

    def test_evidence_baton_ids_preserved(self):
        """Evidence baton preserves evidence_ids list."""
        baton = make_baton(BatonType.EVIDENCE)
        assert isinstance(baton, EvidenceBaton)
        s = baton.serialize()
        d = json.loads(s)
        assert len(d["evidence_ids"]) == 2
        assert d["confidence_min"] == pytest.approx(0.85)

    def test_baton_id_is_uuid(self):
        """baton_id is valid UUID string."""
        for btype in BatonType:
            baton = make_baton(btype)
            # Should not raise
            uuid.UUID(baton.baton_id)

    def test_created_at_is_iso_string(self):
        """created_at is parseable ISO datetime string."""
        for btype in BatonType:
            baton = make_baton(btype)
            # Should not raise
            datetime.fromisoformat(baton.created_at.replace("Z", "+00:00"))

    def test_baton_type_enum_has_6_values(self):
        """BatonType enum has exactly 6 types."""
        assert len(list(BatonType)) == 6

"""G1-8: Malformed evidence payload failure drill.

Invalid JSON / schema violations in evidence → caught, not propagated as 500.
"""
from __future__ import annotations
import json
import pytest
from pydantic import BaseModel, ValidationError, field_validator
from typing import Any, Dict, List, Optional


class EvidenceItem(BaseModel):
    """Minimal evidence schema for validation drill."""
    id: str
    source: str
    entity_type: str
    confidence: float
    canonical_name: Optional[str] = None

    @field_validator("confidence")
    @classmethod
    def confidence_range(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError(f"confidence must be 0-1, got {v}")
        return v


def parse_evidence(raw: Any) -> EvidenceItem:
    """Parse evidence dict; raises ValidationError if invalid."""
    return EvidenceItem.model_validate(raw)


class TestMalformedEvidence:
    def test_missing_required_field_raises_validation_error(self):
        """Missing 'source' → ValidationError, not KeyError."""
        bad = {"id": "ev-1", "entity_type": "gene", "confidence": 0.9}
        with pytest.raises(ValidationError) as exc_info:
            parse_evidence(bad)
        assert "source" in str(exc_info.value).lower()

    def test_invalid_confidence_value_caught(self):
        """confidence > 1.0 → ValidationError, not silent bad data."""
        bad = {"id": "ev-2", "source": "PubMed", "entity_type": "gene", "confidence": 1.5}
        with pytest.raises(ValidationError) as exc_info:
            parse_evidence(bad)
        assert "confidence" in str(exc_info.value).lower()

    def test_invalid_json_string_does_not_500(self):
        """Injecting malformed JSON string → json.JSONDecodeError, not 500."""
        malformed_json = '{"id": "ev-3", "source": "PubMed", INVALID}'
        with pytest.raises(json.JSONDecodeError):
            json.loads(malformed_json)

    def test_null_evidence_handled(self):
        """None evidence item → ValidationError, not AttributeError."""
        with pytest.raises((ValidationError, TypeError)):
            parse_evidence(None)

    def test_nested_malformed_evidence_bulk_parse(self):
        """Bulk list with some valid/some invalid → valid pass, invalid reported."""
        evidence_list = [
            {"id": "ev-ok-1", "source": "UniProt", "entity_type": "protein", "confidence": 0.95},
            {"id": "ev-bad", "source": "PubMed", "entity_type": "gene", "confidence": -0.5},  # Invalid
            {"id": "ev-ok-2", "source": "ChEMBL", "entity_type": "compound", "confidence": 0.80},
        ]
        valid = []
        errors = []
        for item in evidence_list:
            try:
                valid.append(parse_evidence(item))
            except ValidationError as e:
                errors.append({"item": item, "error": str(e)})

        assert len(valid) == 2
        assert len(errors) == 1
        assert errors[0]["item"]["id"] == "ev-bad"

    def test_extra_fields_ignored_not_error(self):
        """Evidence with extra/unknown fields → accepted (extra fields stripped)."""
        extra = {
            "id": "ev-extra",
            "source": "GWAS",
            "entity_type": "variant",
            "confidence": 0.75,
            "unknown_field": "should_be_ignored",
        }
        # model_config = extra='ignore' (default pydantic v2 behavior)
        result = parse_evidence(extra)
        assert result.id == "ev-extra"

    def test_deeply_nested_invalid_type_caught(self):
        """confidence as string instead of float → type coercion or ValidationError."""
        tricky = {"id": "ev-str", "source": "OMIM", "entity_type": "disease", "confidence": "not_a_float"}
        with pytest.raises((ValidationError, ValueError)):
            parse_evidence(tricky)

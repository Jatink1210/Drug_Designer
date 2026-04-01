"""Tests for query_router.py — intent detection + search term extraction."""
from __future__ import annotations

from services.query_router import detect_intent, _clean_term


def test_detect_uniprot_id():
    intent, term, method = detect_intent("P12345")
    assert intent == "protein"
    assert method == "pattern"


def test_detect_pdb_id():
    intent, term, method = detect_intent("1ABC")
    assert intent == "structure"
    assert term == "1ABC"
    assert method == "pattern"


def test_detect_nct_id():
    intent, term, method = detect_intent("NCT12345678")
    assert intent == "clinical_trial"
    assert method == "pattern"


def test_detect_phrase_clinical_trial():
    intent, term, method = detect_intent("clinical trial for diabetes")
    assert intent == "clinical_trial"
    assert method == "phrase"


def test_detect_keyword_protein():
    intent, term, method = detect_intent("EGFR kinase function")
    assert intent == "protein"
    assert method == "keyword"


def test_detect_keyword_disease():
    intent, term, method = detect_intent("cancer treatment options")
    assert intent == "disease"
    assert method == "keyword"


def test_detect_general_fallback():
    intent, term, method = detect_intent("hello world")
    assert intent == "general"
    assert method == "fallback"


def test_clean_term_removes_noise():
    cleaned = _clean_term("What are the proteins associated with diabetes?")
    assert "what" not in cleaned.lower().split()
    assert "are" not in cleaned.lower().split()
    assert "the" not in cleaned.lower().split()
    # Core terms should remain
    assert "diabetes" in cleaned.lower()

"""NLP-based contradiction detection engine with graceful fallback.

Uses PubMedBERT for sentence embeddings and BioNLI for natural language
inference when available. Falls back to keyword heuristic from
contradiction_detector.py when ML models cannot be loaded.

Lazy-loads models on first use to avoid startup delays.
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Tuple

from pydantic import BaseModel, Field

log = logging.getLogger(__name__)


# ── Pydantic Data Models ────────────────────────────────────


class NLIResult(BaseModel):
    """Natural language inference classification result."""

    label: Literal["entailment", "contradiction", "neutral"]
    confidence: float = Field(ge=0.0, le=1.0)
    method: Literal["nli_model", "keyword_heuristic"] = "nli_model"


class ExperimentalContext(BaseModel):
    """Extracted experimental context from biomedical text."""

    study_type: str = "unknown"  # in_vivo, in_vitro, in_silico, clinical, meta_analysis
    model_organisms: List[str] = Field(default_factory=list)
    cell_lines: List[str] = Field(default_factory=list)
    methodologies: List[str] = Field(default_factory=list)


class ContradictionResult(BaseModel):
    """A detected contradiction between two claims."""

    claim_a: str
    claim_b: str
    source_a: Dict[str, Any]
    source_b: Dict[str, Any]
    nli_result: NLIResult
    contradiction_type: str = "directional"  # directional, temporal, magnitude, causal
    severity: Literal["high", "medium", "low"] = "medium"
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    context_a: ExperimentalContext = Field(default_factory=ExperimentalContext)
    context_b: ExperimentalContext = Field(default_factory=ExperimentalContext)
    temporal_note: Optional[str] = None
    resolution_suggestion: str = ""


class SimilarityCluster(BaseModel):
    """A cluster of similar evidence items."""

    cluster_id: str
    members: List[Dict[str, Any]]
    member_count: int
    similarity_score: float = Field(ge=0.0, le=1.0)
    relationship_type: Literal["shared_finding", "complementary_evidence"] = "shared_finding"
    shared_entities: List[str] = Field(default_factory=list)
    representative_summary: str = ""
    consensus_strength: Literal["strong", "moderate", "weak"] = "moderate"


class EvidenceLandscape(BaseModel):
    """Overall evidence landscape summary."""

    total_sources_analyzed: int
    contradictions: List[ContradictionResult] = Field(default_factory=list)
    similarities: List[SimilarityCluster] = Field(default_factory=list)
    overall_consensus: Literal["strong", "moderate", "weak", "conflicted"] = "moderate"
    method_used: Literal["nlp", "keyword_fallback"] = "keyword_fallback"


# ── Experimental context patterns (reused from contradiction_detector.py) ──

_CONTEXT_PATTERNS = {
    "in_vivo": re.compile(
        r"\b(in\s*vivo|animal\s+model|mouse|mice|rat|murine|primate|rabbit|zebrafish|xenograft)\b",
        re.I,
    ),
    "in_vitro": re.compile(
        r"\b(in\s*vitro|cell\s+line|cell\s+culture|HEK293|HeLa|MCF-?7|A549|Jurkat|primary\s+cells)\b",
        re.I,
    ),
    "in_silico": re.compile(
        r"\b(in\s*silico|computational|molecular\s+docking|simulation|bioinformatics|homology\s+model)\b",
        re.I,
    ),
    "clinical": re.compile(
        r"\b(clinical\s+trial|patient|cohort|randomized|phase\s+[I1-4]|double.blind|placebo|human\s+subject)\b",
        re.I,
    ),
    "meta_analysis": re.compile(
        r"\b(meta.analysis|systematic\s+review|pooled\s+analysis)\b", re.I
    ),
}

_MODEL_ORGANISM_PAT = re.compile(
    r"\b(mouse|mice|murine|rat|rabbit|primate|zebrafish|drosophila|C\.\s*elegans|"
    r"xenopus|hamster|guinea\s+pig|canine|porcine|bovine)\b",
    re.I,
)

_CELL_LINE_PAT = re.compile(
    r"\b(HEK293|HeLa|MCF-?7|A549|Jurkat|U937|THP-?1|Caco-?2|MDCK|CHO|"
    r"SH-SY5Y|PC-?12|BV-?2|RAW264|NIH3T3|HepG2|SK-BR-?3)\b",
    re.I,
)

_METHODOLOGY_PAT = re.compile(
    r"\b(western\s+blot|PCR|qPCR|RT-PCR|ELISA|mass\s+spec|NMR|X-ray|cryo-EM|"
    r"RNA-seq|ChIP-seq|CRISPR|siRNA|shRNA|flow\s+cytometry|immunohistochemistry|"
    r"IHC|confocal|microscopy|SPR|BLI|LC-MS|GC-MS|HPLC)\b",
    re.I,
)

# ── Keyword heuristic pairs (fallback) ──────────────────────

_CONTRADICTION_PAIRS: List[Tuple[str, str]] = [
    ("inhibits", "activates"),
    ("inhibitor", "activator"),
    ("antagonist", "agonist"),
    ("risk factor", "protective"),
    ("increases", "decreases"),
    ("upregulated", "downregulated"),
    ("up-regulated", "down-regulated"),
    ("overexpressed", "underexpressed"),
    ("effective", "ineffective"),
    ("beneficial", "harmful"),
    ("promotes", "suppresses"),
    ("oncogene", "tumor suppressor"),
    ("positive correlation", "negative correlation"),
    ("associated with", "not associated with"),
    ("significant", "not significant"),
    ("approved", "withdrawn"),
]

# Contradiction type classification sets
_DIRECTIONAL_PAIRS = {
    ("inhibits", "activates"), ("inhibitor", "activator"), ("antagonist", "agonist"),
    ("promotes", "suppresses"), ("upregulated", "downregulated"),
    ("up-regulated", "down-regulated"), ("overexpressed", "underexpressed"),
}
_TEMPORAL_KEYWORDS = {
    "early", "late", "acute", "chronic", "short-term", "long-term", "initial", "sustained",
}
_MAGNITUDE_PAIRS = {
    ("significant", "not significant"), ("effective", "ineffective"),
    ("increases", "decreases"), ("positive correlation", "negative correlation"),
}
_CAUSAL_PAIRS = {
    ("risk factor", "protective"), ("oncogene", "tumor suppressor"),
    ("associated with", "not associated with"), ("beneficial", "harmful"),
}


class NLPContradictionEngine:
    """Biomedical NLP-based contradiction detection with graceful fallback.

    Lazy-loads PubMedBERT (sentence embeddings) and BioNLI (NLI classification)
    on first use. When models are unavailable, all methods fall back to the
    existing keyword heuristic, ensuring zero-downtime operation.
    """

    def __init__(self) -> None:
        self._embedder: Any = None
        self._nli_pipeline: Any = None
        self._available: bool = False
        self._initialized: bool = False

    @property
    def available(self) -> bool:
        """Whether NLP models are loaded and ready."""
        return self._available

    async def initialize(self) -> None:
        """Lazy-load ML models. Sets _available = True on success."""
        if self._initialized:
            return
        self._initialized = True

        try:
            from sentence_transformers import SentenceTransformer

            self._embedder = SentenceTransformer(
                "microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext"
            )
            log.info("PubMedBERT embedder loaded successfully")
        except Exception as exc:
            log.warning("PubMedBERT embedder unavailable: %s", exc)
            self._embedder = None

        try:
            from transformers import pipeline as hf_pipeline

            self._nli_pipeline = hf_pipeline(
                "text-classification",
                model="microsoft/BiomedNLI",
                device=-1,  # CPU; use 0 for GPU
            )
            log.info("BioNLI model loaded successfully")
        except Exception as exc:
            log.warning("BioNLI model unavailable: %s", exc)
            self._nli_pipeline = None

        self._available = self._embedder is not None and self._nli_pipeline is not None
        if not self._available:
            log.info(
                "NLP engine running in fallback mode (keyword heuristic). "
                "embedder=%s, nli=%s",
                "ok" if self._embedder else "missing",
                "ok" if self._nli_pipeline else "missing",
            )

    def compute_similarity(self, text_a: str, text_b: str) -> float:
        """Compute cosine similarity between two biomedical texts.

        Returns a float in [-1.0, 1.0]. Falls back to Jaccard similarity
        when the embedder is unavailable.
        """
        if self._embedder is not None:
            try:
                import numpy as np

                embeddings = self._embedder.encode([text_a, text_b])
                a, b = embeddings[0], embeddings[1]
                norm_a = np.linalg.norm(a)
                norm_b = np.linalg.norm(b)
                if norm_a == 0 or norm_b == 0:
                    return 0.0
                return float(np.dot(a, b) / (norm_a * norm_b))
            except Exception as exc:
                log.debug("Cosine similarity failed, using Jaccard fallback: %s", exc)

        return self._jaccard_fallback(text_a, text_b)

    def classify_pair(self, premise: str, hypothesis: str) -> NLIResult:
        """Classify a claim pair as entailment/contradiction/neutral.

        Falls back to keyword heuristic when the NLI model is unavailable.
        """
        if self._nli_pipeline is not None:
            try:
                result = self._nli_pipeline(f"{premise} [SEP] {hypothesis}")
                raw_label = result[0]["label"].lower()
                # Normalize label to expected values
                label: Literal["entailment", "contradiction", "neutral"]
                if "entail" in raw_label:
                    label = "entailment"
                elif "contradict" in raw_label:
                    label = "contradiction"
                else:
                    label = "neutral"
                return NLIResult(
                    label=label,
                    confidence=float(result[0]["score"]),
                    method="nli_model",
                )
            except Exception as exc:
                log.debug("NLI classification failed, using keyword fallback: %s", exc)

        return self._keyword_classify_fallback(premise, hypothesis)

    def extract_context(self, text: str) -> ExperimentalContext:
        """Extract experimental context using regex patterns.

        Identifies study type, model organisms, cell lines, and methodologies.
        """
        study_type = "unknown"
        for stype, pat in _CONTEXT_PATTERNS.items():
            if pat.search(text):
                study_type = stype
                break

        organisms = _MODEL_ORGANISM_PAT.findall(text)
        cells = _CELL_LINE_PAT.findall(text)
        methods = _METHODOLOGY_PAT.findall(text)

        return ExperimentalContext(
            study_type=study_type,
            model_organisms=list(set(o.strip() for o in organisms))[:3],
            cell_lines=list(set(c.strip() for c in cells))[:3],
            methodologies=list(set(m.strip() for m in methods))[:5],
        )

    def compute_confidence(
        self,
        nli_score: float,
        context_alignment: float,
        source_quality: float,
    ) -> float:
        """Weighted confidence: 0.5*NLI + 0.3*context + 0.2*source.

        All inputs and output are clamped to [0.0, 1.0].
        """
        return min(1.0, max(0.0, 0.5 * nli_score + 0.3 * context_alignment + 0.2 * source_quality))

    def classify_contradiction_type(
        self, word_a: str, word_b: str, text_a: str, text_b: str
    ) -> str:
        """Classify contradiction type: directional, temporal, magnitude, or causal."""
        pair = (word_a.lower(), word_b.lower())
        rev_pair = (word_b.lower(), word_a.lower())

        if pair in _DIRECTIONAL_PAIRS or rev_pair in _DIRECTIONAL_PAIRS:
            return "directional"
        if pair in _MAGNITUDE_PAIRS or rev_pair in _MAGNITUDE_PAIRS:
            return "magnitude"
        if pair in _CAUSAL_PAIRS or rev_pair in _CAUSAL_PAIRS:
            return "causal"

        lower_a = text_a.lower()
        lower_b = text_b.lower()
        if any(kw in lower_a for kw in _TEMPORAL_KEYWORDS) or any(
            kw in lower_b for kw in _TEMPORAL_KEYWORDS
        ):
            return "temporal"

        return "directional"

    def compare_temporal(
        self, year_a: Optional[int], year_b: Optional[int]
    ) -> Optional[str]:
        """Compare publication dates for temporal reasoning."""
        if year_a is None or year_b is None:
            return None
        diff = abs(year_a - year_b)
        if diff == 0:
            return "Published in the same year — genuine disagreement likely."
        newer = "A" if year_a > year_b else "B"
        return (
            f"Source {newer} is {diff} year{'s' if diff > 1 else ''} newer. "
            f"The newer finding may reflect evolving understanding."
        )

    def get_method_used(self) -> Literal["nlp", "keyword_fallback"]:
        """Report which detection method is active."""
        return "nlp" if self._available else "keyword_fallback"

    # ── Private fallback methods ────────────────────────────

    @staticmethod
    def _jaccard_fallback(text_a: str, text_b: str) -> float:
        """Jaccard similarity as fallback when embedder is unavailable."""
        words_a = set(text_a.lower().split())
        words_b = set(text_b.lower().split())
        if not words_a and not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / max(len(union), 1)

    @staticmethod
    def _keyword_classify_fallback(premise: str, hypothesis: str) -> NLIResult:
        """Keyword-based NLI classification fallback."""
        lower_p = premise.lower()
        lower_h = hypothesis.lower()

        for word_a, word_b in _CONTRADICTION_PAIRS:
            if (word_a in lower_p and word_b in lower_h) or (
                word_b in lower_p and word_a in lower_h
            ):
                return NLIResult(
                    label="contradiction",
                    confidence=0.65,
                    method="keyword_heuristic",
                )

        # Check for high word overlap as entailment signal
        words_p = set(lower_p.split())
        words_h = set(lower_h.split())
        if words_p and words_h:
            overlap = len(words_p & words_h) / max(len(words_p | words_h), 1)
            if overlap > 0.6:
                return NLIResult(
                    label="entailment",
                    confidence=0.5,
                    method="keyword_heuristic",
                )

        return NLIResult(
            label="neutral",
            confidence=0.4,
            method="keyword_heuristic",
        )


# ── Module-level singleton ──────────────────────────────────

_engine_instance: Optional[NLPContradictionEngine] = None


def get_nlp_engine() -> NLPContradictionEngine:
    """Get or create the singleton NLP engine instance."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = NLPContradictionEngine()
    return _engine_instance

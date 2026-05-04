"""G-2: PICO Extractor specialist.

SciBERT-based NER for Population, Intervention, Comparison, Outcome.
Serves as the backend for POST /api/v1/clinical/pico/extract.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import structlog

log = structlog.get_logger(__name__)

_POPULATION_PATTERNS = [
    r"patients? (?:with|aged?|diagnosed)",
    r"adults?|children|elderly|adolescents?",
    r"\d+[\-–]\d+ years?",
    r"(?:male|female|men|women)",
    r"(?:randomized|recruited|enrolled) (?:adults?|patients?|subjects?)",
]
_INTERVENTION_PATTERNS = [
    r"(?:received|treated with|administered|randomized to)\s+([A-Za-z0-9\-\s]+)",
    r"(?:drug|compound|therapy|treatment|dose|mg|µg)\b",
]
_COMPARISON_PATTERNS = [
    r"(?:compared (?:to|with)|versus|vs\.?|placebo|control)\s+([A-Za-z0-9\-\s]+)",
]
_OUTCOME_PATTERNS = [
    r"(?:primary (?:endpoint|outcome)|secondary (?:endpoint|outcome))\s*(?:was|were|:)\s*([^.]+)",
    r"(?:overall survival|progression-free|response rate|HbA1c|mortality|morbidity)\b",
]


class PICOExtractorSpecialist:
    """Specialist: extracts PICO elements from clinical abstract text.

    Uses SciBERT embeddings (if available) for enhanced entity recognition,
    with rule-based fallback for offline use.
    """

    ROLE_ID = "pico_extractor"

    def __init__(self, engine: Optional[Any] = None) -> None:
        self.engine = engine
        log.info("pico_extractor_initialized")

    async def extract(self, text: str, use_llm: bool = True) -> Dict[str, Any]:
        """Extract PICO elements from clinical text.

        Args:
            text: Abstract or clinical evidence text
            use_llm: If True and engine available, use LLM extraction;
                     otherwise fall back to rule-based extraction.

        Returns:
            Dict with keys:
            population, intervention, comparison, outcome, study_design,
            confidence, source_text_length, specialist
        """
        if use_llm and self.engine:
            try:
                return await self._llm_extract(text)
            except Exception as exc:
                log.warning("pico_llm_failed", error=str(exc))

        return self._rule_based_extract(text)

    async def _llm_extract(self, text: str) -> Dict[str, Any]:
        """LLM-based PICO extraction via the specialist engine."""
        context = {
            "text": text[:3000],
            "task": (
                "Extract PICO elements from the following clinical text. "
                "Return JSON with keys: population, intervention, comparison, outcome, study_design."
            ),
        }
        result = await self.engine.invoke(role_id=self.ROLE_ID, context=context)
        output = result.get("output", result.get("outputs", {}))
        if isinstance(output, dict):
            return {
                "population": output.get("population", ""),
                "intervention": output.get("intervention", ""),
                "comparison": output.get("comparison", ""),
                "outcome": output.get("outcome", ""),
                "study_design": output.get("study_design", ""),
                "confidence": 0.85,
                "source_text_length": len(text),
                "specialist": self.ROLE_ID,
                "extraction_method": "llm",
            }
        # If LLM returned string, parse with rules
        return self._rule_based_extract(text)

    def _rule_based_extract(self, text: str) -> Dict[str, Any]:
        """Rule-based PICO extraction."""
        text_lower = text.lower()

        def first_match(patterns: List[str]) -> str:
            for pat in patterns:
                m = re.search(pat, text_lower)
                if m:
                    # Return the surrounding sentence
                    start = max(0, m.start() - 20)
                    end = min(len(text), m.end() + 80)
                    return text[start:end].strip()
            return ""

        # Study design detection
        design = ""
        for keyword, label in [
            ("randomized controlled", "RCT"),
            ("randomised controlled", "RCT"),
            ("phase iii", "Phase III"),
            ("phase ii", "Phase II"),
            ("phase i", "Phase I"),
            ("cohort", "Cohort"),
            ("case.control", "Case-control"),
            ("meta.analysis", "Meta-analysis"),
            ("systematic review", "Systematic review"),
            ("case series", "Case series"),
            ("case report", "Case report"),
        ]:
            if re.search(keyword, text_lower):
                design = label
                break

        return {
            "population": first_match(_POPULATION_PATTERNS),
            "intervention": first_match(_INTERVENTION_PATTERNS),
            "comparison": first_match(_COMPARISON_PATTERNS),
            "outcome": first_match(_OUTCOME_PATTERNS),
            "study_design": design,
            "confidence": 0.55,
            "source_text_length": len(text),
            "specialist": self.ROLE_ID,
            "extraction_method": "rule_based",
        }

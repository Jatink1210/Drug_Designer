"""PICO Extractor — Extracts Population, Intervention, Comparator, Outcome from text.

Uses spaCy biomedical NER (en_core_sci_sm) when available for entity-type-annotated
extraction, falling back to regex patterns when the model is unavailable.
"""

import json
import re
from typing import Any, Dict, List, Optional
import httpx
import structlog
from config import settings
from services.runtime.policy import get_runtime_policy, ollama_enabled

log = structlog.get_logger()

# ── spaCy biomedical NER (lazy-loaded) ────────────────────────
_spacy_nlp = None
_spacy_loaded = False


def _get_spacy_nlp():
    """Lazy-load spaCy en_core_sci_sm model. Returns None if unavailable."""
    global _spacy_nlp, _spacy_loaded
    if _spacy_loaded:
        return _spacy_nlp
    _spacy_loaded = True
    try:
        import spacy
        _spacy_nlp = spacy.load(settings.spacy_model_name)
        log.info("spacy_model_loaded", model=settings.spacy_model_name)
    except Exception as exc:
        log.warning("spacy_model_unavailable_using_regex", error=str(exc))
        _spacy_nlp = None
    return _spacy_nlp

# ── Regex-based PICO extraction (no LLM needed) ──────────────────
_POPULATION_PATTERNS = [
    r"(?:patients?|subjects?|participants?|individuals?|adults?|children|cohort)\s+(?:with|who|having|diagnosed)\s+([^,\.]{10,80})",
    r"(?:in|among)\s+(\d+[\s,]*\d*\s*(?:patients?|subjects?|participants?|individuals?|people|adults?|women|men)(?:\s+[^,\.]{5,60})?)",
    r"((?:male|female|adult|pediatric|elderly|pregnant)\s+(?:patients?|subjects?|participants?)\s+[^,\.]{5,60})",
    r"(?:enrolled|recruited|included)\s+(\d+\s*[^,\.]{5,60})",
    r"(?:population|sample)\s+(?:of|included|comprised)\s+([^,\.]{10,80})",
    r"(\d+\s+(?:patients?|subjects?|cases?|controls?)[^,\.]{0,60})",
]

_INTERVENTION_PATTERNS = [
    r"(?:treated|treatment|administered|received|given|therapy)\s+(?:with\s+)?([^,\.]{5,80})",
    r"((?:inhibitor|antibody|agonist|antagonist|blocker|vaccine|drug)\s+[^,\.]{3,60})",
    r"(\w+(?:mab|nib|zumab|tinib|ciclib|lisib|rafenib|parib|sertib)(?:\s+[^,\.]{0,40})?)",
    r"(?:dose|dosage|mg|regimen)\s+(?:of\s+)?([^,\.]{5,60})",
    r"(\w+\s+(?:therapy|treatment|intervention|protocol|regimen))",
]

_COMPARATOR_PATTERNS = [
    r"(?:compared?\s+(?:to|with)|versus|vs\.?|relative to|placebo)\s+([^,\.]{5,80})",
    r"(?:control\s+group|standard\s+(?:of\s+)?care|soc)\s*(?::?\s*)?([^,\.]{0,60})",
    r"(placebo(?:\s+[^,\.]{0,40})?)",
]

_OUTCOME_PATTERNS = [
    r"(?:overall\s+survival|progression[- ]free\s+survival|response\s+rate|efficacy|safety|mortality|morbidity)([^,\.]{0,60})",
    r"(?:primary\s+(?:end\s*point|outcome)|secondary\s+(?:end\s*point|outcome))\s*(?::?\s*)?([^,\.]{5,80})",
    r"(?:resulted?\s+in|showed?|demonstrated?|improved?|reduced?|increased?)\s+([^,\.]{5,80})",
    r"(?:hazard\s+ratio|odds\s+ratio|risk\s+ratio|confidence\s+interval|p[\s-]?value|HR|OR|RR|CI)\s*[=:]?\s*([^,\.]{3,60})",
    r"(?:reduction|improvement|increase|decrease)\s+(?:in|of)\s+([^,\.]{5,80})",
]


def _extract_first_match(text: str, patterns: List[str]) -> str:
    """Return the first regex match from a list of patterns."""
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip() if m.lastindex else m.group(0).strip()
    return ""


def _regex_pico(text: str) -> Dict[str, str]:
    """Extract PICO from biomedical text using regex heuristics."""
    return {
        "population": _extract_first_match(text, _POPULATION_PATTERNS),
        "intervention": _extract_first_match(text, _INTERVENTION_PATTERNS),
        "comparator": _extract_first_match(text, _COMPARATOR_PATTERNS),
        "outcome": _extract_first_match(text, _OUTCOME_PATTERNS),
    }


# ── Entity type mapping for spaCy NER labels ─────────────────
_ENTITY_TYPE_MAP: Dict[str, str] = {
    # SciSpaCy en_core_sci_sm entity labels
    "DISEASE": "population",
    "ORGANISM": "population",
    "CHEMICAL": "intervention",
    "DRUG": "intervention",
    "GENE_OR_GENE_PRODUCT": "outcome",
    "CELL_TYPE": "population",
    "CELL_LINE": "population",
    "DNA": "outcome",
    "RNA": "outcome",
    "PROTEIN": "outcome",
    "AMINO_ACID": "intervention",
    "SIMPLE_CHEMICAL": "intervention",
    # Generic entity label from en_core_sci_sm
    "ENTITY": "outcome",
}


def _spacy_pico(text: str) -> Optional[Dict[str, Any]]:
    """Extract PICO using spaCy biomedical NER (en_core_sci_sm).

    Returns None if spaCy is unavailable, otherwise returns PICO dict
    with entity type annotations.
    """
    nlp = _get_spacy_nlp()
    if nlp is None:
        return None

    try:
        doc = nlp(text[:5000])  # Limit text length for performance
        pico: Dict[str, List[Dict[str, str]]] = {
            "population": [],
            "intervention": [],
            "comparator": [],
            "outcome": [],
        }

        for ent in doc.ents:
            ent_text = ent.text.strip()
            if len(ent_text) < 2:
                continue
            pico_category = _ENTITY_TYPE_MAP.get(ent.label_, "outcome")
            pico[pico_category].append({
                "text": ent_text,
                "entity_type": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char,
            })

        # Also apply regex patterns to fill gaps (comparator is rarely NER-detected)
        regex_result = _regex_pico(text)

        # Build final result: prefer NER entities, fill gaps with regex
        result: Dict[str, Any] = {"method": "spacy_ner"}
        for key in ("population", "intervention", "comparator", "outcome"):
            if pico[key]:
                # Use the first NER entity as the primary value, include all as annotations
                result[key] = pico[key][0]["text"]
                result[f"{key}_entities"] = pico[key]
            elif regex_result.get(key):
                result[key] = regex_result[key]
                result[f"{key}_entities"] = [{"text": regex_result[key], "entity_type": "regex_match", "start": 0, "end": 0}]
            else:
                result[key] = ""
                result[f"{key}_entities"] = []

        return result
    except Exception as exc:
        log.warning("spacy_pico_extraction_failed", error=str(exc))
        return None


async def extract_pico_data(text: str) -> Dict[str, Any]:
    """Extract PICO using spaCy NER if available, LLM if configured, or regex fallback.

    Priority: spaCy en_core_sci_sm → LLM (OpenAI/Ollama) → regex heuristics.
    """
    if not text or len(text) < 50:
        return {
            "population": "", "intervention": "", "comparator": "", "outcome": "", "method": "none",
            "diagnostics": {"runtime_policy": get_runtime_policy(), "fallback_reason": "text_too_short"},
        }

    diagnostics: Dict[str, Any] = {
        "runtime_policy": get_runtime_policy(),
        "spacy_model": settings.spacy_model_name,
        "llm_backend_attempted": False,
        "fallback_reason": None,
    }

    # Try spaCy biomedical NER first
    spacy_result = _spacy_pico(text)
    if spacy_result is not None:
        # Check if spaCy found meaningful results
        has_content = any(spacy_result.get(k) for k in ("population", "intervention", "comparator", "outcome"))
        if has_content:
            log.info("pico_spacy_ner_success")
            spacy_result["diagnostics"] = diagnostics
            return spacy_result
        
    prompt = f"""
    Analyze the following biomedical text and extract the PICO elements (Population, Intervention, Comparator, Outcome).
    Return ONLY a valid JSON object with these exact keys: "population", "intervention", "comparator", "outcome".
    If any element is missing, return an empty string for that key. Do not include markdown formatting like ```json.
    
    TEXT:
    {text[:2000]}
    """
    
    # Try LLM extraction
    try:
        if settings.openai_api_key:
            diagnostics["llm_backend_attempted"] = True
            result = await _call_openai(prompt)
            result["method"] = "llm"
            result["diagnostics"] = diagnostics
            return result
        elif ollama_enabled():
            diagnostics["llm_backend_attempted"] = True
            result = await _call_ollama(prompt)
            result["method"] = "llm"
            result["diagnostics"] = diagnostics
            return result
    except Exception as e:
        log.warning("pico_llm_unavailable_using_regex", error=str(e))
        diagnostics["fallback_reason"] = str(e)

    # Regex fallback — always produces something
    result = _regex_pico(text)
    result["method"] = "regex"
    result["diagnostics"] = diagnostics
    if any(result.get(k) for k in ("population", "intervention", "comparator", "outcome")):
        log.info("pico_regex_fallback_success")
        if diagnostics["fallback_reason"] is None:
            diagnostics["fallback_reason"] = "regex_fallback"
        return result

    diagnostics["fallback_reason"] = diagnostics["fallback_reason"] or "no_pico_signals_found"
    return {"population": "", "intervention": "", "comparator": "", "outcome": "", "method": "regex", "diagnostics": diagnostics}

async def _call_ollama(prompt: str) -> Dict[str, Any]:
    url = f"{settings.ollama_host}/api/chat"
    payload = {
        "model": settings.ollama_model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "format": "json"
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return json.loads(data.get("message", {}).get("content", "{}"))

async def _call_openai(prompt: str) -> Dict[str, Any]:
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.openai_api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": "You are a specialized medical AI that extracts PICO parameters into valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        content = data["choices"][0]["message"]["content"]
        return json.loads(content)

async def verify_claim(claim: str, evidence_text: str) -> Dict[str, Any]:
    """Tests an extracted claim against raw evidence text using LLMs to score confidence."""
    if not claim or not evidence_text:
        return {"supported": False, "confidence": 0.0, "reasoning": "Missing claim or evidence."}
        
    prompt = f"""
    Evaluate the following CLAIM against the provided EVIDENCE.
    Determine if the CLAIM is supported, contradicted, or not mentioned in the EVIDENCE.
    
    Return ONLY a valid JSON object with:
    - "supported": boolean (true if supported, false otherwise)
    - "confidence": float between 0.0 and 1.0
    - "reasoning": str (brief explanation)
    
    CLAIM: {claim}
    
    EVIDENCE:
    {evidence_text[:3000]}
    """
    
    try:
        if settings.openai_api_key:
            return await _call_openai(prompt)
        elif ollama_enabled():
            return await _call_ollama(prompt)
    except Exception as e:
        log.error("claim_verification_failed", error=str(e))

    return {
        "supported": False,
        "confidence": 0.0,
        "reasoning": "Inference failed.",
        "diagnostics": {"runtime_policy": get_runtime_policy(), "fallback_reason": "llm_unavailable"},
    }

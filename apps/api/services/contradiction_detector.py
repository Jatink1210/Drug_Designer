"""Contradiction detection and confidence scoring for search results.

Uses keyword heuristic (always available) with optional LLM enhancement
when a runtime is reachable.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ── Opposing signal word pairs ──────────────────────────────
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

# ── Source URL templates ────────────────────────────────────
_SOURCE_URLS: Dict[str, str] = {
    "PubMed": "https://pubmed.ncbi.nlm.nih.gov/{id}/",
    "ClinicalTrials": "https://clinicaltrials.gov/study/{id}",
    "ChEMBL": "https://www.ebi.ac.uk/chembl/compound_report_card/{id}/",
    "OpenTargets": "https://platform.opentargets.org/target/{id}",
    "UniProt": "https://www.uniprot.org/uniprotkb/{id}",
    "RCSB": "https://www.rcsb.org/structure/{id}",
    "PubChem": "https://pubchem.ncbi.nlm.nih.gov/compound/{id}",
}


def compute_confidence(entity: Dict[str, Any], source_count: int) -> float:
    """Compute a 0–1 confidence score for a search result entity.

    Formula:
      base 0.3
      + 0.1 per unique source (max 3 → +0.3)
      + 0.1 if has DOI or PMID
      + 0.1 if published in last 5 years
      + 0.1 if has GWAS significance
      + 0.1 if multiple evidence types
    Capped at 1.0.
    """
    score = 0.3

    # Source diversity
    score += min(source_count, 3) * 0.1

    # Has DOI or PMID
    has_pmid = bool(entity.get("pmid") or entity.get("doi"))
    if has_pmid:
        score += 0.1

    # Recency
    year = entity.get("year")
    if year and isinstance(year, (int, float)):
        current_year = time.localtime().tm_year
        if current_year - int(year) <= 5:
            score += 0.1

    # GWAS significance
    if entity.get("gwas_significance"):
        score += 0.1

    # Multiple evidence types (has both publication refs and database IDs)
    evidence_types = set()
    if entity.get("pmid"):
        evidence_types.add("publication")
    if entity.get("nct_id"):
        evidence_types.add("trial")
    if entity.get("uniprot_id") or entity.get("pdb_id") or entity.get("chembl_url"):
        evidence_types.add("database")
    if len(evidence_types) >= 2:
        score += 0.1

    return min(score, 1.0)


def build_citation_refs(
    entity: Dict[str, Any],
    sources_hit: List[str],
) -> List[Dict[str, Any]]:
    """Extract citation references from an entity's fields."""
    refs: List[Dict[str, Any]] = []

    # PMID
    pmid = entity.get("pmid")
    if pmid:
        refs.append({
            "source": "PubMed",
            "external_id": f"PMID:{pmid}" if not str(pmid).startswith("PMID:") else str(pmid),
            "title": entity.get("title", ""),
            "year": entity.get("year"),
            "url": _SOURCE_URLS["PubMed"].format(id=str(pmid).replace("PMID:", "")),
            "confidence": 0.8,
            "evidence_type": "supporting",
        })

    # NCT
    nct = entity.get("nct_id")
    if nct:
        refs.append({
            "source": "ClinicalTrials",
            "external_id": str(nct),
            "title": entity.get("canonical_name", entity.get("name", "")),
            "year": None,
            "url": _SOURCE_URLS["ClinicalTrials"].format(id=nct),
            "confidence": 0.7,
            "evidence_type": "supporting",
        })

    # DOI
    doi = entity.get("doi")
    if doi:
        refs.append({
            "source": "DOI",
            "external_id": str(doi),
            "title": entity.get("title", ""),
            "year": entity.get("year"),
            "url": f"https://doi.org/{doi}",
            "confidence": 0.8,
            "evidence_type": "supporting",
        })

    # ChEMBL
    chembl_url = entity.get("chembl_url") or entity.get("url", "")
    if "chembl" in chembl_url.lower():
        refs.append({
            "source": "ChEMBL",
            "external_id": entity.get("id", ""),
            "title": entity.get("canonical_name", entity.get("name", "")),
            "year": None,
            "url": chembl_url,
            "confidence": 0.7,
            "evidence_type": "supporting",
        })

    # UniProt
    uniprot = entity.get("uniprot_id")
    if uniprot:
        refs.append({
            "source": "UniProt",
            "external_id": str(uniprot),
            "title": entity.get("canonical_name", entity.get("name", "")),
            "year": None,
            "url": _SOURCE_URLS["UniProt"].format(id=uniprot),
            "confidence": 0.9,
            "evidence_type": "supporting",
        })

    # If no specific refs but we have source info, add generic
    if not refs and sources_hit:
        refs.append({
            "source": sources_hit[0] if sources_hit else "unknown",
            "external_id": entity.get("id", ""),
            "title": entity.get("canonical_name", entity.get("name", "")),
            "year": entity.get("year"),
            "url": entity.get("url", ""),
            "confidence": 0.4,
            "evidence_type": "neutral",
        })

    return refs


def _extract_texts(entities: Dict[str, List[Dict[str, Any]]]) -> List[Tuple[str, Dict[str, Any]]]:
    """Extract descriptive text from entities for contradiction analysis."""
    texts: List[Tuple[str, Dict[str, Any]]] = []
    for _etype, ents in entities.items():
        for ent in ents:
            text_parts = []
            for field in ("description", "function_description", "abstract",
                          "mechanism_of_action", "canonical_name", "name"):
                val = ent.get(field, "")
                if val:
                    text_parts.append(str(val))
            combined = " ".join(text_parts).strip()
            if combined:
                texts.append((combined, ent))
    return texts


def _keyword_heuristic(
    texts: List[Tuple[str, Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Detect contradictions via opposing keyword pairs."""
    contradictions: List[Dict[str, Any]] = []

    for i in range(len(texts)):
        text_a, ent_a = texts[i]
        lower_a = text_a.lower()
        for j in range(i + 1, len(texts)):
            text_b, ent_b = texts[j]
            lower_b = text_b.lower()

            for word_a, word_b in _CONTRADICTION_PAIRS:
                if (word_a in lower_a and word_b in lower_b) or \
                   (word_b in lower_a and word_a in lower_b):
                    # Build citation refs for A and B
                    ref_a = {
                        "source": ent_a.get("entity_type", "unknown"),
                        "external_id": ent_a.get("id", ""),
                        "title": ent_a.get("canonical_name", ent_a.get("name", "")),
                        "year": ent_a.get("year"),
                        "url": ent_a.get("url", ""),
                        "confidence": ent_a.get("_confidence", 0.5),
                    }
                    ref_b = {
                        "source": ent_b.get("entity_type", "unknown"),
                        "external_id": ent_b.get("id", ""),
                        "title": ent_b.get("canonical_name", ent_b.get("name", "")),
                        "year": ent_b.get("year"),
                        "url": ent_b.get("url", ""),
                        "confidence": ent_b.get("_confidence", 0.5),
                    }

                    # Truncate claims for display
                    claim_a = text_a[:200].strip()
                    claim_b = text_b[:200].strip()

                    contradictions.append({
                        "claim_a": claim_a,
                        "claim_b": claim_b,
                        "source_a": ref_a,
                        "source_b": ref_b,
                        "severity": "moderate",
                        "explanation": f"Opposing terms detected: '{word_a}' vs '{word_b}'",
                    })
                    break  # one contradiction per pair of entities is enough

    return contradictions


async def _llm_contradiction_check(
    texts: List[str],
    query: str,
) -> Optional[List[Dict[str, Any]]]:
    """Attempt LLM-based contradiction detection. Returns None if unavailable."""
    try:
        from services.runtime.selector import RuntimeSelector
        runtime = RuntimeSelector.get_active_runtime()
        healthy = await runtime.health_check()
        if not healthy:
            return None
    except Exception:
        return None

    # Build prompt with up to 10 claims
    claims = texts[:10]
    numbered = "\n".join(f"{i+1}. {c[:300]}" for i, c in enumerate(claims))
    prompt = (
        f"Given these research findings about '{query}', identify any contradictions "
        f"between them. Return JSON array of objects with fields: "
        f"claim_a_index (int), claim_b_index (int), severity (low/moderate/high), "
        f"explanation (string). If no contradictions, return empty array [].\n\n"
        f"Findings:\n{numbered}\n\nJSON:"
    )

    try:
        response = await runtime.chat([{"role": "user", "content": prompt}])
        text = response.get("content", "").strip()
        # Try to extract JSON from response
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            parsed = json.loads(text[start:end + 1])
            if isinstance(parsed, list):
                return parsed
    except Exception as exc:
        log.debug("LLM contradiction check failed: %s", exc)

    return None


async def detect_contradictions(
    entities: Dict[str, List[Dict[str, Any]]],
    query: str,
) -> List[Dict[str, Any]]:
    """Run contradiction detection on search results.

    Always runs keyword heuristic. Optionally enhances with LLM if available.
    """
    texts = _extract_texts(entities)
    if len(texts) < 2:
        return []

    # Always run keyword heuristic
    contradictions = _keyword_heuristic(texts)

    # Try LLM enhancement
    try:
        plain_texts = [t for t, _ in texts]
        llm_results = await _llm_contradiction_check(plain_texts, query)
        if llm_results:
            for item in llm_results:
                idx_a = item.get("claim_a_index", 0) - 1
                idx_b = item.get("claim_b_index", 0) - 1
                if 0 <= idx_a < len(texts) and 0 <= idx_b < len(texts):
                    text_a, ent_a = texts[idx_a]
                    text_b, ent_b = texts[idx_b]
                    contradictions.append({
                        "claim_a": text_a[:200],
                        "claim_b": text_b[:200],
                        "source_a": {
                            "source": ent_a.get("entity_type", "unknown"),
                            "external_id": ent_a.get("id", ""),
                            "title": ent_a.get("canonical_name", ent_a.get("name", "")),
                            "year": ent_a.get("year"),
                            "url": ent_a.get("url", ""),
                            "confidence": ent_a.get("_confidence", 0.5),
                        },
                        "source_b": {
                            "source": ent_b.get("entity_type", "unknown"),
                            "external_id": ent_b.get("id", ""),
                            "title": ent_b.get("canonical_name", ent_b.get("name", "")),
                            "year": ent_b.get("year"),
                            "url": ent_b.get("url", ""),
                            "confidence": ent_b.get("_confidence", 0.5),
                        },
                        "severity": item.get("severity", "moderate"),
                        "explanation": item.get("explanation", "Detected by LLM analysis"),
                    })
    except Exception as exc:
        log.debug("LLM contradiction enhancement skipped: %s", exc)

    # Deduplicate by entity pair
    seen = set()
    unique: List[Dict[str, Any]] = []
    for c in contradictions:
        key = (c["source_a"].get("external_id", ""), c["source_b"].get("external_id", ""))
        rev = (key[1], key[0])
        if key not in seen and rev not in seen:
            seen.add(key)
            unique.append(c)

    return unique

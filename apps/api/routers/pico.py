"""PICO Verification API (Task 22).

POST /api/v1/pico/extract — Extract PICO elements from publications.
Requirements: 12.1, 12.2, 12.3, 12.4
"""

from typing import Any, Dict, List

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from models.envelope import build_envelope as _shared_envelope
from routers.auth import get_current_user

router = APIRouter(prefix="/api/v1/pico", tags=["pico"])


def _build_envelope(req: Request, data: Any) -> Dict[str, Any]:
    return _shared_envelope(req, data)


class PICOExtractRequest(BaseModel):
    """Request for PICO extraction."""
    query: str = Field("", description="Search query to find publications")
    texts: List[str] = Field(default_factory=list, description="Direct text inputs for PICO extraction")
    max_publications: int = Field(10, description="Maximum publications to analyze")


@router.post("/extract")
async def extract_pico(
    body: PICOExtractRequest,
    request: Request,
    user=Depends(get_current_user),
) -> Dict[str, Any]:
    """POST /api/v1/pico/extract — Extract PICO elements from publications.

    Returns PICO extractions per publication with Population, Intervention,
    Comparison, Outcome elements, study design, sample size, and confidence scores.
    Also generates a summary and evidence quality assessment.

    Requirements: 12.1, 12.2, 12.3, 12.4
    """
    from services.pico_extractor import extract_pico_data

    extractions: List[Dict[str, Any]] = []

    # Process direct text inputs
    for i, text in enumerate(body.texts[:body.max_publications]):
        pico = await extract_pico_data(text)
        extractions.append({
            "publication_index": i,
            "source": "direct_input",
            "title": text[:100] + "..." if len(text) > 100 else text,
            "population": {
                "text": pico.get("population", ""),
                "entities": [],
                "qualifiers": [],
                "confidence": 0.7 if pico.get("population") else 0.0,
            },
            "intervention": {
                "text": pico.get("intervention", ""),
                "entities": [],
                "qualifiers": [],
                "confidence": 0.7 if pico.get("intervention") else 0.0,
            },
            "comparison": {
                "text": pico.get("comparator", ""),
                "entities": [],
                "qualifiers": [],
                "confidence": 0.6 if pico.get("comparator") else 0.0,
            },
            "outcome": {
                "text": pico.get("outcome", ""),
                "entities": [],
                "qualifiers": [],
                "confidence": 0.7 if pico.get("outcome") else 0.0,
            },
            "study_design": _infer_study_design(text),
            "sample_size": _extract_sample_size(text),
            "overall_confidence": _compute_overall_confidence(pico),
        })

    # If query provided, search publications and extract PICO
    if body.query and not body.texts:
        try:
            from connectors.pubmed import PubMedConnector
            pm = PubMedConnector()
            results = await pm.search(body.query, limit=body.max_publications)
            items = results.get("items", [])
            for i, item in enumerate(items):
                abstract = item.get("abstract", item.get("description", item.get("snippet", "")))
                if not abstract:
                    continue
                pico = await extract_pico_data(abstract)
                extractions.append({
                    "publication_index": i,
                    "source": "PubMed",
                    "title": item.get("title", item.get("canonical_name", "")),
                    "pmid": item.get("pmid", item.get("id", "")),
                    "year": item.get("year"),
                    "population": {
                        "text": pico.get("population", ""),
                        "entities": [],
                        "qualifiers": [],
                        "confidence": 0.7 if pico.get("population") else 0.0,
                    },
                    "intervention": {
                        "text": pico.get("intervention", ""),
                        "entities": [],
                        "qualifiers": [],
                        "confidence": 0.7 if pico.get("intervention") else 0.0,
                    },
                    "comparison": {
                        "text": pico.get("comparator", ""),
                        "entities": [],
                        "qualifiers": [],
                        "confidence": 0.6 if pico.get("comparator") else 0.0,
                    },
                    "outcome": {
                        "text": pico.get("outcome", ""),
                        "entities": [],
                        "qualifiers": [],
                        "confidence": 0.7 if pico.get("outcome") else 0.0,
                    },
                    "study_design": _infer_study_design(abstract),
                    "sample_size": _extract_sample_size(abstract),
                    "overall_confidence": _compute_overall_confidence(pico),
                })
        except Exception:
            pass

    # Generate summary and quality assessment
    summary = _generate_pico_summary(extractions)
    quality = _assess_evidence_quality(extractions)

    return _build_envelope(request, {
        "query": body.query,
        "extractions": extractions,
        "total_publications": len(extractions),
        "summary": summary,
        "evidence_quality": quality,
    })


def _infer_study_design(text: str) -> str:
    """Infer study design from text."""
    import re
    lower = text.lower()
    if re.search(r"meta.analysis|systematic\s+review", lower):
        return "meta-analysis"
    if re.search(r"randomized|rct|double.blind|placebo.controlled", lower):
        return "randomized_controlled_trial"
    if re.search(r"cohort|prospective|longitudinal", lower):
        return "cohort_study"
    if re.search(r"case.control", lower):
        return "case_control"
    if re.search(r"cross.sectional|survey", lower):
        return "cross_sectional"
    if re.search(r"case\s+report|case\s+series", lower):
        return "case_report"
    if re.search(r"in\s*vitro|cell\s+line|cell\s+culture", lower):
        return "in_vitro"
    if re.search(r"in\s*vivo|animal|mouse|mice|rat", lower):
        return "in_vivo"
    return "unknown"


def _extract_sample_size(text: str) -> int | None:
    """Extract sample size from text."""
    import re
    patterns = [
        r"(?:n\s*=\s*)(\d[\d,]*)",
        r"(\d[\d,]*)\s*(?:patients?|subjects?|participants?|individuals?)",
        r"(?:enrolled|recruited|included)\s+(\d[\d,]*)",
        r"(?:sample\s+(?:size|of))\s+(\d[\d,]*)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            try:
                return int(m.group(1).replace(",", ""))
            except ValueError:
                continue
    return None


def _compute_overall_confidence(pico: Dict[str, str]) -> float:
    """Compute overall extraction confidence."""
    filled = sum(1 for k in ("population", "intervention", "comparator", "outcome") if pico.get(k))
    return round(filled / 4.0, 2)


def _generate_pico_summary(extractions: List[Dict[str, Any]]) -> str:
    """Generate a summary of PICO extractions."""
    if not extractions:
        return "No publications analyzed."

    total = len(extractions)
    with_population = sum(1 for e in extractions if e.get("population", {}).get("text"))
    with_intervention = sum(1 for e in extractions if e.get("intervention", {}).get("text"))
    with_comparison = sum(1 for e in extractions if e.get("comparison", {}).get("text"))
    with_outcome = sum(1 for e in extractions if e.get("outcome", {}).get("text"))

    designs = {}
    for e in extractions:
        d = e.get("study_design", "unknown")
        designs[d] = designs.get(d, 0) + 1

    summary_parts = [
        f"Analyzed {total} publication(s).",
        f"Population identified in {with_population}/{total}.",
        f"Intervention identified in {with_intervention}/{total}.",
        f"Comparison identified in {with_comparison}/{total}.",
        f"Outcome identified in {with_outcome}/{total}.",
    ]

    if designs:
        design_str = ", ".join(f"{k}: {v}" for k, v in sorted(designs.items(), key=lambda x: -x[1]))
        summary_parts.append(f"Study designs: {design_str}.")

    return " ".join(summary_parts)


def _assess_evidence_quality(extractions: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Assess overall evidence quality."""
    if not extractions:
        return {"grade": "insufficient", "score": 0.0, "details": "No publications to assess."}

    avg_confidence = sum(e.get("overall_confidence", 0) for e in extractions) / len(extractions)

    # Count high-quality study designs
    high_quality_designs = {"randomized_controlled_trial", "meta-analysis"}
    hq_count = sum(1 for e in extractions if e.get("study_design") in high_quality_designs)

    score = avg_confidence * 0.6 + (hq_count / max(len(extractions), 1)) * 0.4

    if score >= 0.7:
        grade = "high"
    elif score >= 0.4:
        grade = "moderate"
    elif score >= 0.2:
        grade = "low"
    else:
        grade = "very_low"

    return {
        "grade": grade,
        "score": round(score, 2),
        "average_extraction_confidence": round(avg_confidence, 2),
        "high_quality_study_count": hq_count,
        "total_publications": len(extractions),
        "details": f"Evidence quality is {grade} based on {len(extractions)} publications "
                   f"with average extraction confidence of {avg_confidence:.0%}.",
    }

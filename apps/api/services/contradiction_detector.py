"""Contradiction detection, similarity analysis, and confidence scoring.

Uses keyword heuristic (always available) with optional LLM enhancement
when a runtime is reachable. Includes experimental context extraction
to explain *why* papers disagree (in vivo vs in vitro, methodology diffs, etc.).
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Dict, List, Optional, Tuple

log = logging.getLogger(__name__)

# ── Experimental context patterns ───────────────────────────
_CONTEXT_PATTERNS = {
    "in_vivo": re.compile(r"\b(in\s*vivo|animal\s+model|mouse|mice|rat|murine|primate|rabbit|zebrafish|xenograft)\b", re.I),
    "in_vitro": re.compile(r"\b(in\s*vitro|cell\s+line|cell\s+culture|HEK293|HeLa|MCF-?7|A549|Jurkat|primary\s+cells)\b", re.I),
    "in_silico": re.compile(r"\b(in\s*silico|computational|molecular\s+docking|simulation|bioinformatics|homology\s+model)\b", re.I),
    "clinical": re.compile(r"\b(clinical\s+trial|patient|cohort|randomized|phase\s+[I1-4]|double.blind|placebo|human\s+subject)\b", re.I),
    "meta_analysis": re.compile(r"\b(meta.analysis|systematic\s+review|pooled\s+analysis)\b", re.I),
}

_MODEL_ORGANISM_PAT = re.compile(
    r"\b(mouse|mice|murine|rat|rabbit|primate|zebrafish|drosophila|C\.\s*elegans|"
    r"xenopus|hamster|guinea\s+pig|canine|porcine|bovine)\b", re.I
)

_CELL_LINE_PAT = re.compile(
    r"\b(HEK293|HeLa|MCF-?7|A549|Jurkat|U937|THP-?1|Caco-?2|MDCK|CHO|"
    r"SH-SY5Y|PC-?12|BV-?2|RAW264|NIH3T3|HepG2|SK-BR-?3)\b", re.I
)

_METHODOLOGY_PAT = re.compile(
    r"\b(western\s+blot|PCR|qPCR|RT-PCR|ELISA|mass\s+spec|NMR|X-ray|cryo-EM|"
    r"RNA-seq|ChIP-seq|CRISPR|siRNA|shRNA|flow\s+cytometry|immunohistochemistry|"
    r"IHC|confocal|microscopy|SPR|BLI|LC-MS|GC-MS|HPLC)\b", re.I
)


def _extract_context(text: str) -> Dict[str, Any]:
    """Extract experimental context: study type, model organism, cell lines, methods."""
    ctx: Dict[str, Any] = {
        "study_type": "unknown",
        "model_organisms": [],
        "cell_lines": [],
        "methodologies": [],
    }

    for stype, pat in _CONTEXT_PATTERNS.items():
        if pat.search(text):
            ctx["study_type"] = stype
            break

    organisms = _MODEL_ORGANISM_PAT.findall(text)
    ctx["model_organisms"] = list(set(o.strip() for o in organisms))[:3]

    cells = _CELL_LINE_PAT.findall(text)
    ctx["cell_lines"] = list(set(c.strip() for c in cells))[:3]

    methods = _METHODOLOGY_PAT.findall(text)
    ctx["methodologies"] = list(set(m.strip() for m in methods))[:5]

    return ctx

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
    import re
    _html_re = re.compile(r"<[^>]+>")
    texts: List[Tuple[str, Dict[str, Any]]] = []
    for _etype, ents in entities.items():
        for ent in ents:
            text_parts = []
            for field in ("description", "function_description", "abstract",
                          "mechanism_of_action", "canonical_name", "name",
                          "title", "snippet"):
                val = ent.get(field, "")
                if val:
                    # Strip any residual HTML tags from source APIs
                    val = _html_re.sub("", str(val))
                    text_parts.append(val)
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

                    # Extract experimental context for both sides
                    ctx_a = _extract_context(text_a)
                    ctx_b = _extract_context(text_b)

                    # Build contextual explanation
                    ctx_explanation = f"Opposing terms detected: '{word_a}' vs '{word_b}'"
                    if ctx_a["study_type"] != "unknown" or ctx_b["study_type"] != "unknown":
                        ctx_explanation += f". Context: A={ctx_a['study_type']}"
                        if ctx_a["model_organisms"]:
                            ctx_explanation += f" ({', '.join(ctx_a['model_organisms'])})"
                        if ctx_a["cell_lines"]:
                            ctx_explanation += f" [{', '.join(ctx_a['cell_lines'])}]"
                        ctx_explanation += f", B={ctx_b['study_type']}"
                        if ctx_b["model_organisms"]:
                            ctx_explanation += f" ({', '.join(ctx_b['model_organisms'])})"
                        if ctx_b["cell_lines"]:
                            ctx_explanation += f" [{', '.join(ctx_b['cell_lines'])}]"

                    contradictions.append({
                        "claim_a": claim_a,
                        "claim_b": claim_b,
                        "source_a": ref_a,
                        "source_b": ref_b,
                        "severity": "moderate",
                        "explanation": ctx_explanation,
                        "context_a": ctx_a,
                        "context_b": ctx_b,
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


class ContradictionDetector:
    """Class-based wrapper for the contradiction detection pipeline.

    Used by SynthArena and other services that need an instance-based API.
    """

    async def detect(self, query: str) -> List[Dict[str, Any]]:
        """Detect contradictions for a given query by fetching evidence from connectors."""
        entities: Dict[str, List[Dict[str, Any]]] = {}
        try:
            from connectors.pubmed import PubMedConnector
            pm = PubMedConnector()
            result = await pm.search(query, limit=10)
            items = result.get("items", [])
            if items:
                entities["pubmed"] = items
        except Exception:
            pass

        try:
            from connectors.opentargets import OpenTargetsConnector
            ot = OpenTargetsConnector()
            result = await ot.search(query, limit=5)
            items = result.get("items", [])
            if items:
                entities["opentargets"] = items
        except Exception:
            pass

        if not entities:
            return []

        return await detect_contradictions(entities, query)


# ═══════════════════════════════════════════════════════════
# Enhanced Contradiction & Similarity Engine (Task 21)
# ═══════════════════════════════════════════════════════════

# Contradiction type classification patterns
_DIRECTIONAL_PAIRS = {("inhibits", "activates"), ("inhibitor", "activator"), ("antagonist", "agonist"),
                       ("promotes", "suppresses"), ("upregulated", "downregulated"),
                       ("up-regulated", "down-regulated"), ("overexpressed", "underexpressed")}
_TEMPORAL_KEYWORDS = {"early", "late", "acute", "chronic", "short-term", "long-term", "initial", "sustained"}
_MAGNITUDE_PAIRS = {("significant", "not significant"), ("effective", "ineffective"),
                     ("increases", "decreases"), ("positive correlation", "negative correlation")}
_CAUSAL_PAIRS = {("risk factor", "protective"), ("oncogene", "tumor suppressor"),
                  ("associated with", "not associated with"), ("beneficial", "harmful")}


def _classify_contradiction_type(word_a: str, word_b: str, text_a: str, text_b: str) -> str:
    """Classify contradiction type: directional, temporal, magnitude, or causal."""
    pair = (word_a.lower(), word_b.lower())
    rev_pair = (word_b.lower(), word_a.lower())

    if pair in _DIRECTIONAL_PAIRS or rev_pair in _DIRECTIONAL_PAIRS:
        return "directional"
    if pair in _MAGNITUDE_PAIRS or rev_pair in _MAGNITUDE_PAIRS:
        return "magnitude"
    if pair in _CAUSAL_PAIRS or rev_pair in _CAUSAL_PAIRS:
        return "causal"

    # Check for temporal context
    lower_a = text_a.lower()
    lower_b = text_b.lower()
    temporal_a = any(kw in lower_a for kw in _TEMPORAL_KEYWORDS)
    temporal_b = any(kw in lower_b for kw in _TEMPORAL_KEYWORDS)
    if temporal_a or temporal_b:
        return "temporal"

    return "directional"  # default


def _compute_severity(ctx_a: Dict[str, Any], ctx_b: Dict[str, Any],
                       conf_a: float, conf_b: float) -> str:
    """Compute contradiction severity: high, medium, or low."""
    # High: both from clinical/meta-analysis with high confidence
    high_types = {"clinical", "meta_analysis"}
    if ctx_a.get("study_type") in high_types and ctx_b.get("study_type") in high_types:
        return "high"
    if conf_a > 0.7 and conf_b > 0.7:
        return "high"

    # Low: one is in_silico or unknown
    low_types = {"in_silico", "unknown"}
    if ctx_a.get("study_type") in low_types or ctx_b.get("study_type") in low_types:
        return "low"

    return "medium"


def _suggest_resolution(contradiction_type: str, ctx_a: Dict[str, Any], ctx_b: Dict[str, Any]) -> str:
    """Generate a resolution suggestion for a contradiction."""
    suggestions = {
        "directional": "Review the experimental conditions and model systems used in each study. "
                       "Differences in cell lines, model organisms, or dosage may explain opposing effects.",
        "temporal": "Consider the time course of the studies. Effects may differ between acute and chronic exposure, "
                    "or between early and late disease stages.",
        "magnitude": "Examine statistical methods and sample sizes. Differences in statistical power or "
                     "endpoint definitions may account for conflicting significance findings.",
        "causal": "Evaluate the causal evidence strength. Genetic studies (GWAS, Mendelian randomization) "
                  "may provide stronger causal evidence than observational studies.",
    }
    base = suggestions.get(contradiction_type, "Further investigation recommended.")

    if ctx_a.get("study_type") != ctx_b.get("study_type"):
        base += f" Note: studies use different approaches ({ctx_a.get('study_type', 'unknown')} vs {ctx_b.get('study_type', 'unknown')})."

    return base


def _find_similarity_clusters(
    texts: List[Tuple[str, Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    """Group similar claims into clusters using NLP cosine similarity when available,
    falling back to Jaccard keyword overlap."""
    from services.nlp_contradiction_engine import get_nlp_engine

    engine = get_nlp_engine()
    clusters: List[Dict[str, Any]] = []
    used = set()

    for i in range(len(texts)):
        if i in used:
            continue
        text_a, ent_a = texts[i]
        cluster_members = [{"text": text_a[:200], "source": ent_a.get("entity_type", "unknown"),
                            "id": ent_a.get("id", ""), "name": ent_a.get("canonical_name", ent_a.get("name", ""))}]
        shared_entities: List[str] = []
        sim_scores: List[float] = []

        for j in range(i + 1, len(texts)):
            if j in used:
                continue
            text_b, ent_b = texts[j]

            # Use NLP engine's compute_similarity (cosine when available, Jaccard fallback)
            similarity = engine.compute_similarity(text_a, text_b)

            if similarity > 0.3:  # threshold for similarity
                cluster_members.append({
                    "text": text_b[:200],
                    "source": ent_b.get("entity_type", "unknown"),
                    "id": ent_b.get("id", ""),
                    "name": ent_b.get("canonical_name", ent_b.get("name", "")),
                })
                sim_scores.append(similarity)
                used.add(j)

                # Track shared entity names
                name_a = (ent_a.get("canonical_name") or ent_a.get("name") or "").lower()
                name_b = (ent_b.get("canonical_name") or ent_b.get("name") or "").lower()
                if name_a and name_b and name_a == name_b:
                    shared_entities.append(name_a)

        if len(cluster_members) >= 2:
            avg_similarity = round(sum(sim_scores) / len(sim_scores), 2) if sim_scores else 0.5
            consensus = "strong" if len(cluster_members) >= 4 else ("moderate" if len(cluster_members) >= 2 else "weak")
            clusters.append({
                "cluster_id": f"sim_{i}",
                "members": cluster_members,
                "member_count": len(cluster_members),
                "similarity_score": avg_similarity,
                "shared_entities": list(set(shared_entities)),
                "consensus_strength": consensus,
            })
            used.add(i)

    return clusters


def _build_evidence_landscape(
    contradictions: List[Dict[str, Any]],
    similarities: List[Dict[str, Any]],
    total_sources: int,
) -> Dict[str, Any]:
    """Generate evidence landscape summary."""
    supporting_count = sum(c.get("member_count", 0) for c in similarities)
    contradicting_count = len(contradictions)

    return {
        "total_sources_analyzed": total_sources,
        "contradictions_found": contradicting_count,
        "similarity_clusters_found": len(similarities),
        "supporting_evidence_count": supporting_count,
        "contradicting_evidence_count": contradicting_count,
        "overall_consensus": (
            "strong" if contradicting_count == 0 and supporting_count > 3
            else "moderate" if contradicting_count <= 2
            else "weak" if contradicting_count <= 5
            else "conflicted"
        ),
        "severity_distribution": {
            "high": sum(1 for c in contradictions if c.get("severity") == "high"),
            "medium": sum(1 for c in contradictions if c.get("severity") == "medium"),
            "low": sum(1 for c in contradictions if c.get("severity") == "low"),
        },
        "type_distribution": {
            "directional": sum(1 for c in contradictions if c.get("contradiction_type") == "directional"),
            "temporal": sum(1 for c in contradictions if c.get("contradiction_type") == "temporal"),
            "magnitude": sum(1 for c in contradictions if c.get("contradiction_type") == "magnitude"),
            "causal": sum(1 for c in contradictions if c.get("contradiction_type") == "causal"),
        },
    }


async def analyze_contradictions_and_similarities(
    query: str,
) -> Dict[str, Any]:
    """Full contradiction & similarity analysis pipeline.

    Uses NLP engine (PubMedBERT + BioNLI) as primary method when available,
    falling back to keyword heuristic. Returns contradictions, similarity
    clusters, and evidence landscape.
    Requirements: 11.1, 11.2, 11.3, 11.4, 11.5, 11.6
    """
    from services.nlp_contradiction_engine import get_nlp_engine

    engine = get_nlp_engine()
    # Lazy-initialize NLP models on first analysis call
    await engine.initialize()

    # Fetch evidence from connectors
    entities: Dict[str, List[Dict[str, Any]]] = {}
    try:
        from connectors.pubmed import PubMedConnector
        pm = PubMedConnector()
        result = await pm.search(query, limit=15)
        items = result.get("items", [])
        if items:
            entities["pubmed"] = items
    except Exception:
        pass

    try:
        from connectors.opentargets import OpenTargetsConnector
        ot = OpenTargetsConnector()
        result = await ot.search(query, limit=10)
        items = result.get("items", [])
        if items:
            entities["opentargets"] = items
    except Exception:
        pass

    try:
        from connectors.chembl import ChEMBLConnector
        ch = ChEMBLConnector()
        result = await ch.search(query, limit=5)
        items = result.get("items", [])
        if items:
            entities["chembl"] = items
    except Exception:
        pass

    texts = _extract_texts(entities)
    if len(texts) < 2:
        return {
            "contradictions": [],
            "similarities": [],
            "evidence_landscape": _build_evidence_landscape([], [], len(texts)),
            "method_used": engine.get_method_used(),
        }

    # ── Primary: NLP-based contradiction detection ──────────
    raw_contradictions: List[Dict[str, Any]] = []

    for i in range(len(texts)):
        text_a, ent_a = texts[i]
        for j in range(i + 1, len(texts)):
            text_b, ent_b = texts[j]

            # Use NLP engine's classify_pair (NLI model or keyword fallback)
            nli_result = engine.classify_pair(text_a[:512], text_b[:512])

            if nli_result.label == "contradiction":
                ctx_a = engine.extract_context(text_a)
                ctx_b = engine.extract_context(text_b)

                # Compute context alignment (how similar the experimental contexts are)
                context_alignment = 1.0 if ctx_a.study_type == ctx_b.study_type else 0.5
                source_quality_a = ent_a.get("_confidence", 0.5)
                source_quality_b = ent_b.get("_confidence", 0.5)
                source_quality = (source_quality_a + source_quality_b) / 2

                confidence = engine.compute_confidence(
                    nli_result.confidence, context_alignment, source_quality
                )

                # Determine contradiction type from keyword pairs if found
                c_type = "directional"
                lower_a = text_a.lower()
                lower_b = text_b.lower()
                for wa, wb in _CONTRADICTION_PAIRS:
                    if (wa in lower_a and wb in lower_b) or (wb in lower_a and wa in lower_b):
                        c_type = engine.classify_contradiction_type(wa, wb, text_a, text_b)
                        break

                # Temporal reasoning
                year_a = ent_a.get("year")
                year_b = ent_b.get("year")
                temporal_note = engine.compare_temporal(
                    int(year_a) if year_a else None,
                    int(year_b) if year_b else None,
                )

                ref_a = {
                    "source": ent_a.get("entity_type", "unknown"),
                    "external_id": ent_a.get("id", ""),
                    "title": ent_a.get("canonical_name", ent_a.get("name", "")),
                    "year": ent_a.get("year"),
                    "url": ent_a.get("url", ""),
                    "confidence": source_quality_a,
                }
                ref_b = {
                    "source": ent_b.get("entity_type", "unknown"),
                    "external_id": ent_b.get("id", ""),
                    "title": ent_b.get("canonical_name", ent_b.get("name", "")),
                    "year": ent_b.get("year"),
                    "url": ent_b.get("url", ""),
                    "confidence": source_quality_b,
                }

                severity = _compute_severity(ctx_a.model_dump(), ctx_b.model_dump(), source_quality_a, source_quality_b)
                resolution = _suggest_resolution(c_type, ctx_a.model_dump(), ctx_b.model_dump())

                raw_contradictions.append({
                    "claim_a": text_a[:200].strip(),
                    "claim_b": text_b[:200].strip(),
                    "source_a": ref_a,
                    "source_b": ref_b,
                    "contradiction_type": c_type,
                    "severity": severity,
                    "confidence": round(confidence, 3),
                    "explanation": f"NLI: {nli_result.label} ({nli_result.confidence:.2f}). Method: {nli_result.method}",
                    "context_a": ctx_a.model_dump(),
                    "context_b": ctx_b.model_dump(),
                    "temporal_note": temporal_note,
                    "resolution_suggestion": resolution,
                    "nli_method": nli_result.method,
                })

    # ── Fallback: also run keyword heuristic to catch anything NLI missed ──
    keyword_contradictions = _keyword_heuristic(texts)
    for c in keyword_contradictions:
        explanation = c.get("explanation", "")
        word_a = word_b = ""
        for wa, wb in _CONTRADICTION_PAIRS:
            if wa in explanation.lower() and wb in explanation.lower():
                word_a, word_b = wa, wb
                break
        ctx_a = c.get("context_a", {})
        ctx_b = c.get("context_b", {})
        conf_a = c.get("source_a", {}).get("confidence", 0.5)
        conf_b = c.get("source_b", {}).get("confidence", 0.5)
        c["contradiction_type"] = _classify_contradiction_type(word_a, word_b, c.get("claim_a", ""), c.get("claim_b", ""))
        c["severity"] = _compute_severity(ctx_a, ctx_b, conf_a, conf_b)
        c["resolution_suggestion"] = _suggest_resolution(c["contradiction_type"], ctx_a, ctx_b)
        c["nli_method"] = "keyword_heuristic"
        raw_contradictions.append(c)

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
                    raw_contradictions.append({
                        "claim_a": text_a[:200],
                        "claim_b": text_b[:200],
                        "source_a": {
                            "source": ent_a.get("entity_type", "unknown"),
                            "external_id": ent_a.get("id", ""),
                            "title": ent_a.get("canonical_name", ent_a.get("name", "")),
                        },
                        "source_b": {
                            "source": ent_b.get("entity_type", "unknown"),
                            "external_id": ent_b.get("id", ""),
                            "title": ent_b.get("canonical_name", ent_b.get("name", "")),
                        },
                        "contradiction_type": "directional",
                        "severity": item.get("severity", "medium"),
                        "explanation": item.get("explanation", "Detected by LLM analysis"),
                        "resolution_suggestion": "Review the original publications for detailed methodology comparison.",
                        "nli_method": "llm",
                    })
    except Exception:
        pass

    # Deduplicate
    seen = set()
    unique_contradictions: List[Dict[str, Any]] = []
    for c in raw_contradictions:
        key = (c.get("source_a", {}).get("external_id", ""), c.get("source_b", {}).get("external_id", ""))
        rev = (key[1], key[0])
        if key not in seen and rev not in seen:
            seen.add(key)
            unique_contradictions.append(c)

    # Find similarity clusters (uses NLP engine internally)
    similarities = _find_similarity_clusters(texts)

    # Build evidence landscape
    landscape = _build_evidence_landscape(unique_contradictions, similarities, len(texts))

    return {
        "contradictions": unique_contradictions,
        "similarities": similarities,
        "evidence_landscape": landscape,
        "method_used": engine.get_method_used(),
    }

"""Advanced contradiction detector — Phase C (§18).

Five specialised detection functions:
  1. detect_directional   — inhibition vs activation
  2. detect_temporal      — reversal >5 yr apart
  3. detect_score_divergence — std(confidence) > threshold
  4. detect_methodological — in-vitro vs clinical mismatch
  5. detect_population    — ethnicity / Indian pop conflicts
  6. run_all              — runs all, deduplicates

Each function accepts a list of EvidenceItemRecord-like dicts (or ORM objects)
and returns a list of ContradictionResult dataclasses.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from statistics import stdev
from typing import Any, Dict, List, Optional, Sequence, Tuple

import structlog

log = structlog.get_logger(__name__)

# ---------------------------------------------------------------------------
# Shared data structures
# ---------------------------------------------------------------------------

@dataclass
class ContradictionResult:
    """A detected contradiction between two evidence items."""
    id: str                       # deterministic: "type:idA:idB"
    contradiction_type: str       # directional | temporal | score_divergence | methodological | population
    item_a_id: str
    item_b_id: str
    item_a_title: str
    item_b_title: str
    item_a_source: str
    item_b_source: str
    detail: str                   # human-readable explanation
    confidence: float = 0.7
    group_key: str = ""           # e.g. gene symbol shared by both items
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "contradiction_type": self.contradiction_type,
            "item_a": {"id": self.item_a_id, "title": self.item_a_title, "source": self.item_a_source},
            "item_b": {"id": self.item_b_id, "title": self.item_b_title, "source": self.item_b_source},
            "detail": self.detail,
            "confidence": self.confidence,
            "group_key": self.group_key,
            **self.extra,
        }


# ---------------------------------------------------------------------------
# Helper: normalize evidence items
# ---------------------------------------------------------------------------

def _norm(item: Any) -> Dict[str, Any]:
    """Accept ORM object or dict; return plain dict with safe defaults."""
    if isinstance(item, dict):
        return item
    out: Dict[str, Any] = {}
    for attr in (
        "id", "title", "source_name", "source_family",
        "confidence", "contradiction_state", "contradiction_type",
        "normalized_entity_id", "entities", "metadata_json",
        "retrieved_at", "indian_population_relevant",
    ):
        out[attr] = getattr(item, attr, None)
    return out


def _entity_keys(item: Dict[str, Any]) -> List[str]:
    """Extract entity identifiers from evidence item dict."""
    keys: List[str] = []
    ents = item.get("entities") or []
    if isinstance(ents, list):
        for e in ents:
            if isinstance(e, dict) and e.get("symbol"):
                keys.append(e["symbol"].upper())
            elif isinstance(e, str):
                keys.append(e.upper())
    if item.get("normalized_entity_id"):
        keys.append(str(item["normalized_entity_id"]).upper())
    return keys


def _item_key(a: Dict[str, Any], b: Dict[str, Any]) -> str:
    """Stable pair key (sorted IDs)."""
    ids = sorted([str(a.get("id", "")), str(b.get("id", ""))])
    return f"{ids[0]}:{ids[1]}"


# ---------------------------------------------------------------------------
# Directional patterns — up/down, inhibits/activates
# ---------------------------------------------------------------------------

_UP_PATS = re.compile(
    r"\b(activates?|activating|activation|agonist|upregulat|up-regulat|overexpress|increases?|promotes?|"
    r"stimulates?|induces?|enhances?|potentiat|positive\s+regul)\b", re.I
)
_DOWN_PATS = re.compile(
    r"\b(inhibits?|inhibitor|inhibiting|inhibition|antagonist|downregulat|down-regulat|underexpress|"
    r"decreases?|suppresses?|blocks?|silences?|represses?|negative\s+regul)\b", re.I
)


def _directionality(text: str) -> str:
    up = bool(_UP_PATS.search(text or ""))
    down = bool(_DOWN_PATS.search(text or ""))
    if up and not down:
        return "up"
    if down and not up:
        return "down"
    return "unknown"


def detect_directional(
    evidence_items: Sequence[Any],
) -> List[ContradictionResult]:
    """Detect directional contradictions (up vs down regulation).

    Groups items by shared entity key; within each group finds pairs where one
    claims up-regulation and the other down-regulation on the same entity.
    """
    from collections import defaultdict

    items = [_norm(i) for i in evidence_items]
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in items:
        for k in _entity_keys(item) or ["__unkeyed__"]:
            groups[k].append(item)

    results: List[ContradictionResult] = []
    seen: set = set()

    for gkey, group in groups.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                pk = _item_key(a, b)
                if pk in seen:
                    continue
                ta = _directionality(str(a.get("title", "")))
                tb = _directionality(str(b.get("title", "")))
                if ta != "unknown" and tb != "unknown" and ta != tb:
                    seen.add(pk)
                    results.append(ContradictionResult(
                        id=f"directional:{pk}",
                        contradiction_type="directional",
                        item_a_id=str(a.get("id", "")),
                        item_b_id=str(b.get("id", "")),
                        item_a_title=str(a.get("title", ""))[:120],
                        item_b_title=str(b.get("title", ""))[:120],
                        item_a_source=str(a.get("source_name", "")),
                        item_b_source=str(b.get("source_name", "")),
                        detail=(
                            f"Directional conflict for '{gkey}': "
                            f"source A signals {ta}-regulation, source B signals {tb}-regulation."
                        ),
                        confidence=0.8,
                        group_key=gkey,
                    ))
    log.debug("detect_directional_done", count=len(results))
    return results


# ---------------------------------------------------------------------------
# Temporal contradictions — reversal >5 yr apart
# ---------------------------------------------------------------------------

_YEAR_THRESHOLD = 5

def _extract_year(item: Dict[str, Any]) -> Optional[int]:
    meta = item.get("metadata_json") or {}
    if isinstance(meta, dict):
        for key in ("pub_year", "year", "publication_year", "year_published"):
            v = meta.get(key)
            if v:
                try:
                    return int(str(v)[:4])
                except ValueError:
                    pass
    ra = item.get("retrieved_at")
    if ra:
        try:
            if isinstance(ra, str):
                return datetime.fromisoformat(ra).year
            if hasattr(ra, "year"):
                return ra.year
        except Exception:
            pass
    return None


def detect_temporal(
    evidence_items: Sequence[Any],
    threshold_years: int = _YEAR_THRESHOLD,
) -> List[ContradictionResult]:
    """Detect temporal contradictions: same entity, opposing direction, >threshold years apart."""
    from collections import defaultdict

    items = [_norm(i) for i in evidence_items]
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in items:
        for k in _entity_keys(item) or ["__unkeyed__"]:
            groups[k].append(item)

    results: List[ContradictionResult] = []
    seen: set = set()

    for gkey, group in groups.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                pk = _item_key(a, b)
                if pk in seen:
                    continue
                yr_a = _extract_year(a)
                yr_b = _extract_year(b)
                if yr_a is None or yr_b is None:
                    continue
                if abs(yr_a - yr_b) < threshold_years:
                    continue
                ta = _directionality(str(a.get("title", "")))
                tb = _directionality(str(b.get("title", "")))
                if ta != "unknown" and tb != "unknown" and ta != tb:
                    seen.add(pk)
                    results.append(ContradictionResult(
                        id=f"temporal:{pk}",
                        contradiction_type="temporal",
                        item_a_id=str(a.get("id", "")),
                        item_b_id=str(b.get("id", "")),
                        item_a_title=str(a.get("title", ""))[:120],
                        item_b_title=str(b.get("title", ""))[:120],
                        item_a_source=str(a.get("source_name", "")),
                        item_b_source=str(b.get("source_name", "")),
                        detail=(
                            f"Temporal reversal for '{gkey}': "
                            f"{yr_a} study ({ta}) vs {yr_b} study ({tb}) — "
                            f"{abs(yr_a - yr_b)} yr gap exceeds {threshold_years} yr threshold."
                        ),
                        confidence=0.75,
                        group_key=gkey,
                        extra={"year_a": yr_a, "year_b": yr_b, "year_gap": abs(yr_a - yr_b)},
                    ))
    log.debug("detect_temporal_done", count=len(results))
    return results


# ---------------------------------------------------------------------------
# Score divergence — std(confidence) > threshold
# ---------------------------------------------------------------------------

def detect_score_divergence(
    evidence_items: Sequence[Any],
    threshold: float = 0.3,
) -> List[ContradictionResult]:
    """Detect score divergence: items in same entity group with high std(confidence)."""
    from collections import defaultdict

    items = [_norm(i) for i in evidence_items]
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in items:
        for k in _entity_keys(item) or ["__unkeyed__"]:
            groups[k].append(item)

    results: List[ContradictionResult] = []
    seen: set = set()

    for gkey, group in groups.items():
        scored = [(i, float(i.get("confidence") or 0)) for i in group if i.get("confidence") is not None]
        if len(scored) < 2:
            continue
        scores = [s for _, s in scored]
        try:
            sd = stdev(scores)
        except Exception:
            continue
        if sd < threshold:
            continue
        # Report the pair with maximum score difference
        scored.sort(key=lambda x: x[1])
        a, _ = scored[0]
        b, _ = scored[-1]
        pk = _item_key(a, b)
        if pk in seen:
            continue
        seen.add(pk)
        results.append(ContradictionResult(
            id=f"score_divergence:{pk}",
            contradiction_type="score_divergence",
            item_a_id=str(a.get("id", "")),
            item_b_id=str(b.get("id", "")),
            item_a_title=str(a.get("title", ""))[:120],
            item_b_title=str(b.get("title", ""))[:120],
            item_a_source=str(a.get("source_name", "")),
            item_b_source=str(b.get("source_name", "")),
            detail=(
                f"Score divergence for '{gkey}': group std={sd:.3f} (threshold {threshold}). "
                f"Confidence range: [{min(scores):.2f}, {max(scores):.2f}]."
            ),
            confidence=min(0.9, sd),
            group_key=gkey,
            extra={"std": round(sd, 4), "n_items": len(scored), "score_min": min(scores), "score_max": max(scores)},
        ))
    log.debug("detect_score_divergence_done", count=len(results))
    return results


# ---------------------------------------------------------------------------
# Methodological — in-vitro vs clinical mismatch
# ---------------------------------------------------------------------------

_METHOD_TYPES: Dict[str, re.Pattern] = {
    "case_study":    re.compile(r"\b(case\s+(study|report)|single\s+patient|case\s+series)\b", re.I),
    "rct":           re.compile(r"\b(randomized|randomised|RCT|double.blind|placebo.controlled|phase\s+[23])\b", re.I),
    "meta_analysis": re.compile(r"\b(meta.analysis|systematic\s+review|pooled)\b", re.I),
    "in_vitro":      re.compile(r"\b(in\s*vitro|cell\s+line|cell\s+culture|HEK|HeLa)\b", re.I),
    "in_vivo":       re.compile(r"\b(in\s*vivo|animal\s+model|mouse|murine|rat\s+model)\b", re.I),
    "clinical":      re.compile(r"\b(clinical\s+trial|cohort|patient|human\s+subject)\b", re.I),
}

# Pairs that are methodologically contradictory
_METHODOLOGICAL_CONFLICTS: List[Tuple[str, str]] = [
    ("in_vitro", "clinical"),
    ("in_vitro", "rct"),
    ("case_study", "rct"),
    ("case_study", "meta_analysis"),
    ("in_vivo", "clinical"),
]


def _method_type(text: str) -> str:
    for mtype, pat in _METHOD_TYPES.items():
        if pat.search(text or ""):
            return mtype
    return "unknown"


def detect_methodological(
    evidence_items: Sequence[Any],
) -> List[ContradictionResult]:
    """Detect methodological mismatches (in-vitro vs clinical, case-study vs RCT, etc.)."""
    from collections import defaultdict

    items = [_norm(i) for i in evidence_items]
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in items:
        for k in _entity_keys(item) or ["__unkeyed__"]:
            groups[k].append(item)

    conflict_set = {(a, b) for a, b in _METHODOLOGICAL_CONFLICTS} | {(b, a) for a, b in _METHODOLOGICAL_CONFLICTS}

    results: List[ContradictionResult] = []
    seen: set = set()

    for gkey, group in groups.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                pk = _item_key(a, b)
                if pk in seen:
                    continue
                ma = _method_type(str(a.get("title", "")))
                mb = _method_type(str(b.get("title", "")))
                if (ma, mb) in conflict_set:
                    seen.add(pk)
                    results.append(ContradictionResult(
                        id=f"methodological:{pk}",
                        contradiction_type="methodological",
                        item_a_id=str(a.get("id", "")),
                        item_b_id=str(b.get("id", "")),
                        item_a_title=str(a.get("title", ""))[:120],
                        item_b_title=str(b.get("title", ""))[:120],
                        item_a_source=str(a.get("source_name", "")),
                        item_b_source=str(b.get("source_name", "")),
                        detail=(
                            f"Methodological conflict for '{gkey}': "
                            f"source A is {ma}, source B is {mb} — "
                            "translational gap may explain discordance."
                        ),
                        confidence=0.65,
                        group_key=gkey,
                        extra={"method_a": ma, "method_b": mb},
                    ))
    log.debug("detect_methodological_done", count=len(results))
    return results


# ---------------------------------------------------------------------------
# Population — ethnicity / Indian-specific conflicts
# ---------------------------------------------------------------------------

_INDIAN_PAT = re.compile(
    r"\b(indian|india|south\s+asian|desi|hindi|punjabi|bengali|tamil|telugu|"
    r"gujarati|marathi|kannada|indo.aryan|dravidian|CTRI|IndiGen|GenomeAsia)\b", re.I
)
_NON_INDIAN_POP_PAT = re.compile(
    r"\b(european|caucasian|white|african|east\s+asian|hispanic|latino|CEU|YRI|CHB|JPT|"
    r"1000\s+Genomes|gnomAD)\b", re.I
)


def detect_population(
    evidence_items: Sequence[Any],
) -> List[ContradictionResult]:
    """Detect population-specific contradictions — Indian vs non-Indian cohort conflicts."""
    from collections import defaultdict

    items = [_norm(i) for i in evidence_items]
    groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for item in items:
        for k in _entity_keys(item) or ["__unkeyed__"]:
            groups[k].append(item)

    results: List[ContradictionResult] = []
    seen: set = set()

    for gkey, group in groups.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                a, b = group[i], group[j]
                pk = _item_key(a, b)
                if pk in seen:
                    continue

                a_title = str(a.get("title", ""))
                b_title = str(b.get("title", ""))
                a_indian = bool(_INDIAN_PAT.search(a_title)) or bool(a.get("indian_population_relevant"))
                b_indian = bool(_INDIAN_PAT.search(b_title)) or bool(b.get("indian_population_relevant"))
                a_non_indian = bool(_NON_INDIAN_POP_PAT.search(a_title))
                b_non_indian = bool(_NON_INDIAN_POP_PAT.search(b_title))

                # Conflict: one item is Indian-specific, the other is from a non-Indian cohort
                # AND they have opposing directionality
                pop_conflict = (a_indian and b_non_indian) or (b_indian and a_non_indian)
                if not pop_conflict:
                    continue

                ta = _directionality(a_title)
                tb = _directionality(b_title)
                if ta == "unknown" or tb == "unknown" or ta == tb:
                    # Even without opposing direction, flag population-specific vs general mismatch
                    if not pop_conflict:
                        continue

                seen.add(pk)
                pop_a = "Indian-specific" if a_indian else "non-Indian cohort"
                pop_b = "Indian-specific" if b_indian else "non-Indian cohort"
                results.append(ContradictionResult(
                    id=f"population:{pk}",
                    contradiction_type="population",
                    item_a_id=str(a.get("id", "")),
                    item_b_id=str(b.get("id", "")),
                    item_a_title=a_title[:120],
                    item_b_title=b_title[:120],
                    item_a_source=str(a.get("source_name", "")),
                    item_b_source=str(b.get("source_name", "")),
                    detail=(
                        f"Population conflict for '{gkey}': "
                        f"source A ({pop_a}) vs source B ({pop_b}). "
                        "Results may not generalise across ethnic groups."
                    ),
                    confidence=0.7,
                    group_key=gkey,
                    extra={"pop_a": pop_a, "pop_b": pop_b},
                ))
    log.debug("detect_population_done", count=len(results))
    return results


# ---------------------------------------------------------------------------
# run_all — convenience aggregator
# ---------------------------------------------------------------------------

def run_all(
    evidence_items: Sequence[Any],
    *,
    score_divergence_threshold: float = 0.3,
    temporal_years: int = _YEAR_THRESHOLD,
) -> List[ContradictionResult]:
    """Run all five detectors and deduplicate by (item_a_id, item_b_id) pair.

    Returns a combined list sorted by confidence descending.
    """
    all_results: List[ContradictionResult] = []
    all_results.extend(detect_directional(evidence_items))
    all_results.extend(detect_temporal(evidence_items, threshold_years=temporal_years))
    all_results.extend(detect_score_divergence(evidence_items, threshold=score_divergence_threshold))
    all_results.extend(detect_methodological(evidence_items))
    all_results.extend(detect_population(evidence_items))

    # Deduplicate: keep first occurrence for each (item_a_id, item_b_id) regardless of type
    seen_pairs: set = set()
    deduped: List[ContradictionResult] = []
    for r in all_results:
        pair = tuple(sorted([r.item_a_id, r.item_b_id]))
        if pair not in seen_pairs:
            seen_pairs.add(pair)
            deduped.append(r)

    deduped.sort(key=lambda r: r.confidence, reverse=True)
    log.info("contradiction_run_all_done", total=len(all_results), after_dedup=len(deduped))
    return deduped

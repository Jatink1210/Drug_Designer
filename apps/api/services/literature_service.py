"""Literature-focused analysis service.

Orchestrates deep literature retrieval from multiple sources (PubMed, Europe PMC,
Semantic Scholar, OpenAlex, CrossRef, Patents), full-text processing, term frequency
analysis, and literature-specific enrichments (contradictions with experimental
context, similarities, nuanced relationships, term maps).

Flow: Query → Multi-source fetch → Deduplicate → Sort by relevance →
      Term extraction → Contradiction/Similarity analysis → KG construction →
      Sentence tokenization → Evidence linking (bidirectional traceability)
"""

from __future__ import annotations

import asyncio
import re
import time
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Tuple

import structlog

log = structlog.get_logger(__name__)

# ── Term extraction patterns ────────────────────────────────

_GENE_PAT = re.compile(r"\b([A-Z][A-Z0-9]{1,9})\b")
_SMILES_PAT = re.compile(r"(?<![a-zA-Z])([CNOSPFBrClI][a-zA-Z0-9@+\-\[\]\(\)=#/\\.,:]{8,})")
_DOI_PAT = re.compile(r"10\.\d{4,}/[^\s]+")

# Experimental context keywords
_CONTEXT_MARKERS = {
    "in_vivo": re.compile(r"\b(in\s*vivo|animal\s+model|mouse|mice|rat|murine|primate|rabbit|zebrafish)\b", re.I),
    "in_vitro": re.compile(r"\b(in\s*vitro|cell\s+line|cell\s+culture|HEK293|HeLa|MCF-?7|A549|Jurkat)\b", re.I),
    "in_silico": re.compile(r"\b(in\s*silico|computational|molecular\s+docking|simulation|bioinformatics)\b", re.I),
    "clinical": re.compile(r"\b(clinical\s+trial|patient|cohort|randomized|phase\s+[I1-4]|double.blind|placebo)\b", re.I),
    "meta_analysis": re.compile(r"\b(meta.analysis|systematic\s+review|pooled\s+analysis)\b", re.I),
}

# Methodology extraction
_METHODOLOGY_PAT = re.compile(
    r"\b(western\s+blot|PCR|qPCR|RT-PCR|ELISA|mass\s+spec|NMR|X-ray|cryo-EM|"
    r"RNA-seq|ChIP-seq|CRISPR|siRNA|shRNA|flow\s+cytometry|immunohistochemistry|"
    r"IHC|confocal|microscopy|SPR|BLI|IC50|EC50|Ki\b|Kd\b)\b",
    re.I,
)

# Nuanced relationship keywords (broadened for real-world abstracts)
_REFINES_PAT = re.compile(
    r"\b(refines?|extends?|builds?\s+(?:on|upon)|improves?\s+(?:on|upon)|further\s+(?:demonstrates?|characteriz|identif|elucidates?|investigat|analyz)|advancing|advances?|expands?\s+(?:on|upon|our)|contribut|corroborat|complement|validat|supports?\s+(?:previous|earlier|prior)|additional\s+evidence|consistent\s+with\s+(?:previous|prior))\b",
    re.I,
)
_FAILS_REPLICATE_PAT = re.compile(
    r"\b(fail(?:s|ed)?\s+to\s+(?:replicate|reproduce|confirm)|could\s+not\s+(?:reproduce|replicate|confirm)|non.replicable|contradict(?:s|ed|ing)?|inconsistent\s+with|contrary\s+to|challenge[sd]?\s+(?:the|previous)|opposes?|disputes?|conflicting)\b",
    re.I,
)
_USES_METHOD_PAT = re.compile(
    r"\b(using\s+(?:the\s+)?(?:same\s+)?method(?:ology)?|adapts?\s+(?:the\s+)?approach|(?:similar|same|identical)\s+(?:assay|protocol|technique|procedure|pipeline|workflow|analysis)|(?:CRISPR|RNA.?seq|ChIP.?seq|western\s+blot|mass\s+spec|immunohistochem|qPCR|flow\s+cytometry|whole.?exome|whole.?genome))\b",
    re.I,
)
_EXPANDS_PAT = re.compile(
    r"\b(expands?\s+(?:to|upon)|generaliz(?:e|es)|novel\s+(?:model|approach|application|strategy|mechanism|pathway|target|therapy|inhibitor)|first\s+(?:time|report|demonstration|evidence)|new\s+(?:mechanism|insight|finding|model|target)|previously\s+(?:unknown|uncharacterized|unreported))\b",
    re.I,
)


def _extract_experimental_context(text: str) -> Dict[str, Any]:
    """Extract experimental context from text — model system, methodology, organism."""
    context: Dict[str, Any] = {
        "model_systems": [],
        "methodologies": [],
        "study_type": "unknown",
    }
    for stype, pat in _CONTEXT_MARKERS.items():
        if pat.search(text):
            context["study_type"] = stype
            matches = pat.findall(text)
            context["model_systems"].extend(matches[:3])
            break

    methods = _METHODOLOGY_PAT.findall(text)
    context["methodologies"] = list(set(m.strip() for m in methods))[:5]
    return context


def _compute_term_frequency(papers: List[Dict[str, Any]], query_terms: List[str]) -> Dict[str, int]:
    """Count term frequency across all paper texts → sort by relevance."""
    freq: Counter = Counter()
    for paper in papers:
        text = " ".join(filter(None, [
            paper.get("title", ""),
            paper.get("abstract", ""),
            paper.get("snippet", ""),
        ])).lower()
        for term in query_terms:
            count = text.count(term.lower())
            if count > 0:
                freq[term] += count
    return dict(freq.most_common(100))


def _deduplicate_papers(papers: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Deduplicate papers by DOI or PMID or title similarity."""
    seen_ids: set = set()
    seen_titles: set = set()
    unique: List[Dict[str, Any]] = []

    for p in papers:
        doi = (p.get("doi") or "").strip().lower()
        pmid = str(p.get("pmid") or "").strip()
        title_norm = re.sub(r"\s+", " ", (p.get("title") or "").lower().strip())

        # Skip if already seen
        if doi and doi in seen_ids:
            continue
        if pmid and pmid != "" and pmid in seen_ids:
            continue
        if title_norm and title_norm in seen_titles:
            continue

        if doi:
            seen_ids.add(doi)
        if pmid:
            seen_ids.add(pmid)
        if title_norm:
            seen_titles.add(title_norm)
        unique.append(p)

    return unique


def _relevance_score(paper: Dict[str, Any], query_terms: List[str]) -> float:
    """Compute relevance score for sorting: term frequency + citation count + recency."""
    text = " ".join(filter(None, [
        paper.get("title", ""),
        paper.get("abstract", ""),
        paper.get("snippet", ""),
    ])).lower()

    # Term frequency component
    term_hits = sum(1 for t in query_terms if t.lower() in text)
    term_score = term_hits / max(len(query_terms), 1)

    # Citation component (log scale)
    import math
    citations = paper.get("citation_count", 0) or 0
    cite_score = min(math.log10(citations + 1) / 4, 1.0)

    # Recency component
    year = paper.get("year") or 2000
    recency = min(max(year - 2015, 0) / 11, 1.0)  # 2015-2026 → 0-1

    return term_score * 0.5 + cite_score * 0.3 + recency * 0.2


async def fetch_literature(
    query: str,
    keywords: List[str],
    limit: int = 100,
) -> Dict[str, Any]:
    """Fetch literature from all available sources in parallel.

    Returns:
        {
            "papers": [...],           # Deduplicated, sorted by relevance
            "total_fetched": int,
            "sources_queried": [...],
            "term_frequency": {...},
            "fetch_timings": {...},
        }
    """
    from connectors.pubmed import PubMedConnector
    from connectors.europe_pmc import EuropePMCConnector
    from connectors.semantic_scholar import SemanticScholarConnector
    from connectors.openalex import OpenAlexConnector
    from connectors.crossref import CrossRefConnector

    connectors = [
        ("PubMed", PubMedConnector()),
        ("EuropePMC", EuropePMCConnector()),
        ("SemanticScholar", SemanticScholarConnector()),
        ("OpenAlex", OpenAlexConnector()),
        ("CrossRef", CrossRefConnector()),
    ]

    per_source = max(limit // len(connectors), 20)
    timings: Dict[str, float] = {}
    sources_queried: List[str] = []

    async def _fetch_one(name: str, conn, q: str, lim: int):
        t0 = time.time()
        try:
            results = await conn.search(q, limit=lim)
            timings[name] = round((time.time() - t0) * 1000, 1)
            sources_queried.append(name)
            return results or []
        except Exception as ex:
            timings[name] = round((time.time() - t0) * 1000, 1)
            log.warning("literature_fetch_failed", connector_name=name, err_msg=str(ex)[:200])
            return []

    # Parallel fetch from all sources
    tasks = [_fetch_one(name, conn, query, per_source) for name, conn in connectors]

    # Also search with individual keywords for broader coverage
    if keywords:
        kw_query = " OR ".join(keywords[:5])
        tasks.append(_fetch_one("PubMed_KW", PubMedConnector(), kw_query, per_source))

    results = await asyncio.gather(*tasks)
    all_papers = []
    for batch in results:
        all_papers.extend(batch)

    # Deduplicate
    unique = _deduplicate_papers(all_papers)

    # ── Full-text retrieval for open-access papers (PageIndex concept) ──
    # Read every paper fully when possible — use Europe PMC fulltext API
    try:
        from connectors.europe_pmc import EuropePMCConnector
        epmc = EuropePMCConnector()
        fulltext_tasks = []
        ft_paper_indices = []
        for idx, paper in enumerate(unique[:50]):
            pmc_id = paper.get("pmc_id") or paper.get("pmcid") or ""
            is_oa = paper.get("is_open_access", False)
            # Try full text for papers w/ PMC ID or OA flag
            if pmc_id or is_oa:
                pmcid = pmc_id if pmc_id else f"PMC{paper.get('pmid', '')}"
                if pmcid and pmcid.startswith("PMC"):
                    fulltext_tasks.append(epmc.fetch_fulltext(pmcid))
                    ft_paper_indices.append(idx)
        if fulltext_tasks:
            ft_results = await asyncio.gather(*fulltext_tasks, return_exceptions=True)
            for i, ft_text in enumerate(ft_results):
                if isinstance(ft_text, str) and ft_text and len(ft_text) > 200:
                    pidx = ft_paper_indices[i]
                    unique[pidx]["full_text"] = ft_text[:50000]  # Cap at 50k chars
                    # Use full text for better abstract if current one is short
                    current_abs = unique[pidx].get("abstract", "")
                    if len(current_abs) < 300 and len(ft_text) > 300:
                        # Extract first meaningful paragraph as enhanced abstract
                        paras = [p for p in ft_text.split("\n") if len(p) > 100]
                        if paras:
                            unique[pidx]["abstract"] = paras[0][:2000]
            log.info("fulltext_fetched", attempted=len(fulltext_tasks),
                     succeeded=sum(1 for r in ft_results if isinstance(r, str) and r))
    except Exception as exc:
        log.debug("fulltext_enrichment_skipped", error=str(exc)[:200])

    # Enrich: add experimental context + relevance score
    search_terms = [t.lower() for t in ([query] + keywords)]
    for paper in unique:
        text = " ".join(filter(None, [
            paper.get("title", ""),
            paper.get("abstract", ""),
            paper.get("snippet", ""),
        ]))
        paper["_experimental_context"] = _extract_experimental_context(text)
        paper["_relevance_score"] = _relevance_score(paper, search_terms)

        # Ensure DOI URL if present
        doi = paper.get("doi", "")
        if doi and not paper.get("doi_url"):
            clean = doi.replace("https://doi.org/", "").strip()
            if clean:
                paper["doi_url"] = f"https://doi.org/{clean}"

    # Sort by relevance
    unique.sort(key=lambda p: p.get("_relevance_score", 0), reverse=True)

    # Term frequency analysis
    term_freq = _compute_term_frequency(unique, keywords + query.split())

    return {
        "papers": unique[:limit],
        "total_fetched": len(all_papers),
        "total_unique": len(unique),
        "sources_queried": list(set(sources_queried)),
        "term_frequency": term_freq,
        "fetch_timings": timings,
    }


def build_literature_table(
    papers: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build standardized literature table rows."""
    rows = []
    for i, p in enumerate(papers):
        authors = p.get("authors", [])
        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."

        doi = p.get("doi", "")
        doi_url = p.get("doi_url", "")
        if not doi_url and doi:
            doi_url = f"https://doi.org/{doi.replace('https://doi.org/', '')}"

        rows.append({
            "sno": i + 1,
            "id": p.get("id", ""),
            "doi": doi,
            "doi_url": doi_url,
            "title": p.get("title", ""),
            "authors": author_str,
            "year": p.get("year"),
            "journal": p.get("journal", ""),
            "summary": p.get("abstract", p.get("snippet", ""))[:300],
            "citation_count": p.get("citation_count", 0),
            "relevance_score": round(p.get("_relevance_score", 0), 3),
            "source": p.get("provenance", [{}])[0].get("source", "") if p.get("provenance") else "",
            "pmid": p.get("pmid", ""),
            "url": p.get("url", "") or doi_url,
            "methodology_context": p.get("_experimental_context", {}).get("study_type", "unknown"),
        })
    return rows


def build_filtered_table(
    papers: List[Dict[str, Any]],
    filter_terms: List[str],
    filter_type: str = "keyword",
) -> List[Dict[str, Any]]:
    """Build filtered literature table for user-specified data (GWAS, mechanisms, etc.)."""
    filtered = []
    for p in papers:
        text = " ".join(filter(None, [
            p.get("title", ""),
            p.get("abstract", ""),
            p.get("snippet", ""),
        ])).lower()

        matched_terms = [t for t in filter_terms if t.lower() in text]
        if not matched_terms:
            continue

        authors = p.get("authors", [])
        author_str = ", ".join(authors[:3])
        if len(authors) > 3:
            author_str += " et al."

        # Extract specific data mentioned
        specific_data = []
        for term in matched_terms:
            # Find sentence containing term
            sentences = re.split(r'[.!?]', text)
            for s in sentences:
                if term.lower() in s.lower():
                    specific_data.append(s.strip()[:200])
                    break

        filtered.append({
            "sno": len(filtered) + 1,
            "id": p.get("id", ""),
            "doi": p.get("doi", ""),
            "title": p.get("title", ""),
            "authors": author_str,
            "year": p.get("year"),
            "summary": p.get("abstract", p.get("snippet", ""))[:200],
            "specific_data": "; ".join(specific_data[:3]) if specific_data else "—",
            "matched_terms": matched_terms,
            "filter_type": filter_type,
            "url": p.get("url", ""),
            "pmid": p.get("pmid", ""),
        })

    return filtered


def extract_terms_map(
    papers: List[Dict[str, Any]],
    query: str,
) -> Dict[str, Any]:
    """Extract a comprehensive terms map from all papers.

    Returns genes, drugs, diseases, pathways, methods with frequency counts.
    """
    gene_counts: Counter = Counter()
    drug_counts: Counter = Counter()
    disease_counts: Counter = Counter()
    method_counts: Counter = Counter()
    all_terms: Counter = Counter()

    # Known disease terms
    _DISEASE_TERMS = re.compile(
        r"\b(cancer|carcinoma|tumor|diabetes|alzheimer|parkinson|hypertension|"
        r"asthma|arthritis|leukemia|lymphoma|melanoma|glioblastoma|fibrosis|"
        r"cirrhosis|hepatitis|influenza|tuberculosis|malaria|HIV|COVID|SARS|"
        r"obesity|stroke|epilepsy|schizophrenia|depression|anxiety|COPD|"
        r"pneumonia|sepsis|anemia|thrombosis|atherosclerosis)\b", re.I
    )

    _DRUG_TERMS = re.compile(
        r"\b(\w+(?:mab|nib|lib|sib|rib|vir|tide|statin|pril|sartan|olol|pine|"
        r"mycin|cycline|azole|fenac|profen|amide|etine|oxib|axel|imus|platin|"
        r"taxel|rubicin|mustine|sulam|ximab|zumab|lumab|tinib|rafenib|ciclib|"
        r"lisib|parib|lectinib|nertinib|ratinib))\b", re.I
    )

    # Known drug names that don't match suffix patterns
    _KNOWN_DRUGS = {
        "tamoxifen", "doxorubicin", "methotrexate", "cisplatin", "carboplatin",
        "paclitaxel", "docetaxel", "gemcitabine", "capecitabine", "fluorouracil",
        "cyclophosphamide", "etoposide", "vincristine", "bevacizumab", "trastuzumab",
        "pertuzumab", "olaparib", "rucaparib", "niraparib", "talazoparib",
        "palbociclib", "ribociclib", "abemaciclib", "alpelisib", "everolimus",
        "exemestane", "letrozole", "anastrozole", "fulvestrant", "megestrol",
        "toremifene", "raloxifene", "sorafenib", "sunitinib", "imatinib",
        "erlotinib", "gefitinib", "lapatinib", "neratinib", "tucatinib",
        "sacituzumab", "pembrolizumab", "atezolizumab", "nivolumab", "ipilimumab",
        "metformin", "aspirin", "celecoxib", "rituximab", "bortezomib",
        "lenalidomide", "thalidomide", "ibrutinib", "venetoclax", "acalabrutinib",
    }
    _KNOWN_DRUGS_PAT = re.compile(
        r"\b(" + "|".join(re.escape(d) for d in _KNOWN_DRUGS) + r")\b", re.I
    )

    for p in papers:
        text = " ".join(filter(None, [
            p.get("title", ""),
            p.get("abstract", ""),
            p.get("snippet", ""),
        ]))

        # Gene symbols
        genes = _GENE_PAT.findall(text)
        for g in genes:
            if len(g) >= 2 and g not in ("AND", "THE", "FOR", "NOT", "BUT", "WITH", "FROM", "THIS", "THAT", "HAVE", "BEEN"):
                gene_counts[g] += 1

        # Disease terms
        diseases = _DISEASE_TERMS.findall(text)
        for d in diseases:
            disease_counts[d.lower()] += 1

        # Drug names (suffix patterns)
        drugs = _DRUG_TERMS.findall(text)
        for dr in drugs:
            drug_counts[dr.lower()] += 1

        # Drug names (known names)
        known_drugs = _KNOWN_DRUGS_PAT.findall(text)
        for dr in known_drugs:
            drug_counts[dr.lower()] += 1

        # Methods
        methods = _METHODOLOGY_PAT.findall(text)
        for m in methods:
            method_counts[m.lower().strip()] += 1

        # All significant terms (>3 chars, alphanumeric)
        words = re.findall(r"\b[a-zA-Z]{4,}\b", text)
        for w in words:
            wl = w.lower()
            if wl not in ("this", "that", "with", "from", "have", "been", "were", "they",
                          "which", "their", "than", "also", "more", "most", "some", "other",
                          "into", "only", "each", "both", "such", "between", "through"):
                all_terms[wl] += 1

    return {
        "genes": dict(gene_counts.most_common(50)),
        "drugs": dict(drug_counts.most_common(30)),
        "diseases": dict(disease_counts.most_common(20)),
        "methods": dict(method_counts.most_common(20)),
        "top_terms": dict(all_terms.most_common(100)),
        "total_papers_analyzed": len(papers),
    }


def detect_similarities(
    papers: List[Dict[str, Any]],
    threshold: float = 0.4,
) -> List[Dict[str, Any]]:
    """Detect paper similarities using term overlap (Jaccard-like).

    Groups papers that share significant findings/terminology.
    """
    similarities: List[Dict[str, Any]] = []

    def _tokenize(text: str) -> set:
        words = set(re.findall(r"\b[a-zA-Z]{3,}\b", text.lower()))
        # Remove common stop words
        stops = {"the", "and", "for", "are", "but", "not", "you", "all", "can",
                 "had", "her", "was", "one", "our", "out", "has", "its", "this",
                 "that", "with", "from", "have", "been", "were", "they", "which",
                 "their", "than", "also", "more", "most", "some", "other", "into",
                 "only", "each", "both", "such", "about", "these", "would", "could",
                 "should", "between", "through", "after", "before", "during"}
        return words - stops

    # Pre-tokenize
    paper_tokens = []
    for p in papers[:50]:  # Cap at 50 to avoid O(n²) explosion
        text = " ".join(filter(None, [
            p.get("title", ""),
            p.get("abstract", ""),
            p.get("snippet", ""),
            p.get("summary", ""),
        ]))
        paper_tokens.append(_tokenize(text))

    for i in range(len(paper_tokens)):
        for j in range(i + 1, len(paper_tokens)):
            if not paper_tokens[i] or not paper_tokens[j]:
                continue
            intersection = paper_tokens[i] & paper_tokens[j]
            union = paper_tokens[i] | paper_tokens[j]
            jaccard = len(intersection) / len(union) if union else 0

            if jaccard >= threshold:
                shared = sorted(intersection - {"study", "results", "analysis", "method",
                                                "found", "using", "based", "showed", "significant"})
                similarities.append({
                    "paper_a": {
                        "title": papers[i].get("title", ""),
                        "id": papers[i].get("id", ""),
                        "year": papers[i].get("year"),
                        "authors": papers[i].get("authors", [])[:3],
                    },
                    "paper_b": {
                        "title": papers[j].get("title", ""),
                        "id": papers[j].get("id", ""),
                        "year": papers[j].get("year"),
                        "authors": papers[j].get("authors", [])[:3],
                    },
                    "similarity_score": round(jaccard, 3),
                    "shared_terms": shared[:15],
                    "relationship_type": "similar",
                })

    # Sort by similarity (highest first), cap at 30
    similarities.sort(key=lambda s: s["similarity_score"], reverse=True)
    return similarities[:30]


def detect_nuanced_relationships(
    papers: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Detect nuanced relationships: Refines, Fails to Replicate, Uses Methodology From, Expands."""
    relationships: List[Dict[str, Any]] = []

    for i, pa in enumerate(papers[:40]):
        text_a = " ".join(filter(None, [
            pa.get("title", ""),
            pa.get("abstract", ""),
            pa.get("snippet", ""),
            pa.get("summary", ""),
        ]))
        for j in range(i + 1, min(len(papers), 40)):
            pb = papers[j]
            text_b = " ".join(filter(None, [
                pb.get("title", ""),
                pb.get("abstract", ""),
                pb.get("snippet", ""),
                pb.get("summary", ""),
            ]))

            rel_type = None
            explanation = ""

            # Check: Fails to replicate
            if _FAILS_REPLICATE_PAT.search(text_a) or _FAILS_REPLICATE_PAT.search(text_b):
                # Check if they share topic
                a_genes = set(_GENE_PAT.findall(text_a))
                b_genes = set(_GENE_PAT.findall(text_b))
                if a_genes & b_genes:
                    rel_type = "fails_to_replicate"
                    explanation = f"Shared genes {', '.join(list(a_genes & b_genes)[:3])} with replication failure signal"

            # Check: Refines
            elif _REFINES_PAT.search(text_a) or _REFINES_PAT.search(text_b):
                a_genes = set(_GENE_PAT.findall(text_a))
                b_genes = set(_GENE_PAT.findall(text_b))
                if a_genes & b_genes:
                    rel_type = "refines"
                    explanation = f"Builds upon findings related to {', '.join(list(a_genes & b_genes)[:3])}"

            # Check: Expands to new model
            elif _EXPANDS_PAT.search(text_a) or _EXPANDS_PAT.search(text_b):
                ctx_a = _extract_experimental_context(text_a)
                ctx_b = _extract_experimental_context(text_b)
                if ctx_a["study_type"] != ctx_b["study_type"] and ctx_a["study_type"] != "unknown":
                    rel_type = "expands_to_new_model"
                    explanation = f"Paper A: {ctx_a['study_type']}, Paper B: {ctx_b['study_type']}"

            # Check: Uses methodology from
            elif _USES_METHOD_PAT.search(text_a) or _USES_METHOD_PAT.search(text_b):
                ctx_a = _extract_experimental_context(text_a)
                ctx_b = _extract_experimental_context(text_b)
                shared_methods = set(ctx_a.get("methodologies", [])) & set(ctx_b.get("methodologies", []))
                if shared_methods:
                    rel_type = "uses_methodology_from"
                    explanation = f"Shared methodology: {', '.join(list(shared_methods)[:3])}"

            # Fallback: shared genes + different study types → complementary evidence
            if not rel_type:
                a_genes = set(_GENE_PAT.findall(text_a))
                b_genes = set(_GENE_PAT.findall(text_b))
                shared_g = a_genes & b_genes
                if len(shared_g) >= 2:
                    ctx_a = _extract_experimental_context(text_a)
                    ctx_b = _extract_experimental_context(text_b)
                    if ctx_a["study_type"] != ctx_b["study_type"] and "unknown" not in (ctx_a["study_type"], ctx_b["study_type"]):
                        rel_type = "complementary_evidence"
                        explanation = f"Shared genes {', '.join(list(shared_g)[:3])} across {ctx_a['study_type']} vs {ctx_b['study_type']}"
                    elif len(shared_g) >= 3:
                        rel_type = "shared_topic"
                        explanation = f"Convergent research on {', '.join(list(shared_g)[:4])}"

            if rel_type:
                relationships.append({
                    "paper_a": {
                        "title": pa.get("title", ""),
                        "id": pa.get("id", ""),
                        "year": pa.get("year"),
                    },
                    "paper_b": {
                        "title": pb.get("title", ""),
                        "id": pb.get("id", ""),
                        "year": pb.get("year"),
                    },
                    "relationship_type": rel_type,
                    "explanation": explanation,
                    "icon": {
                        "refines": "🔬",
                        "fails_to_replicate": "❌",
                        "uses_methodology_from": "🧪",
                        "expands_to_new_model": "🌐",
                        "complementary_evidence": "🔄",
                        "shared_topic": "🧬",
                    }.get(rel_type, "🔗"),
                })

    return relationships[:20]


def build_literature_kg(
    papers: List[Dict[str, Any]],
    terms_map: Dict[str, Any],
    contradictions: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a Knowledge Graph from literature terms.

    Nodes: genes, drugs, diseases, methods — each category distinct color.
    Edges: co-occurrence in papers, contradiction links.
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    node_ids: set = set()

    # Node colors by category
    COLORS = {
        "gene": "#6366f1",
        "drug": "#e11d48",
        "disease": "#dc2626",
        "method": "#10b981",
        "pathway": "#0891b2",
        "paper": "#f59e0b",
    }

    # Add top gene nodes
    for gene, count in list(terms_map.get("genes", {}).items())[:20]:
        nid = f"gene:{gene}"
        if nid not in node_ids:
            nodes.append({
                "id": nid, "label": gene, "type": "gene",
                "color": COLORS["gene"], "size": min(count * 2, 30),
                "frequency": count,
            })
            node_ids.add(nid)

    # Add top disease nodes
    for disease, count in list(terms_map.get("diseases", {}).items())[:10]:
        nid = f"disease:{disease}"
        if nid not in node_ids:
            nodes.append({
                "id": nid, "label": disease.title(), "type": "disease",
                "color": COLORS["disease"], "size": min(count * 2, 30),
                "frequency": count,
            })
            node_ids.add(nid)

    # Add top drug nodes
    for drug, count in list(terms_map.get("drugs", {}).items())[:10]:
        nid = f"drug:{drug}"
        if nid not in node_ids:
            nodes.append({
                "id": nid, "label": drug.title(), "type": "drug",
                "color": COLORS["drug"], "size": min(count * 2, 30),
                "frequency": count,
            })
            node_ids.add(nid)

    # Add method nodes
    for method, count in list(terms_map.get("methods", {}).items())[:8]:
        nid = f"method:{method}"
        if nid not in node_ids:
            nodes.append({
                "id": nid, "label": method.upper(), "type": "method",
                "color": COLORS["method"], "size": min(count * 2, 20),
                "frequency": count,
            })
            node_ids.add(nid)

    # Build co-occurrence edges from papers
    edge_ids: set = set()
    for paper in papers[:30]:
        text = " ".join(filter(None, [
            paper.get("title", ""),
            paper.get("abstract", ""),
            paper.get("snippet", ""),
        ])).lower()

        paper_nodes = []
        for n in nodes:
            label_lower = n["label"].lower()
            if label_lower in text:
                paper_nodes.append(n["id"])

        # Create edges between all co-occurring nodes in this paper
        for a in range(len(paper_nodes)):
            for b in range(a + 1, len(paper_nodes)):
                eid = tuple(sorted([paper_nodes[a], paper_nodes[b]]))
                if eid not in edge_ids:
                    edge_ids.add(eid)
                    edges.append({
                        "source": paper_nodes[a],
                        "target": paper_nodes[b],
                        "type": "co_occurrence",
                        "weight": 1,
                        "paper_title": paper.get("title", "")[:100],
                    })
                else:
                    # Increment weight
                    for e in edges:
                        if (e["source"], e["target"]) == eid or (e["target"], e["source"]) == eid:
                            e["weight"] = e.get("weight", 1) + 1
                            break

    # Add contradiction edges
    for c in contradictions[:15]:
        src_a = c.get("source_a", {})
        src_b = c.get("source_b", {})
        title_a = src_a.get("title", "Unknown A")
        title_b = src_b.get("title", "Unknown B")
        nid_a = f"paper:{title_a[:30]}"
        nid_b = f"paper:{title_b[:30]}"

        if nid_a not in node_ids:
            nodes.append({
                "id": nid_a, "label": title_a[:40], "type": "paper",
                "color": COLORS["paper"], "size": 15,
            })
            node_ids.add(nid_a)
        if nid_b not in node_ids:
            nodes.append({
                "id": nid_b, "label": title_b[:40], "type": "paper",
                "color": COLORS["paper"], "size": 15,
            })
            node_ids.add(nid_b)

        edges.append({
            "source": nid_a, "target": nid_b,
            "type": "contradiction",
            "contradiction": True,
            "contradiction_state": "confirmed",
            "weight": 3,
            "explanation": c.get("explanation", ""),
        })

    return {
        "nodes": nodes,
        "edges": edges,
        "node_categories": COLORS,
    }


def extract_user_specified_terms(query: str) -> Dict[str, List[str]]:
    """Parse query to find user-specified filters (GWAS, mechanism, structure, etc.)."""
    q_lower = query.lower()
    specifics: Dict[str, List[str]] = {
        "filter_terms": [],
        "filter_type": "keyword",
        "data_requests": [],
    }

    # GWAS-specific
    if "gwas" in q_lower or "genome-wide" in q_lower:
        specifics["filter_terms"].extend(["gwas", "genome-wide association", "SNP", "variant", "locus"])
        specifics["filter_type"] = "gwas"

    # Mechanism-specific (includes "cluster by mechanism")
    if any(kw in q_lower for kw in ("mechanism", "pathway", "signaling", "cluster the evidence by mechanism",
                                     "cluster by mechanism", "molecular mechanism")):
        specifics["filter_terms"].extend(["mechanism", "pathway", "signaling", "cascade", "phosphorylation",
                                          "kinase", "receptor", "inhibition", "activation"])
        specifics["filter_type"] = "mechanism"

    # Structure-specific
    if "structure" in q_lower or "crystal" in q_lower or "binding" in q_lower:
        specifics["filter_terms"].extend(["structure", "crystal", "binding site", "pocket", "conformation"])
        specifics["filter_type"] = "structure"

    # Drug interaction
    if "drug interaction" in q_lower or "pharmacokin" in q_lower:
        specifics["filter_terms"].extend(["drug interaction", "pharmacokinetic", "metabolism", "CYP", "clearance"])
        specifics["filter_type"] = "pharmacology"

    # Biomarker
    if "biomarker" in q_lower or "diagnostic" in q_lower:
        specifics["filter_terms"].extend(["biomarker", "diagnostic", "prognostic", "sensitivity", "specificity"])
        specifics["filter_type"] = "biomarker"

    # Cohort / population emphasis
    cohort_patterns = {
        "indian": ["Indian cohort", "India", "Indian population", "South Asian"],
        "south asian": ["South Asian", "Indian subcontinent", "Bangladesh", "Pakistan", "Sri Lanka"],
        "east asian": ["East Asian", "Chinese", "Japanese", "Korean", "Han Chinese"],
        "european": ["European", "Caucasian", "Western population", "UK Biobank"],
        "global": ["global cohort", "multi-ethnic", "diverse population", "worldwide"],
        "mixed": ["mixed cohort", "multi-ethnic", "diverse ancestry"],
        "african": ["African", "African American", "Sub-Saharan"],
    }
    for cohort_key, cohort_terms in cohort_patterns.items():
        if cohort_key in q_lower or f"emphasis on {cohort_key}" in q_lower:
            specifics["filter_terms"].extend(cohort_terms)
            if specifics["filter_type"] == "keyword":
                specifics["filter_type"] = f"cohort:{cohort_key}"

    # Contradiction / dissenting evidence
    if any(kw in q_lower for kw in ("contradiction", "dissenting", "opposing", "conflicting")):
        specifics["data_requests"].append("contradictions")

    # Supporting evidence
    if any(kw in q_lower for kw in ("supporting", "strongest", "evidence for")):
        specifics["data_requests"].append("supporting_evidence")

    # Downstream prioritization
    if "prioritization" in q_lower or "prioriti" in q_lower:
        specifics["data_requests"].append("prioritization_rationale")

    # Extract additional terms from query
    gene_matches = _GENE_PAT.findall(query)
    specifics["filter_terms"].extend(gene_matches[:5])

    return specifics


# ── Sentence-level tokenizer for bidirectional traceability ──

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
_PROTEIN_SEQ_PAT = re.compile(
    r"\b([ACDEFGHIKLMNPQRSTVWY]{10,})\b"
)


def tokenize_sentences(text: str) -> List[Dict[str, Any]]:
    """Split text into sentences with positional offsets for traceability."""
    if not text or len(text) < 10:
        return []
    sentences = _SENTENCE_SPLIT.split(text)
    result = []
    offset = 0
    for i, sent in enumerate(sentences):
        sent = sent.strip()
        if len(sent) < 15:
            offset += len(sent) + 1
            continue
        result.append({
            "idx": i,
            "text": sent,
            "offset": offset,
            "length": len(sent),
        })
        offset += len(sent) + 1
    return result


def extract_evidence_sentences(
    papers: List[Dict[str, Any]],
    claims: List[str],
    max_per_claim: int = 3,
) -> Dict[str, List[Dict[str, Any]]]:
    """For each claim string, find the best matching sentences across papers.

    Returns {claim_text: [{paper_id, paper_title, sentence, offset, score}]}
    Used for bidirectional traceability — clicking a claim → exact source sentence.
    """
    evidence_map: Dict[str, List[Dict[str, Any]]] = {}

    for claim in claims:
        claim_lower = claim.lower()
        claim_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", claim_lower))
        if not claim_words:
            continue

        matches: List[Dict[str, Any]] = []

        for paper in papers[:50]:
            text = " ".join(filter(None, [
                paper.get("title", ""),
                paper.get("abstract", ""),
                paper.get("snippet", ""),
            ]))
            sentences = tokenize_sentences(text)

            for sent in sentences:
                sent_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", sent["text"].lower()))
                if not sent_words:
                    continue
                overlap = len(claim_words & sent_words)
                score = overlap / max(len(claim_words), 1)
                if score >= 0.3:
                    matches.append({
                        "paper_id": paper.get("id", ""),
                        "paper_title": paper.get("title", "")[:150],
                        "doi": paper.get("doi", ""),
                        "sentence": sent["text"][:300],
                        "offset": sent["offset"],
                        "score": round(score, 3),
                        "year": paper.get("year"),
                        "source": (paper.get("provenance", [{}])[0].get("source", "")
                                   if paper.get("provenance") else ""),
                    })

        # Sort by score desc, take top N
        matches.sort(key=lambda m: m["score"], reverse=True)
        evidence_map[claim[:200]] = matches[:max_per_claim]

    return evidence_map


def build_paper_sentences(
    papers: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Build per-paper sentence index for traceability side-panel.

    Each paper gets its abstract tokenized into sentences with offsets.
    Frontend can use these to highlight exact source text when user clicks citation.
    """
    indexed = []
    for paper in papers[:50]:
        text = paper.get("abstract", "") or paper.get("snippet", "")
        if not text:
            continue
        sentences = tokenize_sentences(text)
        if sentences:
            indexed.append({
                "paper_id": paper.get("id", ""),
                "title": paper.get("title", "")[:200],
                "doi": paper.get("doi", ""),
                "year": paper.get("year"),
                "sentences": sentences[:30],  # Cap sentences per paper
            })
    return indexed


# ── SMILES / Protein sequence extraction from literature ──

def extract_structures_from_literature(
    papers: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Extract SMILES strings and protein sequences mentioned in paper texts.

    Returns list of {type, value, paper_title, paper_id, context} for rendering
    in the interactive Structures Grid.
    """
    structures: List[Dict[str, Any]] = []
    seen: set = set()

    for paper in papers[:50]:
        text = " ".join(filter(None, [
            paper.get("title", ""),
            paper.get("abstract", ""),
            paper.get("snippet", ""),
        ]))

        # Extract SMILES
        smiles_matches = _SMILES_PAT.findall(text)
        for smi in smiles_matches:
            smi_clean = smi.strip()
            if smi_clean in seen or len(smi_clean) < 10:
                continue
            # Basic SMILES validation: must have ring/branch/bond AND lowercase atom
            if not re.search(r"[()=@#\[\]]", smi_clean):
                continue
            # Real SMILES contain lowercase letters (aromatic atoms, element symbols)
            if not re.search(r"[a-z]", smi_clean):
                continue
            # Real SMILES almost always have digits (ring numbers)
            if not re.search(r"\d", smi_clean):
                continue
            # Reject if looks like a gene/protein name (mostly uppercase + digits)
            alpha_chars = [c for c in smi_clean if c.isalpha()]
            if alpha_chars and sum(1 for c in alpha_chars if c.isupper()) / len(alpha_chars) > 0.7:
                continue
            # Reject if contains common English word fragments
            low = smi_clean.lower()
            if any(w in low for w in ('poly', 'based', 'related', 'mutant', 'mutat', 'type', 'assoc', 'patient', 'treatment', 'positive', 'negative', 'receptor')):
                continue
            seen.add(smi_clean)
            # Find context sentence
            ctx = ""
            for sent in _SENTENCE_SPLIT.split(text):
                if smi_clean in sent:
                    ctx = sent.strip()[:200]
                    break
            structures.append({
                "type": "smiles",
                "value": smi_clean,
                "paper_id": paper.get("id", ""),
                "paper_title": paper.get("title", "")[:150],
                "doi": paper.get("doi", ""),
                "context": ctx,
                "source": "regex",
            })

        # Extract protein sequences (≥10 residue uppercase amino acid strings)
        protein_matches = _PROTEIN_SEQ_PAT.findall(text)
        for seq in protein_matches:
            seq_clean = seq.strip()
            if seq_clean in seen or len(seq_clean) < 12:
                continue
            # Filter false positives (common English words in all-caps)
            if seq_clean in ("ABSTRACT", "RESULTS", "METHODS", "MATERIALS",
                             "DISCUSSION", "INTRODUCTION", "CONCLUSION",
                             "FINDINGS", "BACKGROUND", "SUPPLEMENTARY",
                             "PARTICIPANTS", "OBJECTIVES", "POPULATION",
                             "CONCLUSIONS", "SIGNIFICANT", "TREATMENT",
                             "PROGNOSIS", "DIAGNOSIS", "EXPRESSION",
                             "MUTATIONS", "SCREENING", "DETECTION"):
                continue
            seen.add(seq_clean)
            structures.append({
                "type": "protein_sequence",
                "value": seq_clean,
                "paper_id": paper.get("id", ""),
                "paper_title": paper.get("title", "")[:150],
                "doi": paper.get("doi", ""),
                "context": "",
            })

    return structures[:30]


def enrich_structures_from_pubchem(
    terms_map: Dict[str, Any],
    existing_structures: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Query PubChem for canonical SMILES of drug/compound names found in literature.

    Supplements regex-extracted SMILES with verified structures from PubChem.
    """
    import httpx

    drugs = terms_map.get("drugs", {})
    if not drugs:
        log.info("pubchem_enrich_skip", reason="no drugs in terms_map")
        return existing_structures

    seen_values = {s.get("value", "") for s in existing_structures}
    new_structs = list(existing_structures)

    log.info("pubchem_enrich_start", drug_count=len(drugs), top_drugs=list(drugs.keys())[:10])

    for drug_name, freq in sorted(drugs.items(), key=lambda x: -x[1])[:15]:
        if len(drug_name) < 3 or drug_name.lower() in ("drug", "compound", "molecule", "agent", "therapy"):
            continue
        try:
            url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{drug_name}/property/CanonicalSMILES,MolecularFormula,MolecularWeight,IUPACName/JSON"
            resp = httpx.get(url, timeout=8.0)
            if resp.status_code != 200:
                log.debug("pubchem_miss", drug=drug_name, status=resp.status_code)
                continue
            data = resp.json()
            props = data.get("PropertyTable", {}).get("Properties", [{}])[0]
            smi = props.get("CanonicalSMILES") or props.get("ConnectivitySMILES") or props.get("IsomericSMILES") or ""
            if smi and smi not in seen_values and len(smi) >= 5:
                seen_values.add(smi)
                new_structs.append({
                    "type": "smiles",
                    "value": smi,
                    "paper_id": "",
                    "paper_title": f"PubChem: {drug_name}",
                    "doi": "",
                    "context": f"{drug_name} — {props.get('IUPACName', '')} (MW: {props.get('MolecularWeight', '')}, {props.get('MolecularFormula', '')})",
                    "source": "pubchem",
                    "drug_name": drug_name,
                    "molecular_formula": props.get("MolecularFormula", ""),
                    "molecular_weight": props.get("MolecularWeight", ""),
                })
        except Exception:
            continue

    return new_structs[:30]


# ── Pathway-literature cross-reference ──

def cross_reference_pathways(
    papers: List[Dict[str, Any]],
    pathway_data: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Cross-reference pathway entries with literature papers.

    For each pathway, find papers that mention it → enables
    "Which papers discuss this pathway?" annotations.
    """
    if not pathway_data:
        return []

    enriched = []
    for pw in pathway_data[:20]:
        pw_name = (pw.get("name", "") or pw.get("title", "") or "").lower()
        pw_id = pw.get("id", "")
        if not pw_name:
            continue

        # Find papers mentioning this pathway
        mentioning_papers = []
        pw_terms = set(re.findall(r"\b[a-zA-Z]{3,}\b", pw_name))
        if not pw_terms:
            continue

        for paper in papers[:50]:
            text = " ".join(filter(None, [
                paper.get("title", ""),
                paper.get("abstract", ""),
                paper.get("snippet", ""),
            ])).lower()

            paper_words = set(re.findall(r"\b[a-zA-Z]{3,}\b", text))
            overlap = len(pw_terms & paper_words)
            if overlap >= max(len(pw_terms) * 0.5, 2):
                mentioning_papers.append({
                    "paper_id": paper.get("id", ""),
                    "title": paper.get("title", "")[:150],
                    "year": paper.get("year"),
                    "doi": paper.get("doi", ""),
                })

        enriched.append({
            **pw,
            "lit_papers": mentioning_papers[:5],
            "lit_paper_count": len(mentioning_papers),
        })

    return enriched


# ── LLM-verified contradiction detection ──

async def verify_contradictions_llm(
    papers: List[Dict[str, Any]],
    query: str,
    engine: Any = None,
) -> List[Dict[str, Any]]:
    """Use Gemma 4 26B to verify contradictions between paper pairs.

    Flow:
    1. Pre-filter candidate pairs via keyword heuristic (fast)
    2. Send top candidate pairs to LLM for verification
    3. LLM confirms/rejects + explains WHY they contradict
       (in vivo vs in vitro, dosage, model organism, methodology)
    4. Returns LLM-verified contradictions w/ experimental context

    Falls back to keyword-only if LLM unavailable.
    """
    if not papers or len(papers) < 2:
        return []

    # Step 1: Build candidate pairs via keyword scan
    from services.contradiction_detector import _CONTRADICTION_PAIRS, _extract_context
    candidates: List[Dict[str, Any]] = []

    texts = []
    for p in papers[:40]:
        t = " ".join(filter(None, [
            p.get("title", ""),
            p.get("abstract", ""),
            p.get("full_text", "")[:3000] if p.get("full_text") else "",
            p.get("snippet", ""),
        ]))
        texts.append((t, p))

    for i in range(len(texts)):
        text_a, pa = texts[i]
        la = text_a.lower()
        for j in range(i + 1, len(texts)):
            text_b, pb = texts[j]
            lb = text_b.lower()
            for wa, wb in _CONTRADICTION_PAIRS:
                if (wa in la and wb in lb) or (wb in la and wa in lb):
                    candidates.append({
                        "idx_a": i, "idx_b": j,
                        "paper_a": pa, "paper_b": pb,
                        "text_a": text_a[:2000], "text_b": text_b[:2000],
                        "trigger": f"{wa} vs {wb}",
                        "ctx_a": _extract_context(text_a),
                        "ctx_b": _extract_context(text_b),
                    })
                    break
            if len(candidates) >= 15:
                break
        if len(candidates) >= 15:
            break

    # Step 1b: If keyword pre-filter found nothing, pick diverse paper pairs
    # for LLM-based contradiction discovery (broader net)
    if not candidates and engine and len(texts) >= 2:
        import random as _rand
        # Pick up to 6 diverse pairs (different years, different sources)
        all_pairs = []
        for i in range(len(texts)):
            for j in range(i + 1, len(texts)):
                pa, pb = texts[i][1], texts[j][1]
                # Prefer papers from different years or sources for diversity
                score = 0
                if pa.get("year") != pb.get("year"):
                    score += 1
                if pa.get("source") != pb.get("source"):
                    score += 1
                all_pairs.append((score, i, j))
        all_pairs.sort(key=lambda x: -x[0])
        for _, i, j in all_pairs[:6]:
            pa, pb = texts[i][1], texts[j][1]
            candidates.append({
                "idx_a": i, "idx_b": j,
                "paper_a": pa, "paper_b": pb,
                "text_a": texts[i][0][:2000], "text_b": texts[j][0][:2000],
                "trigger": "LLM-discovery (no keyword match)",
                "ctx_a": _extract_context(texts[i][0]),
                "ctx_b": _extract_context(texts[j][0]),
            })

    if not candidates:
        return []

    # Step 2: LLM verification (sequential — Ollama queues requests, parallel wastes timeout)
    verified: List[Dict[str, Any]] = []

    if engine:
        # Process top 3 candidates sequentially (each ~60s on Gemma 4 26B)
        for cand in candidates[:3]:
            pa_title = cand["paper_a"].get("title", "Unknown")[:200]
            pb_title = cand["paper_b"].get("title", "Unknown")[:200]
            text_a_short = cand["text_a"][:1500]
            text_b_short = cand["text_b"][:1500]

            prompt = (
                f"You are a biomedical research analyst. Two papers may have a nuanced relationship "
                f"regarding '{query}'. Analyze and determine:\n"
                f"1. Relationship: Do they 'Contradict', 'Refine', 'Fail to Replicate', 'Use Methodology From', 'Expand to New Model' or 'Similar'?\n"
                f"2. Claims: What specifically are the two respective findings/claims?\n"
                f"3. Experimental Context: List the EXPLICIT variables (e.g., In vivo vs In vitro, Murine vs Human, different dosages, cell lines, timeframe).\n"
                f"4. Which finding is more reliable and why?\n\n"
                f"Paper A: \"{pa_title}\"\n{text_a_short}\n\n"
                f"Paper B: \"{pb_title}\"\n{text_b_short}\n\n"
                f"Respond in this exact format:\n"
                f"RELATIONSHIP: [Contradict | Refine | Fail to Replicate | Uses Methodology From | Expands to New Model | Similar | Unrelated]\n"
                f"CLAIM_A: [Paper A's claim]\n"
                f"CLAIM_B: [Paper B's claim]\n"
                f"CONTEXT_A: [Paper A's experimental context]\n"
                f"CONTEXT_B: [Paper B's experimental context]\n"
                f"REACHED_BY: [Why they differ or relate - differences in context]\n"
                f"RELIABILITY: [Which is more reliable and why]"
            )

            try:
                resp = await engine.generate(prompt, max_tokens=500)
                llm_text = resp.get("text", "")
                log.debug("llm_contradiction_raw", text_len=len(llm_text), first_200=llm_text[:200])

                # Strip <think>...</think> blocks (Gemma 4 thinking mode)
                import re as _re
                clean_text = _re.sub(r"<think>.*?</think>", "", llm_text, flags=_re.DOTALL).strip()

                lines = clean_text.split("\n")
                parsed = {}
                for line in lines:
                    # Strip markdown bold, list markers, extra whitespace
                    cleaned = line.strip().lstrip("-•*0123456789. ").replace("**", "").strip()
                    for key in ("RELATIONSHIP", "CLAIM_A", "CLAIM_B", "CONTEXT_A", "CONTEXT_B",
                                "REACHED_BY", "RELIABILITY"):
                        if cleaned.upper().startswith(key + ":"):
                            parsed[key.lower()] = cleaned.split(":", 1)[1].strip()

                log.debug("llm_contradiction_parsed", keys=list(parsed.keys()), rel=parsed.get("relationship", ""))
                rel = parsed.get("relationship", "").lower()
                # Accept any successfully-parsed relationship except "unrelated"
                if rel and "unrelated" not in rel:
                    verified.append({
                        "relationship": parsed.get("relationship", "Contradict").strip(),
                        "claim_a": parsed.get("claim_a", cand["text_a"][:300]),
                        "claim_b": parsed.get("claim_b", cand["text_b"][:300]),
                        "source_a": {
                            "title": pa_title,
                            "id": cand["paper_a"].get("id", ""),
                            "doi": cand["paper_a"].get("doi", ""),
                            "year": cand["paper_a"].get("year"),
                            "url": cand["paper_a"].get("url", ""),
                        },
                        "source_b": {
                            "title": pb_title,
                            "id": cand["paper_b"].get("id", ""),
                            "doi": cand["paper_b"].get("doi", ""),
                            "year": cand["paper_b"].get("year"),
                            "url": cand["paper_b"].get("url", ""),
                        },
                        "reason": parsed.get("reached_by", f"Opposing signals: {cand['trigger']}"),
                        "reliability_judgment": parsed.get("reliability", ""),
                        "severity": "high" if ("contradict" in rel or "fail" in rel) else "moderate",
                        "context_a": parsed.get("context_a", ""),
                        "context_b": parsed.get("context_b", ""),
                        "llm_verified": True,
                        "explanation": (
                            f"LLM-verified Relationship ({parsed.get('relationship', 'Contradict')}): {parsed.get('reached_by', cand['trigger'])}. "
                            f"Context A: {parsed.get('context_a', 'Unknown')} "
                            f"Context B: {parsed.get('context_b', 'Unknown')}"
                        ),
                    })
            except Exception as exc:
                log.debug("llm_contradiction_verify_failed", error=str(exc)[:200])

    # Fallback: if LLM returned nothing, use keyword candidates w/ context
    if not verified:
        from services.contradiction_detector import _extract_context
        for cand in candidates[:10]:
            verified.append({
                "claim_a": cand["text_a"][:300],
                "claim_b": cand["text_b"][:300],
                "source_a": {
                    "title": cand["paper_a"].get("title", "")[:200],
                    "id": cand["paper_a"].get("id", ""),
                    "doi": cand["paper_a"].get("doi", ""),
                    "year": cand["paper_a"].get("year"),
                    "url": cand["paper_a"].get("url", ""),
                },
                "source_b": {
                    "title": cand["paper_b"].get("title", "")[:200],
                    "id": cand["paper_b"].get("id", ""),
                    "doi": cand["paper_b"].get("doi", ""),
                    "year": cand["paper_b"].get("year"),
                    "url": cand["paper_b"].get("url", ""),
                },
                "reason": f"Keyword signal: {cand['trigger']}",
                "severity": "moderate",
                "context_a": cand["ctx_a"],
                "context_b": cand["ctx_b"],
                "llm_verified": False,
                "explanation": (
                    f"Opposing terms: {cand['trigger']}. "
                    f"A={cand['ctx_a']['study_type']}, B={cand['ctx_b']['study_type']}"
                ),
            })

    return verified


# ── Traceable AI Summary w/ [Ref N] citations ──

async def build_traceable_summary(
    papers: List[Dict[str, Any]],
    query: str,
    contradictions: List[Dict[str, Any]],
    terms_map: Dict[str, Any],
    engine: Any = None,
) -> Dict[str, Any]:
    """Generate literature synthesis w/ traceable [Ref N] citations.

    Each [Ref N] maps to exact paper + sentence for bidirectional traceability.
    User can click [Ref N] → see exact source sentence in paper.

    Returns:
        {
            "summary_text": str,  # The narrative with [Ref N] tags
            "references": [{ref_num, paper_id, title, doi, sentence, year}],
            "supporting_findings": [top 5],
            "dissenting_findings": [top 5],
        }
    """
    if not papers:
        return {"summary_text": "No papers found.", "references": [],
                "supporting_findings": [], "dissenting_findings": []}

    # Build reference index from top papers
    ref_index: List[Dict[str, Any]] = []
    for i, p in enumerate(papers[:20]):
        text = " ".join(filter(None, [
            p.get("abstract", ""),
            p.get("full_text", "")[:3000] if p.get("full_text") else "",
            p.get("snippet", ""),
        ]))
        # Get key sentences from each paper
        sents = tokenize_sentences(text)
        key_sent = sents[0]["text"][:300] if sents else (text[:300] if text else "")

        ref_index.append({
            "ref_num": i + 1,
            "paper_id": p.get("id", ""),
            "title": p.get("title", "")[:200],
            "doi": p.get("doi", ""),
            "year": p.get("year"),
            "key_finding": key_sent,
            "authors": p.get("authors", [])[:3],
            "methodology": p.get("_experimental_context", {}).get("study_type", "unknown")
            if isinstance(p.get("_experimental_context"), dict)
            else _extract_experimental_context(text),
        })

    # Extract top genes/drugs/diseases for context
    top_genes = list(terms_map.get("genes", {}).keys())[:5]
    top_drugs = list(terms_map.get("drugs", {}).keys())[:5]
    top_diseases = list(terms_map.get("diseases", {}).keys())[:3]

    # Build LLM prompt for traceable synthesis
    ref_block = ""
    for r in ref_index[:15]:
        auth = ", ".join(r["authors"][:2]) if r["authors"] else "Unknown"
        ref_block += (
            f"[Ref {r['ref_num']}] {auth} ({r['year'] or 'n.d.'}): "
            f"\"{r['title']}\"\n"
            f"  Key finding: {r['key_finding']}\n"
            f"  Method: {r['methodology']}\n\n"
        )

    contradiction_block = ""
    if contradictions:
        for c in contradictions[:5]:
            sa = c.get("source_a", {})
            sb = c.get("source_b", {})
            contradiction_block += (
                f"- {sa.get('title', 'Paper A')[:80]} vs {sb.get('title', 'Paper B')[:80]}: "
                f"{c.get('reason', c.get('explanation', 'Opposing findings'))}\n"
            )

    summary_prompt = (
        f"You are synthesizing {len(papers)} research papers about: {query}\n\n"
        f"Key entities: genes={', '.join(top_genes)}, drugs={', '.join(top_drugs)}, "
        f"diseases={', '.join(top_diseases)}\n\n"
        f"REFERENCES:\n{ref_block}\n"
        f"{'CONTRADICTIONS:\\n' + contradiction_block if contradiction_block else ''}\n"
        f"Write a precise literature synthesis (300-500 words) that:\n"
        f"1. Synthesizes the actual findings — what compounds/genes/mechanisms were studied\n"
        f"2. References specific papers using [Ref N] tags (e.g. 'Compound X shows binding "
        f"affinity to Receptor Y in murine models [Ref 1]')\n"
        f"3. Highlights key contradictions between studies and WHY they differ\n"
        f"4. Identifies the strongest supporting and dissenting evidence\n"
        f"5. Notes methodology differences (in vivo vs in vitro, clinical vs preclinical)\n\n"
        f"Every major claim MUST have a [Ref N] citation. Be specific about findings, "
        f"not generic. Mention actual compound names, receptor targets, effect sizes when available."
    )

    summary_text = ""
    if engine:
        try:
            resp = await engine.generate(summary_prompt, max_tokens=1500)
            raw = resp.get("text", "")
            # Strip <think>...</think> blocks (Gemma 4 thinking mode)
            import re as _re
            summary_text = _re.sub(r"<think>.*?</think>", "", raw, flags=_re.DOTALL).strip()
        except Exception as exc:
            log.warning("traceable_summary_llm_failed", error=str(exc)[:200])

    # Fallback if LLM unavailable
    if not summary_text:
        parts = [f"Literature analysis of {len(papers)} papers for: {query}\n"]
        for r in ref_index[:10]:
            parts.append(f"[Ref {r['ref_num']}] {r['title']}: {r['key_finding'][:200]}")
        if contradictions:
            parts.append(f"\n{len(contradictions)} contradictions detected between studies.")
        summary_text = "\n".join(parts)

    # Extract supporting vs dissenting findings w/ prioritization rationale
    supporting = []
    dissenting = []
    for r in ref_index[:15]:
        finding = r["key_finding"][:300]
        methodology = r["methodology"]
        study_type = methodology.get("study_type", "unknown") if isinstance(methodology, dict) else str(methodology)

        # Generate prioritization rationale
        influence_reasons = []
        anti_reasons = []

        # Recency
        year = r.get("year")
        if year and isinstance(year, (int, float)) and year >= 2020:
            influence_reasons.append(f"Recent ({year}) — reflects current understanding")
        elif year and isinstance(year, (int, float)) and year < 2015:
            anti_reasons.append(f"Older study ({year}) — may not reflect latest evidence")

        # Study type strength
        if study_type in ("clinical", "meta_analysis"):
            influence_reasons.append(f"High evidence level ({study_type.replace('_', ' ')})")
        elif study_type == "in_silico":
            anti_reasons.append("Computational only — needs experimental validation")
        elif study_type == "in_vitro":
            anti_reasons.append("In vitro — may not translate to in vivo/clinical")

        # Has DOI (peer-reviewed indicator)
        if r.get("doi"):
            influence_reasons.append("Peer-reviewed (has DOI)")

        entry = {
            "ref_num": r["ref_num"],
            "title": r["title"],
            "doi": r["doi"],
            "year": year,
            "finding": finding,
            "methodology": methodology,
            "should_influence": influence_reasons or ["Relevant to query topic"],
            "should_not_influence": anti_reasons or [],
        }
        # Check if this paper appears in contradictions as dissenting
        is_dissenting = False
        for c in contradictions:
            sa = c.get("source_a", {})
            sb = c.get("source_b", {})
            title_short = r["title"][:50]
            if sb.get("title", "")[:50] == title_short or sa.get("title", "")[:50] == title_short:
                is_dissenting = True
                entry["contradiction_note"] = c.get("reason", c.get("explanation", ""))
                entry["should_not_influence"].append(
                    f"Contradicted by other evidence: {c.get('reason', '')[:100]}"
                )
                break
        if is_dissenting:
            dissenting.append(entry)
        else:
            supporting.append(entry)

    # If not enough dissenting from contradictions, pull weakest-evidence papers
    if len(dissenting) < 5 and len(supporting) > 5:
        # Sort supporting by number of anti_reasons (most limitations → dissenting)
        supporting.sort(key=lambda e: len(e.get("should_not_influence", [])), reverse=True)
        while len(dissenting) < 5 and len(supporting) > 5:
            weak = supporting.pop(0)
            if not weak.get("should_not_influence"):
                weak["should_not_influence"] = ["Weaker evidence relative to other findings"]
            dissenting.append(weak)

    return {
        "summary_text": summary_text,
        "references": ref_index,
        "supporting_findings": supporting[:5],
        "dissenting_findings": dissenting[:5],
    }


# ── Unified Pathways Diagram builder ──

def build_unified_pathways(
    terms_map: Dict[str, Any],
    papers: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Build a unified pathway diagram from all extracted terms.

    Connects genes → drugs → diseases → methods into a biological/chemical
    pathway visualization. Each node is a term, edges show relationships
    found across the literature corpus.

    Returns: {nodes: [...], edges: [...], pathway_layers: [...]}
    """
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []
    node_ids: set = set()

    LAYER_COLORS = {
        "gene": {"color": "#6366f1", "layer": 0, "label": "Molecular Targets"},
        "drug": {"color": "#e11d48", "layer": 1, "label": "Compounds/Drugs"},
        "disease": {"color": "#dc2626", "layer": 2, "label": "Disease/Phenotype"},
        "method": {"color": "#10b981", "layer": 3, "label": "Methodology"},
        "pathway": {"color": "#0891b2", "layer": 4, "label": "Biological Pathways"},
    }

    # Build nodes from terms
    for category in ("genes", "drugs", "diseases", "methods"):
        cat_key = category.rstrip("s") if category != "diseases" else "disease"
        layer_info = LAYER_COLORS.get(cat_key, {"color": "#888", "layer": 5})
        for term, freq in list(terms_map.get(category, {}).items())[:15]:
            nid = f"{cat_key}:{term}"
            if nid not in node_ids:
                nodes.append({
                    "id": nid,
                    "label": term,
                    "type": cat_key,
                    "color": layer_info["color"],
                    "layer": layer_info["layer"],
                    "frequency": freq,
                    "size": min(freq * 3 + 8, 40),
                })
                node_ids.add(nid)

    # Build edges from co-occurrence in papers
    edge_counts: Dict[str, int] = {}
    edge_papers: Dict[str, List[str]] = {}

    for paper in papers[:40]:
        text = " ".join(filter(None, [
            paper.get("title", ""),
            paper.get("abstract", ""),
            paper.get("snippet", ""),
        ])).lower()

        paper_title = paper.get("title", "")[:80]
        present_nodes = []
        for n in nodes:
            if n["label"].lower() in text:
                present_nodes.append(n["id"])

        for a in range(len(present_nodes)):
            for b in range(a + 1, len(present_nodes)):
                eid = "|".join(sorted([present_nodes[a], present_nodes[b]]))
                edge_counts[eid] = edge_counts.get(eid, 0) + 1
                if eid not in edge_papers:
                    edge_papers[eid] = []
                if len(edge_papers[eid]) < 3:
                    edge_papers[eid].append(paper_title)

    for eid, count in sorted(edge_counts.items(), key=lambda x: -x[1])[:60]:
        src, tgt = eid.split("|")
        src_type = src.split(":")[0]
        tgt_type = tgt.split(":")[0]

        # Determine edge type from node categories
        edge_type = "co_occurrence"
        if src_type != tgt_type:
            edge_type = f"{src_type}_to_{tgt_type}"

        edges.append({
            "source": src,
            "target": tgt,
            "type": edge_type,
            "weight": count,
            "papers": edge_papers.get(eid, []),
            "label": f"{count} papers",
        })

    # Define pathway layers for visualization
    pathway_layers = []
    for cat_key, info in LAYER_COLORS.items():
        layer_nodes = [n for n in nodes if n["type"] == cat_key]
        if layer_nodes:
            pathway_layers.append({
                "layer": info["layer"],
                "label": info["label"],
                "color": info["color"],
                "node_count": len(layer_nodes),
            })

    return {
        "nodes": nodes,
        "edges": edges,
        "pathway_layers": sorted(pathway_layers, key=lambda x: x["layer"]),
        "total_nodes": len(nodes),
        "total_edges": len(edges),
    }


# ── Mechanism clustering ──

_MECHANISM_CATEGORIES = {
    "Inflammation & Immune": re.compile(
        r"\b(inflammat|cytokine|interleukin|IL-\d|TNF|NF-κB|NF-kB|NFkB|"
        r"immune|autoimmun|T.cell|B.cell|macrophage|neutrophil|complement|"
        r"interferon|chemokine|toll.like|TLR|innate.immun|adaptive.immun|"
        r"inflammatory|anti.inflammat)\b", re.I),
    "Oxidative Stress & Metabolism": re.compile(
        r"\b(oxidative\s+stress|ROS|reactive\s+oxygen|antioxidant|redox|"
        r"mitochond|metaboli[sc]|glycoly|gluconeogenesis|lipid\s+metabolism|"
        r"fatty\s+acid|insulin\s+resist|glucose\s+transport|AMPK|mTOR|"
        r"PPARγ|PPAR.gamma|adiponectin|leptin|ketogenesis|beta.oxidat)\b", re.I),
    "Cell Signaling & Kinase": re.compile(
        r"\b(signal|kinase|phosphorylat|MAPK|ERK|JNK|PI3K|AKT|Wnt|Notch|"
        r"Hedgehog|receptor\s+tyrosine|EGFR|VEGF|PDGF|FGF|cascade|"
        r"transduction|second\s+messenger|cAMP|calcium\s+signal)\b", re.I),
    "Apoptosis & Cell Death": re.compile(
        r"\b(apoptosis|programmed\s+cell\s+death|caspase|Bcl-?2|BAX|"
        r"necrosis|necroptosis|ferroptosis|pyroptosis|autophagy|"
        r"cell\s+death|pro.apoptotic|anti.apoptotic|survival\s+signal)\b", re.I),
    "Gene Regulation & Epigenetics": re.compile(
        r"\b(epigenet|methylat|acetylat|histone|chromatin|miRNA|lncRNA|"
        r"transcription\s+factor|promoter|enhancer|gene\s+expression|"
        r"splicing|CRISPR|siRNA|shRNA|gene\s+silencing|DNA\s+repair|"
        r"telomere|epigenome)\b", re.I),
    "Genetic Variants & GWAS": re.compile(
        r"\b(GWAS|genome.wide|SNP|variant|polymorphism|allele|locus|loci|"
        r"genotype|phenotype|heritab|genetic\s+risk|susceptib|"
        r"linkage\s+disequilibr|haplotype|copy\s+number|CNV)\b", re.I),
    "Drug Action & Pharmacology": re.compile(
        r"\b(pharmacol|pharmacokin|bioavailab|half.life|clearance|"
        r"drug\s+target|binding\s+affinity|IC50|EC50|dose.response|"
        r"therapeutic|drug\s+resist|efflux|CYP\d|metaboli[sz]|"
        r"absorption|distribution|excretion|toxicity|adverse|side\s+effect)\b", re.I),
    "Structural & Protein": re.compile(
        r"\b(protein\s+structure|crystal|binding\s+site|pocket|conformation|"
        r"folding|misfolding|aggregat|amyloid|prion|chaperone|"
        r"PDB|cryo.EM|X.ray\s+crystal|NMR\s+struct|docking)\b", re.I),
}


def cluster_by_mechanism(
    papers: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Group papers by biological mechanism category.

    Returns {
        "clusters": [{name, papers: [{title, id, doi, year, relevance}], count}],
        "unclustered": [{title, id, doi, year}],
        "total_clustered": int,
    }
    """
    clusters: Dict[str, List[Dict[str, Any]]] = {k: [] for k in _MECHANISM_CATEGORIES}
    unclustered: List[Dict[str, Any]] = []

    for paper in papers:
        text = " ".join(filter(None, [
            paper.get("title", ""),
            paper.get("abstract", ""),
            paper.get("snippet", ""),
        ]))

        matched = False
        for mech_name, pat in _MECHANISM_CATEGORIES.items():
            if pat.search(text):
                clusters[mech_name].append({
                    "title": paper.get("title", "")[:200],
                    "id": paper.get("id", ""),
                    "doi": paper.get("doi", ""),
                    "year": paper.get("year"),
                    "relevance_score": paper.get("_relevance_score", 0),
                })
                matched = True
                break  # Each paper → primary mechanism only

        if not matched:
            unclustered.append({
                "title": paper.get("title", "")[:200],
                "id": paper.get("id", ""),
                "doi": paper.get("doi", ""),
                "year": paper.get("year"),
            })

    result_clusters = []
    for name, papers_list in clusters.items():
        if papers_list:
            result_clusters.append({
                "name": name,
                "papers": papers_list,
                "count": len(papers_list),
            })

    result_clusters.sort(key=lambda c: c["count"], reverse=True)

    return {
        "clusters": result_clusters,
        "unclustered": unclustered[:20],
        "total_clustered": sum(c["count"] for c in result_clusters),
    }

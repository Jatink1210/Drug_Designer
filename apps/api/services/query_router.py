"""Query Router — Intent detection + search term extraction."""

from __future__ import annotations

import re
from typing import Tuple

# Intent categories
INTENTS = [
    "protein", "gene", "molecule", "drug", "disease", "pathway",
    "structure", "clinical_trial", "publication", "variant", "general",
]

# Keyword rules: (intent, keywords)
_RULES: list[Tuple[str, list[str]]] = [
    ("structure", ["structure", "3d", "crystal", "pdb", "alphafold", "cryo-em", "nmr structure"]),
    ("protein", [
        "protein", "receptor", "kinase", "enzyme", "antibody", "transporter",
        "uniprot", "p53", "egfr", "brca", "akt", "mtor", "kras",
    ]),
    ("gene", ["gene", "ensembl", "ensg", "transcript", "exon"]),
    ("variant", ["variant", "mutation", "polymorphism", "snp", "rsid", "allele", "gwas"]),
    ("drug", [
        "drug", "inhibitor", "agonist", "antagonist", "therapeutic",
        "imatinib", "gefitinib", "pembrolizumab", "trastuzumab",
    ]),
    ("molecule", [
        "molecule", "compound", "smiles", "chemical", "pubchem", "chembl",
        "molecular weight", "logp",
    ]),
    ("disease", [
        "disease", "disorder", "syndrome", "cancer", "diabetes", "alzheimer",
        "parkinson", "covid", "malaria", "hypertension", "asthma",
    ]),
    ("pathway", ["pathway", "signaling", "kegg", "reactome", "mapk", "wnt", "notch"]),
    ("clinical_trial", [
        "clinical trial", "nct", "phase i", "phase ii", "phase iii",
        "recruiting", "trial", "randomized",
    ]),
    ("publication", ["publication", "paper", "pubmed", "pmid", "journal", "review"]),
]

# Phrase priority (multi-word > single word)
_PHRASE_PRIORITY: list[Tuple[str, list[str]]] = [
    ("clinical_trial", ["clinical trial", "phase i ", "phase ii ", "phase iii"]),
    ("pathway", ["signaling pathway", "metabolic pathway"]),
    ("structure", ["crystal structure", "3d structure", "cryo-em structure"]),
]

_UNIPROT_PATTERN = re.compile(r"\b[OPQ][0-9][A-Z0-9]{3}[0-9]\b", re.I)
_PDB_PATTERN = re.compile(r"\b[0-9][A-Za-z0-9]{3}\b")
_NCT_PATTERN = re.compile(r"\bNCT\d{8}\b", re.I)


def detect_intent(query: str) -> Tuple[str, str, str]:
    """Classify query intent and extract search term.

    Returns (intent, cleaned_search_term, method).
    """
    q_lower = query.lower().strip()

    # Check for explicit identifiers first
    if _UNIPROT_PATTERN.search(query):
        return "protein", query.strip(), "pattern"
    if _NCT_PATTERN.search(query):
        return "clinical_trial", query.strip(), "pattern"
    if _PDB_PATTERN.match(query.strip()) and len(query.strip()) == 4:
        return "structure", query.strip().upper(), "pattern"

    # Phrase priority matching
    for intent, phrases in _PHRASE_PRIORITY:
        if any(p in q_lower for p in phrases):
            return intent, _clean_term(query), "phrase"

    # Scored keyword matching
    scores: dict[str, float] = {}
    for intent, keywords in _RULES:
        score = 0.0
        for kw in keywords:
            if kw in q_lower:
                score += 2.0 if " " in kw else 1.0
        if score > 0:
            scores[intent] = score

    if scores:
        best = max(scores, key=scores.get)  # type: ignore
        return best, _clean_term(query), "keyword"

    return "general", query.strip(), "fallback"


_NOISE_WORDS = {
    "what", "which", "show", "find", "about", "are", "is", "the", "a", "an",
    "for", "with", "from", "in", "of", "to", "and", "or", "associated",
    "related", "linked", "proteins", "genes", "drugs", "tell", "me", "all",
}


def _clean_term(query: str) -> str:
    """Strip noise words from query to extract the core search term."""
    tokens = query.strip().split()
    cleaned = [t for t in tokens if t.lower().rstrip("?.,!") not in _NOISE_WORDS]
    return " ".join(cleaned) if cleaned else query.strip()

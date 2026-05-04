"""Advanced query classifier for cockpit analysis.

Extracts structured intent from natural-language queries to route
the cockpit pipeline appropriately. Handles all 25 query type
categories from the DrugSynth 1000-query test spec.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ── Known diseases (canonical + aliases) ──────────────────

_DISEASE_MAP: list[Tuple[str, list[str]]] = [
    ("triple-negative breast cancer", [
        "triple-negative breast cancer", "triple negative breast cancer",
        "tnbc", "triple-negative", "basal-like breast cancer",
    ]),
    ("Type 2 diabetes mellitus", [
        "type 2 diabetes mellitus", "type 2 diabetes", "t2dm", "t2d",
        "diabetes mellitus type 2", "non-insulin dependent diabetes",
    ]),
    ("Alzheimer's disease", [
        "alzheimer's disease", "alzheimers disease", "alzheimer disease",
        "alzheimer's", "alzheimers", "ad dementia",
    ]),
    ("non-small cell lung cancer", [
        "non-small cell lung cancer", "non small cell lung cancer",
        "nsclc", "non-small-cell lung cancer",
    ]),
    ("rheumatoid arthritis", [
        "rheumatoid arthritis", "ra disease", "rheumatoid",
    ]),
    ("glioblastoma", [
        "glioblastoma", "glioblastoma multiforme", "gbm",
    ]),
    ("ulcerative colitis", [
        "ulcerative colitis", "uc disease",
    ]),
    ("hepatocellular carcinoma", [
        "hepatocellular carcinoma", "hcc", "liver cancer",
        "hepatocarcinoma",
    ]),
    ("Parkinson's disease", [
        "parkinson's disease", "parkinsons disease", "parkinson disease",
        "parkinson's", "parkinsons", "parkinsonism",
    ]),
    ("melanoma", [
        "melanoma", "malignant melanoma", "cutaneous melanoma",
        "metastatic melanoma", "uveal melanoma",
    ]),
    ("acute myeloid leukemia", [
        "acute myeloid leukemia", "acute myeloid leukaemia", "aml",
    ]),
    ("breast cancer", [
        "breast cancer", "breast carcinoma", "mammary carcinoma",
    ]),
    ("colorectal cancer", [
        "colorectal cancer", "colon cancer", "rectal cancer", "crc",
    ]),
    ("pancreatic cancer", [
        "pancreatic cancer", "pancreatic adenocarcinoma", "pdac",
    ]),
    ("prostate cancer", [
        "prostate cancer", "prostatic adenocarcinoma", "crpc",
    ]),
    ("ovarian cancer", [
        "ovarian cancer", "ovarian carcinoma",
    ]),
    ("chronic kidney disease", [
        "chronic kidney disease", "ckd", "renal failure",
    ]),
    ("systemic lupus erythematosus", [
        "systemic lupus erythematosus", "lupus", "sle",
    ]),
    ("multiple sclerosis", [
        "multiple sclerosis", "ms disease",
    ]),
    ("Crohn's disease", [
        "crohn's disease", "crohns disease", "crohn disease",
    ]),
    ("psoriasis", [
        "psoriasis", "psoriatic",
    ]),
    ("asthma", [
        "asthma", "bronchial asthma",
    ]),
    ("Huntington's disease", [
        "huntington's disease", "huntingtons disease", "huntington disease",
        "huntington's", "huntingtons",
    ]),
    ("renal cell carcinoma", [
        "renal cell carcinoma", "rcc", "kidney cancer",
    ]),
]

# ── Known gene symbols ───────────────────────────────────

_GENE_SYMBOLS = [
    "EGFR", "PPARG", "KRAS", "TNF", "IL6", "PCSK9", "APOE",
    "PIK3CA", "JAK2", "BRAF", "BRCA1", "BRCA2", "TP53", "MYC",
    "AKT1", "MTOR", "PTEN", "RB1", "HER2", "ERBB2", "ALK",
    "ROS1", "MET", "NTRK1", "VEGFA", "VEGFR", "FGFR1", "FGFR2",
    "CDK4", "CDK6", "BCL2", "MCL1", "IDH1", "IDH2", "NOTCH1",
    "WNT1", "CTNNB1", "SMAD4", "TGFB1", "RAF1", "MEK1", "ERK1",
    "NFKB1", "STAT3", "SRC", "ABL1", "FLT3", "KIT", "PDGFRA",
    "RET", "NRAS", "HRAS", "MAP2K1", "MAP2K2", "STK11", "KEAP1",
    "NRF2", "APC", "CTLA4", "PD1", "PDL1", "CD274", "PTPN11",
    "SHP2", "BCR", "TNFRSF1A", "IL4", "CCL3", "JUN", "CXCL8",
    "RELA", "CCL2", "IL6R", "HLA-DRB1", "IL37", "IL10RB", "IL23R",
    "IRF5", "MUC12",
    # Additional disease-associated targets
    "PTPN22", "IL1B", "IL10", "NOD2", "CARD9", "TCF7L2", "KCNJ11",
    "SLC30A8", "INS", "GCK", "HNF1A", "ABCC8", "IRS1", "APP",
    "PSEN1", "PSEN2", "MAPT", "BACE1", "TREM2", "CLU", "BIN1",
    "SORL1", "MGMT", "CDKN2A", "NF1", "AXIN1", "ARID1A", "TERT",
    # Neurodegeneration
    "SNCA", "LRRK2", "PARK7", "PINK1", "PRKN", "GBA1", "VPS35",
    "COMT", "HTT", "BDNF", "DCAF17",
    # Additional cancer
    "AR", "CDH1", "GATA3", "SPOP", "FOXA1", "CDK12", "TMPRSS2",
    "ERG", "CCNE1", "PALB2", "ATM", "TGFBR2", "FBXW7", "MLH1",
    "MSH2", "NPM1", "DNMT3A", "TET2", "RUNX1", "CEBPA",
    # Autoimmune
    "IL17A", "IL12B", "CARD14", "TRAF3IP2", "IL7R", "IL2RA",
    "CD58", "CLEC16A", "IRF8", "TYK2", "ATG16L1", "IRGM",
    # Respiratory
    "IL13", "IL33", "TSLP", "IL5", "ADAM33", "ORMDL3", "GSDMB", "ADRB2",
    # Renal
    "PKD1", "PKD2", "UMOD", "APOL1", "AGT", "ACE", "NPHS1",
]
_GENE_SYMBOLS_SET = set(_GENE_SYMBOLS)

# ── Known signaling pathways ─────────────────────────────

_PATHWAY_MAP: list[Tuple[str, list[str]]] = [
    ("PI3K-AKT", ["pi3k-akt", "pi3k/akt", "pi3k akt", "pi3k"]),
    ("NF-kappaB", ["nf-kappab", "nf-κb", "nfkb", "nf-kb", "nuclear factor kappa"]),
    ("insulin signaling", ["insulin signaling", "insulin pathway"]),
    ("MAPK", ["mapk", "ras-raf-mek-erk", "ras/raf/mek/erk", "mapk/erk"]),
    ("JAK-STAT", ["jak-stat", "jak/stat", "janus kinase"]),
    ("mTOR", ["mtor", "mammalian target of rapamycin", "mtor signaling"]),
    ("Wnt", ["wnt signaling", "wnt/beta-catenin", "wnt pathway"]),
    ("TGF-beta", ["tgf-beta", "tgf-β", "tgfb", "transforming growth factor beta"]),
    ("Notch", ["notch signaling", "notch pathway"]),
    ("Hedgehog", ["hedgehog signaling", "hedgehog pathway", "shh"]),
    ("apoptosis", ["apoptosis", "apoptotic", "programmed cell death"]),
    ("autophagy", ["autophagy pathway"]),
    ("p53", ["p53 pathway", "p53 signaling"]),
]

# ── Cohort / population patterns ─────────────────────────

_COHORT_PATTERNS: list[Tuple[str, list[str]]] = [
    ("Indian", ["indian cohort", "indian population", "indian evidence", "indian demographic",
                "for indian", "india-specific", "indian genetic", "indian pharmacogenomic",
                "indian-cohort", "emphasis on indian"]),
    ("South Asian", ["south asian cohort", "south asian population", "south asian evidence",
                     "south asian genetic"]),
    ("East Asian", ["east asian cohort", "east asian population", "east asian evidence",
                    "east asian genetic"]),
    ("European", ["european cohort", "european population", "european evidence",
                  "european genetic"]),
    ("global", ["global cohort", "global population", "global evidence"]),
    ("mixed-cohort", ["mixed-cohort", "mixed cohort"]),
]

# ── Chemistry types ──────────────────────────────────────

_CHEMISTRY_TYPES: list[Tuple[str, list[str]]] = [
    ("kinase inhibitor", ["kinase inhibitor"]),
    ("allosteric modulator", ["allosteric modulator"]),
    ("covalent inhibitor", ["covalent inhibitor"]),
    ("fragment-like molecule", ["fragment-like molecule", "fragment-like"]),
    ("macrocycle", ["macrocycle"]),
    ("peptidomimetic", ["peptidomimetic"]),
    ("natural-product-like scaffold", ["natural-product-like", "natural product"]),
    ("CNS-penetrant small molecule", ["cns-penetrant", "cns penetrant", "brain-penetrant"]),
]


# ── Query type patterns ──────────────────────────────────

@dataclass
class QueryClassification:
    """Result of classifying a natural-language query."""
    query_type: str = "general"  # one of the 25 types
    disease: Optional[str] = None
    genes: List[str] = field(default_factory=list)
    pathways: List[str] = field(default_factory=list)
    cohort: Optional[str] = None
    chemistry_type: Optional[str] = None
    comparison_targets: List[str] = field(default_factory=list)  # for SynthArena
    runtime_mode: Optional[str] = None  # hosted/local/auto
    emphasis: List[str] = field(default_factory=list)  # sections to emphasize
    search_terms: List[str] = field(default_factory=list)  # additional search terms

    def to_dict(self):
        return {
            "query_type": self.query_type,
            "disease": self.disease,
            "genes": self.genes,
            "pathways": self.pathways,
            "cohort": self.cohort,
            "chemistry_type": self.chemistry_type,
            "comparison_targets": self.comparison_targets,
            "runtime_mode": self.runtime_mode,
            "emphasis": self.emphasis,
            "search_terms": self.search_terms,
        }


# ── Query type detection rules ───────────────────────────
# Ordered by specificity: most specific / lab-name patterns first,
# then broad section patterns, fallback at end

_QUERY_TYPE_RULES: list[Tuple[str, list[str], list[str]]] = [
    # ── Exact lab names & catch-all programs (highest priority) ──

    ("e2e_program", [
        "end-to-end", "complete scientific program",
        "full pipeline", "comprehensive workflow",
        "starting from scratch",
    ], ["all"]),

    ("autopilot", [
        "auto-pilot", "autopilot", "specialist handoff",
        "agentic.*execution", "autonomous execution",
    ], ["all"]),

    ("target_discovery_lab", [
        "target discovery lab", "network exploration",
        "interactome", "target network",
        "exploration-grade hypothes",
        "target discovery", "discover.*novel.*target",
        "target identification", "target validation",
        "identify.*novel.*target", "find.*novel.*target",
        "find.*new.*target", "uncover.*target", "screen.*target",
    ], ["target_prioritization", "graph", "pathway"]),

    ("molecule_lab", [
        "molecule generation lab", "molecule lab",
        "rl-guided proposal", "reinforcement loop.*optimize",
        "generative molecule", "de novo design",
        "de novo.*molecule", "generate.*molecule",
        "molecular generation", "novel.*molecule",
        "optimization trajectory",
    ], ["molecule", "admet", "structure"]),

    ("pocket_discovery", [
        "pocket discovery lab", "pocket discovery",
        "structure-guided screening",
        "orthosteric.*allosteric.*cryptic",
        "realistically designable",
        "druggable.*pocket", "binding.*pocket", "binding.*site",
        "allosteric.*site", "cryptic.*pocket", "pocket.*analysis",
        "druggability.*assessment", "binding.*groove",
    ], ["structure", "molecule"]),

    # ── Scenario and runtime (specific keywords) ──

    ("syntharena", [
        "syntharena", "compares a", "scenario comparison", "compare.*strategy",
        "-first strategy versus",
        "compare.*(?:-first|first).*(?:vs|versus)",
        r"\bvs\b.*\bvs\b|(?:-first|first).*(?:-first|first)",
    ], ["scenario_comparison", "target_prioritization", "contradiction"]),

    ("error_handling", [
        "degraded state", "degraded run", "error handling", "recovery path",
        "failed.*connector", "source.{0,15}(?:is |went |gone )?down(?!stream)",
        "timeout recovery", "simulate.*degraded", "degrades truthfully",
        "runtime disconnects", "disconnects mid",
        "timeout.*error", "api.*(?:returns?|throws?).*error",
        "what happens when.*(?:fail|error|timeout|down)",
    ], ["errors", "runtime", "provenance"]),

    ("runtime", [
        "run this analysis in hosted mode", "run this analysis in local mode",
        "run this analysis in auto mode", "runtime selected",
        "local or hosted inference", "runtime center", "model center",
        "switch.*(?:to |)(?:local|hosted|auto).*(?:mode|runtime)",
        "local runtime", "hosted runtime", "auto runtime",
        "run.*(?:on |)(?:my |)gpu", "gpu.*(?:mode|inference)",
    ], ["runtime", "provenance"]),

    # ── Population, vaccine, metabolic (specific domains) ──

    ("population_genomics", [
        "indian.*genetic evidence", "south asian.*genetic evidence",
        "pharmacogenomic consideration", "population-specific response",
        "assess whether.*strengthened or weakened",
        "variant frequencies.*population",
        "population.*(?:frequency|data|variant)",
        "population.*genomics", "pharmacogenomics",
        "gnomad", "indigen", "genomeasia",
        "allele.*frequency", "cohort.*frequency",
        "rs\\d+.*(?:across|frequency|population)",
    ], ["population_genomics", "target_prioritization", "disease"]),

    ("vaccine_epitope", [
        "vaccine", "epitope", "immunogen", "antigen design",
        "t-cell epitope", "b-cell epitope", "neoantigen",
    ], ["vaccine", "structure", "population_genomics"]),

    ("metabolic_engineering", [
        "metabolic engineering", "flux", "metabolic pathway",
        "biosynthetic", "fermentation",
        "metabolic flux", "flux balance",
        "pathway engineering", "metabolic network",
        "production.*pathway", "biosynthesis.*route",
        "enzyme engineering", "biocatal",
        "metabolic.*optimization", "yield.*optimization",
    ], ["metabolic", "pathway", "graph"]),

    # ── Research / dossier / error ──

    ("dossier", [
        "decision dossier", "generate.*dossier", "export.*dossier",
        "dossier readiness", "formal report", "create.*report",
        "compile.*dossier", "regulatory.*dossier", "target dossier",
    ], ["dossier", "export", "summary"]),

    ("research_loop", [
        "research loop", "autonomous.*research", "automl",
        "research cycle", "iterative research", "auto-research",
    ], ["research_loop", "evidence", "target_prioritization"]),

    # ── Structure (before evidence to avoid "structural evidence" false match) ──

    ("structure_pocket", [
        "structure and pocket context", "pocket mapping",
        "druggability.*(?:pocket|site|binding|map|assessment)",
        "druggable.*pocket", "candidate pocket",
        "experimental.*structure", "predicted.*structure",
        "alphafold.*structure", "3d structure",
        "open the structure", "pocket detection",
        "allosteric.*pocket", "pocket.*docking",
        "score druggability", "structural evidence",
    ], ["structure", "target_prioritization"]),

    # ── Evidence & literature (specific → broad to avoid false matches) ──

    ("translational_pico", [
        "translational research.*pico", "pico-style evidence",
        "intervention narrative", "mechanistic support.*human-outcome",
        "run translational research", r"\bpico\b",
    ], ["pico", "clinical_trials", "population_genomics"]),

    ("translation_research", [
        "translation research", "translational.*gap",
        "bench.to.bedside", "preclinical.*clinical",
        "clinical.*translation", "translational.*science",
        "translational.*medicine", "translational.*potential",
        "translational.*relevance", "animal.*model.*human",
        "preclinical.*finding", "clinical.*implication",
        "from.*lab.*clinic", "translational.*pathway",
        "biomarker.*translation", "therapeutic.*translation",
        "meaning.*preserv", "terminology drift",
    ], ["translation", "evidence", "pico"]),

    ("evidence_retrieval", [
        "search the literature", "public evidence source",
        "cluster the evidence by mechanism", "literature mining",
        "contradiction surfacing", "supporting and.*dissenting finding",
        "influence downstream prioritization",
        "clinical evidence", "summarize.*evidence", "review.*evidence",
        "literature.*review", "evidence.*(?:for|against|supporting)",
        "systematic review", "meta.analysis", "published.*(?:data|studies)",
    ], ["evidence", "contradiction", "summary"]),

    # ── Chemistry pipeline (retro → admet → design) ──

    ("retrosynthesis", [
        "retrosynthetic route", "retrosynthesis", "synthetic accessibility",
        "synthetic route", "commercially available precursor",
        "route bottleneck", "lab work needed",
    ], ["retrosynthesis", "admet", "molecule"]),

    ("admet", [
        "admet", "off-target screening", "herg", "cyp",
        "hepatotoxicity", "mutagenicity", "bbb concern",
        "compounds should advance.*optimized.*killed",
    ], ["admet", "molecule", "target_prioritization"]),

    ("design_studio", [
        "retrieve known active chemistry", "design set",
        "pharmacophore", "starting point", "scaffold",
        "pocket context.*separate retrieval",
        "retrieval-based candidates from generated",
        "design.?studio",
        "design.*(?:inhibitor|molecule|compound|drug|analog|ligand)",
        "lead optimization", "structure.activity relationship",
        r"\bsar\b", "optimize.*(?:selectivity|potency|affinity)",
        "improve.*(?:metabolic stability|bioavailability|potency)",
        "medicinal chemistry", "hit.to.lead",
        "fragment.based.*design",
    ], ["molecule", "structure", "admet"]),

    # ── Mapping, prioritization, disease (before structure) ──

    ("uniprot_mapping", [
        "audit all aliases", "outdated gene symbol",
        "protein accession.*pathway label", "identifier resolution",
        "resolved each identifier", "ambiguous.*mapping",
        "canonical ids", "uniprot", "isoform",
        "signal peptide", "post-translational",
        "active site.*annotation", "map.*(?:to its|entry|record)",
    ], ["entity_normalization", "target_prioritization"]),

    ("target_prioritization", [
        "prioritize target", "target prioritization", "target-scoring",
        "composite.*scor", "score component", "rank.*target.*(?:by|score|composite)",
        "rank.*(?:as|the).*target", "rank.*vs.*(?:as|for).*target",
        "robust versus speculative", "explainable ranking",
        "genetics.*pathway centrality.*literature",
        "seven-signal", "scoring model", "scoring pipeline",
        "druggability.*signal", "druggability.*score",
        "evaluate.*(?:as|versus|vs).*target",
    ], ["target_prioritization", "disease", "graph"]),

    ("disease_intelligence", [
        "run disease intelligence", "disease intelligence",
        "disease normalization",
        "ontology normalization", "disease identifier.*synonym",
        "disease-gene evidence", "target-ready disease summary",
        "aggregate disease", "unresolved mapping",
        "epidemiology", "unmet.*(?:medical |clinical )?need",
        "standard of care", "genetic risk.*loci",
        "disease.*summary", "disease.*profile",
        "disease.*mechanism", "pathogenesis", "etiology",
        "pathophysiology", "molecular basis.*disease",
        "disease.*(?:biology|landscape|overview)",
    ], ["disease", "entity_normalization", "target_prioritization"]),

    # ── Knowledge graph ──

    ("knowledge_graph", [
        "evidence-backed knowledge graph", "knowledge graph",
        "build.*graph", "graph.*around",
        "expand two hops", "bridge protein", "disease-specific rewiring",
        "graph findings.*ranking", "pathway analysis",
        "gene-gene.*edge", "gene-pathway.*edge",
        "interactor", "interaction network", "protein.*interaction",
        "kinase.substrate", "signaling.*cascade", "signaling.*network",
        "pathway crosstalk",
        "map.*through.*relationship", "regulatory.*network",
        "downstream.*target", "upstream.*regulator",
        "network.*topology", "hub.*gene", "network pharmacology",
        "how.*pathway.*(?:drive|mediate|cause|contribute)",
        "pathway.*(?:drive|mediate).*resist",
    ], ["graph", "pathway", "target_prioritization"]),

    # ── Fallback cockpit ──

    ("cockpit_resume", [
        "resume my project", "most relevant prior evidence",
        "what changed since my last session",
        "what action.*take next", "project memory",
        "context continuity",
    ], ["summary", "evidence", "target_prioritization", "contradiction"]),
]


def classify_query(query: str) -> QueryClassification:
    """Classify a natural-language query into structured intent.

    Returns a QueryClassification with extracted disease, genes,
    pathways, cohort, and module emphasis.
    """
    result = QueryClassification()
    q_lower = query.lower()

    # ── Extract disease ──────────────────────────────────
    for canonical, aliases in _DISEASE_MAP:
        for alias in aliases:
            if alias in q_lower:
                result.disease = canonical
                result.search_terms.append(canonical)
                break
        if result.disease:
            break

    # Fallback: check short disease abbreviations with word boundaries
    if not result.disease:
        _SHORT_ABBREVS = [
            (r"\btnbc\b", "triple-negative breast cancer"),
            (r"\bt2dm?\b", "Type 2 diabetes mellitus"),
            (r"\bnsclc\b", "non-small cell lung cancer"),
            (r"\bgbm\b", "glioblastoma"),
            (r"\bhcc\b", "hepatocellular carcinoma"),
            (r"\buc\b", "ulcerative colitis"),
            (r"\b(?:^|\W)ra(?:\W|$)", "rheumatoid arthritis"),
            (r"\bad\b", "Alzheimer's disease"),
        ]
        for pat, canonical in _SHORT_ABBREVS:
            if re.search(pat, query, re.IGNORECASE):
                result.disease = canonical
                result.search_terms.append(canonical)
                break

    # ── Extract gene symbols ─────────────────────────────
    # Use word boundary matching for gene symbols
    for gene in _GENE_SYMBOLS:
        pattern = rf"\b{re.escape(gene)}\b"
        if re.search(pattern, query, re.IGNORECASE):
            if gene not in result.genes:
                result.genes.append(gene)

    # Handle "GENE/N" shorthand (e.g. "CDK4/6" → CDK4 + CDK6)
    for m in re.finditer(r"\b([A-Z][A-Z0-9]+)(\d+)/(\d+)\b", query):
        prefix, n1, n2 = m.group(1), m.group(2), m.group(3)
        for suffix in (n1, n2):
            sym = prefix + suffix
            if sym in _GENE_SYMBOLS_SET and sym not in result.genes:
                result.genes.append(sym)

    # Handle mutation-appended gene names (e.g. "KRASG12C" → KRAS, "BRAFV600E" → BRAF)
    for m in re.finditer(r"\b([A-Z][A-Z0-9]+?)([A-Z]\d+[A-Z])\b", query):
        sym = m.group(1)
        if sym in _GENE_SYMBOLS_SET and sym not in result.genes:
            result.genes.append(sym)

    # ── Extract pathways ─────────────────────────────────
    for canonical, aliases in _PATHWAY_MAP:
        for alias in aliases:
            if alias in q_lower:
                result.pathways.append(canonical)
                result.search_terms.append(canonical)
                break

    # ── Extract cohort ───────────────────────────────────
    for cohort_name, patterns in _COHORT_PATTERNS:
        for pat in patterns:
            if pat in q_lower:
                result.cohort = cohort_name
                break
        if result.cohort:
            break

    # ── Extract chemistry type ───────────────────────────
    for chem_name, patterns in _CHEMISTRY_TYPES:
        for pat in patterns:
            if pat in q_lower:
                result.chemistry_type = chem_name
                break
        if result.chemistry_type:
            break

    # ── Extract comparison targets (SynthArena) ──────────
    synth_match = re.search(
        r"compares?\s+a?\s*(\w+)-first\s+strategy\s+versus\s+a?\s*(\w+)-first",
        query, re.IGNORECASE,
    )
    if synth_match:
        result.comparison_targets = [synth_match.group(1), synth_match.group(2)]

    # ── Extract runtime mode ─────────────────────────────
    runtime_match = re.search(
        r"\bin\s+(hosted|local|auto)\s+mode\b", query, re.IGNORECASE,
    )
    if runtime_match:
        result.runtime_mode = runtime_match.group(1).lower()

    # ── Detect query type ────────────────────────────────
    for qtype, patterns, emphasis in _QUERY_TYPE_RULES:
        for pat in patterns:
            try:
                if re.search(pat, q_lower):
                    result.query_type = qtype
                    result.emphasis = emphasis
                    break
            except re.error:
                if pat in q_lower:
                    result.query_type = qtype
                    result.emphasis = emphasis
                    break
        if result.query_type != "general":
            break

    # ── Fallback: if disease found but no type, default cockpit ──
    if result.query_type == "general" and result.disease:
        result.query_type = "cockpit_resume"
        result.emphasis = ["summary", "evidence", "target_prioritization"]

    # ── Build search terms ───────────────────────────────
    if not result.search_terms:
        if result.disease:
            result.search_terms.append(result.disease)
        if result.genes:
            result.search_terms.extend(result.genes[:3])

    return result


def get_search_query(classification: QueryClassification, original_query: str) -> str:
    """Build optimized search query from classification.

    For gene-specific queries, combines gene + disease for targeted results.
    For disease-only queries, uses the disease name.
    """
    parts = []

    if classification.disease:
        parts.append(classification.disease)

    if classification.genes:
        parts.extend(classification.genes[:3])

    if classification.pathways:
        parts.extend(classification.pathways[:2])

    if classification.cohort and classification.cohort not in ("global", "mixed-cohort"):
        parts.append(classification.cohort)

    if parts:
        return " ".join(parts)

    # Fallback: use original query but strip long instructional text
    # Take first meaningful phrase before commas
    short = original_query.split(",")[0].strip()
    if len(short) > 100:
        short = " ".join(short.split()[:15])
    return short


def get_summary_prompt_context(classification: QueryClassification) -> str:
    """Generate context injection for the LLM summary prompt based on query type."""

    ctx_parts = []

    if classification.query_type == "cockpit_resume":
        ctx_parts.append("FOCUS: Project status, evidence changes, unresolved contradictions, actionable next steps.")
    elif classification.query_type == "evidence_retrieval":
        ctx_parts.append("FOCUS: Cluster evidence by mechanism, highlight contradictions, extract 5 strongest supporting + 5 dissenting findings, assess source reliability.")
    elif classification.query_type == "disease_intelligence":
        ctx_parts.append("FOCUS: Disease normalization (IDs, synonyms), disease-gene evidence aggregation, candidate gene→protein mapping, unresolved mappings, target-ready summary.")
    elif classification.query_type == "uniprot_mapping":
        ctx_parts.append("FOCUS: Identifier audit — aliases, outdated symbols, accessions, pathway labels. Show resolution chain, flag ambiguities, identify consuming modules.")
    elif classification.query_type == "target_prioritization":
        ctx_parts.append("FOCUS: Composite target scoring with 7 signals (GWAS, druggability, pathway centrality, expression, novelty, safety, literature). Explain each score, surface contradictions, classify robust vs speculative.")
    elif classification.query_type == "knowledge_graph":
        ctx_parts.append("FOCUS: Evidence-backed knowledge graph, 2-hop expansion from top targets, bridge proteins, contradiction-heavy edges, disease-specific rewiring. Explain graph impact on ranking.")
    elif classification.query_type == "structure_pocket":
        ctx_parts.append("FOCUS: Experimental vs predicted structures, pocket detection, druggability scoring, confidence intervals. Assess ligand discovery viability.")
    elif classification.query_type == "design_studio":
        ctx_parts.append("FOCUS: Known active chemistry retrieval, diverse starting points, pocket-conditioned design, pharmacophore preservation. Separate retrieval-based vs generated candidates.")
    elif classification.query_type == "admet":
        ctx_parts.append("FOCUS: Multi-task ADMET screening (hERG, CYP, hepatotoxicity, mutagenicity, BBB), uncertainty quantification. Classify: advance / optimize / kill.")
    elif classification.query_type == "retrosynthesis":
        ctx_parts.append("FOCUS: Synthetic accessibility estimation, retrosynthetic routes, challenging steps, commercially available precursors, route bottlenecks, minimum lab validation.")
    elif classification.query_type == "translation_research":
        ctx_parts.append("FOCUS: Meaning-preserving evidence transformation, terminology drift prevention, traceable summaries, side-by-side interpretation vs original.")
    elif classification.query_type == "translational_pico":
        ctx_parts.append("FOCUS: PICO-style evidence extraction, intervention comparison, mechanistic vs human-outcome support separation, population-specific recommendation changes.")
    elif classification.query_type == "population_genomics":
        ctx_parts.append("FOCUS: Indian/South Asian genetic evidence assessment for specific target, variant frequencies, pharmacogenomic considerations, population-specific response patterns, ranking impact.")
    elif classification.query_type == "syntharena":
        ctx_parts.append("FOCUS: Strategy comparison (target A vs target B), evidence scoring, tractability, translational plausibility, risk/uncertainty, population context. Determine stronger scientific program.")

    if classification.cohort:
        ctx_parts.append(f"POPULATION EMPHASIS: {classification.cohort} cohort data should be prioritized where available.")

    if classification.genes:
        ctx_parts.append(f"SPECIFIC GENE(S): {', '.join(classification.genes)} — provide gene-specific analysis.")

    if classification.pathways:
        ctx_parts.append(f"PATHWAY FOCUS: {', '.join(classification.pathways)} signaling.")

    if classification.chemistry_type:
        ctx_parts.append(f"CHEMISTRY CLASS: {classification.chemistry_type}.")

    return "\n".join(ctx_parts) if ctx_parts else ""

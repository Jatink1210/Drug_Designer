# Requirements Document — Drug Designer Codebase Alignment

## Introduction

The Drug Designer platform has extensive scaffolding (~68 frontend pages, ~47 backend routers, ~158 connectors) but is only 30-40% functionally complete. A comprehensive gap analysis comparing the codebase against the Drug_Designer.md master specification (11,350 lines) revealed 12 critical functional gaps. This document defines each gap with exhaustive detail: what the end user sees, what the backend produces, what data is included, and the best implementation approach.

Prior specs (drug-designer-product-alignment, platform-polish-and-improvements) addressed initial wiring and UI polish. This spec targets the remaining deep functional gaps that prevent the platform from being a real scientific tool.

## Glossary

- **NLP_Contradiction_Engine**: `apps/api/services/nlp_contradiction_engine.py` — PubMedBERT embeddings + BioNLI for semantic contradiction detection
- **Contradiction_Detector**: `apps/api/services/contradiction_detector.py` — Main entry point for contradiction and similarity analysis
- **Similarity_Analyzer**: `apps/api/services/similarity_analyzer.py` — Clusters evidence items by semantic similarity
- **PICO_Extractor**: `apps/api/services/pico_extractor.py` — Extracts Population, Intervention, Comparison, Outcome from literature
- **Research_Lab**: One of 8 labs: Target Discovery, Pocket Detection, Molecule Generation, ADMET, Retrosynthesis, Vaccine, Metabolic Engineering, Pharmacogenomics
- **Knowledge_Graph**: Interactive force-directed graph rendered by `ForceGraph.tsx`
- **ENTITY_COLORS**: Canonical color map in `entityColors.ts` — protein=#7c3aed, gene=#6366f1, disease=#dc2626, drug=#e11d48, compound=#d97706, pathway=#0891b2, publication=#3b82f6, clinical_trial=#059669, variant=#ea580c
- **Entity_Detail_Page**: Drawer/modal showing AI overview, publications, patents, clinical trials, related entities, action buttons
- **Pathway_Explorer**: `BiologicalPathwayWorkbench` component rendering interactive pathway diagrams
- **Structure_Viewer**: Mol*-based 3D viewer in `StructurePage.tsx`
- **Clinical_Workflow**: 10-step sequential clinical design workflow
- **SynthArena**: Drug candidate comparison arena with scoring, debate, dossier generation
- **Debate_Engine**: Multi-agent debate simulation within SynthArena
- **Decision_Dossier**: AI-generated document with evidence backing and provenance
- **WebSocket_Manager**: `core/websocket_manager.py` managing real-time progress events
- **Provenance_Chain**: Metadata tracking sources queried, succeeded, and degraded
- **Response_Envelope**: Universal API wrapper with status, data, provenance, timing
- **Handoff_Payload**: Structured data passed between pages to preserve context
- **ForceGraph**: `ForceGraph.tsx` WebGL-accelerated graph component
- **Connector**: Backend module in `apps/api/connectors/` fetching from external scientific APIs

## Requirements

### Requirement 1: Biomedical NLP Engine Pipeline Integration

**User Story:** As a biomedical researcher, I want contradiction and similarity detection to use semantic NLP (PubMedBERT + BioNLI) as the primary method with keyword fallback, so that nuanced contradictions in the literature are accurately identified.

**Frontend Expected Outcome:**
- Contradictions page shows a method badge on each card: "NLP" (purple) or "Keyword" (gray) indicating which detection method produced the result
- Each contradiction card displays a confidence percentage (0-100%) derived from the NLI model probability
- Similarity clusters show cosine similarity scores (e.g., "87% similar") instead of Jaccard overlap
- PICO extraction page shows extracted elements with entity type highlighting (Population in blue, Intervention in green, Comparison in orange, Outcome in purple)
- A banner at the top of the Contradictions page shows "Analysis method: Biomedical NLP (PubMedBERT + BioNLI)" or "Analysis method: Keyword Heuristic (NLP models unavailable)"

**Backend Expected Outcome:**
- `analyze_contradictions_and_similarities()` in contradiction_detector.py calls `get_nlp_engine().classify_pair()` as PRIMARY method for every claim pair
- NLP engine lazy-loads PubMedBERT (`microsoft/BiomedNLP-BiomedBERT-base-uncased-abstract-fulltext`) via sentence-transformers and BioNLI (`microsoft/BiomedNLI`) via transformers pipeline on first call
- When models unavailable, falls back to keyword heuristic and sets `method: "keyword_fallback"` in response
- Similarity clustering uses cosine similarity on PubMedBERT embeddings (threshold 0.7) instead of Jaccard
- PICO extraction uses spaCy biomedical NER (`en_core_sci_sm`) when available, regex patterns as fallback

**Data Included in Response:**
```json
{
  "contradictions": [{
    "claim_a": "string (max 200 chars)",
    "claim_b": "string (max 200 chars)",
    "source_a": {"source": "PubMed", "external_id": "PMID:12345", "title": "...", "year": 2024, "url": "..."},
    "source_b": {"source": "OpenTargets", "external_id": "...", "title": "...", "year": 2023, "url": "..."},
    "nli_result": {"label": "contradiction", "confidence": 0.87, "method": "nli_model"},
    "contradiction_type": "directional|temporal|magnitude|causal",
    "severity": "high|medium|low",
    "confidence": 0.82,
    "context_a": {"study_type": "in_vivo", "model_organisms": ["mouse"], "cell_lines": [], "methodologies": ["western blot"]},
    "context_b": {"study_type": "clinical", "model_organisms": [], "cell_lines": [], "methodologies": ["RCT"]},
    "temporal_note": "Source B is 2 years newer. The newer finding may reflect evolving understanding.",
    "resolution_suggestion": "Review experimental conditions..."
  }],
  "similarities": [{
    "cluster_id": "sim_0",
    "members": [{"text": "...", "source_db": "PubMed", "entity_name": "BRCA1"}],
    "member_count": 3,
    "similarity_score": 0.87,
    "relationship_type": "shared_finding|complementary_evidence",
    "shared_entities": ["BRCA1", "TP53"],
    "representative_summary": "...",
    "consensus_strength": "strong|moderate|weak"
  }],
  "evidence_landscape": {"total_sources_analyzed": 25, "overall_consensus": "moderate"},
  "method_used": "nlp|keyword_fallback"
}
```

**Best Implementation Approach:**
- The nlp_contradiction_engine.py already has the correct class structure with lazy loading, compute_similarity(), classify_pair(), extract_context(), and compute_confidence()
- Integration point: contradiction_detector.py's `analyze_contradictions_and_similarities()` already calls `get_nlp_engine()` — verify the NLP engine is initialized with `await engine.initialize()` before first use
- The similarity_analyzer.py already uses the NLP engine — verify it's wired into the contradiction_detector's `_find_similarity_clusters()`
- For PICO: enhance pico_extractor.py to try loading `en_core_sci_sm` spaCy model, fall back to regex patterns
- Add `sentence-transformers` and `transformers` to requirements.txt if not present

#### Acceptance Criteria

1. WHEN the Contradiction_Detector analyzes claims, THE system SHALL call NLP_Contradiction_Engine.classify_pair() as the primary classification method, falling back to keyword heuristic only when NLP models are unavailable
2. WHEN the NLP_Contradiction_Engine initializes, THE system SHALL lazy-load PubMedBERT and BioNLI models and set an _available flag; IF loading fails, THE system SHALL log the error and set _available=False without crashing
3. WHEN two claims are classified, THE NLI result SHALL include label (entailment/contradiction/neutral), confidence (0.0-1.0), and method (nli_model/keyword_heuristic)
4. WHEN the Similarity_Analyzer clusters evidence, THE system SHALL use cosine similarity on PubMedBERT embeddings with configurable threshold (default 0.7)
5. WHEN the PICO_Extractor processes literature, THE system SHALL use biomedical NER for entity extraction when spaCy en_core_sci_sm is available, falling back to regex patterns
6. WHEN the Contradictions page renders results, THE UI SHALL display a method badge (NLP/Keyword), confidence percentage, and experimental context for each contradiction
7. WHEN the analysis response is returned, THE response SHALL include a top-level method_used field indicating "nlp" or "keyword_fallback"


### Requirement 2: Research Labs Real Computation

**User Story:** As a computational biologist, I want all 8 research labs to perform real computation using actual connectors and scientific algorithms, so that I receive actionable results instead of degraded placeholder responses.

**Frontend Expected Outcome:**
- Each lab page (TargetDiscoveryLabPage, PocketLabPage, MoleculeGenerationLabPage, AdmetPanels, RetrosynthesisPage, VaccineLabPage, MetabolicEngineeringLabPage, PharmacogenomicsLabPage) shows real computation results in structured tables and visualizations
- Results include data tables with sortable columns, score breakdowns, and provenance indicators
- No "degraded — tool not available" messages for core functionality
- Each result card shows which APIs/tools were used (e.g., "Sources: OpenTargets, DisGeNET, UniProt")
- Loading states show real progress ("Querying OpenTargets... Querying DisGeNET... Computing scores...")

**Backend Expected Outcome:**
- Target Discovery: Calls OpenTargets (`/api/v1/labs/target-discovery/start`) → queries OpenTargets, DisGeNET, UniProt connectors in parallel → scores targets using TargetScorer → returns ranked targets with PPI network data
- Pocket Detection: Calls fpocket binary on downloaded PDB file → parses pocket output → ranks by druggability score → returns pocket list with 3D coordinates
- Molecule Generation: Uses DLModelService diffusion model → generates candidate molecules → computes RDKit descriptors → returns SMILES + properties
- ADMET: Uses ADMETPredictor with RDKit descriptors → computes absorption, distribution, metabolism, excretion, toxicity → returns predictions with conformal intervals
- Retrosynthesis: Uses RDKit RECAP decomposition → identifies retrosynthetic routes → scores feasibility → returns route trees
- Vaccine: Analyzes antigen sequence → predicts B-cell/T-cell epitopes using sliding window + hydrophilicity → returns ranked candidates
- Metabolic Engineering: Performs stoichiometric flux analysis → identifies bottleneck reactions → suggests pathway modifications
- Pharmacogenomics: Queries PharmGKB + CPIC connectors → returns gene-drug interactions, variant annotations, dosing recommendations

**Data Included in Response (per lab):**
```json
{
  "run_id": "uuid",
  "lab_type": "target-discovery",
  "status": "success|degraded|error",
  "artifacts": [/* lab-specific structured data */],
  "provenance": {
    "sources_queried": ["OpenTargets", "DisGeNET", "UniProt"],
    "sources_succeeded": ["OpenTargets", "UniProt"],
    "sources_degraded": ["DisGeNET"],
    "computation_time_ms": 4500
  },
  "warnings": ["DisGeNET returned partial results due to rate limiting"]
}
```

**Best Implementation Approach:**
- The inline functions in labs.py (`_inline_target_discovery`, `_inline_admet`, etc.) already exist — enhance each to call real connectors via asyncio.gather
- For Target Discovery: use existing TargetScorer service + OpenTargets/DisGeNET/UniProt connectors
- For Pocket Detection: use existing DockingService.detect_pockets() which already calls fpocket
- For ADMET: use existing ADMETPredictor in molecule_service.py which already computes RDKit descriptors
- For Retrosynthesis: use existing RDKit RECAP decomposition in _inline_retrosynthesis
- For Vaccine/MetabolicEng/Pharmacogenomics: implement lightweight computation using sequence analysis, stoichiometric models, and PharmGKB/CPIC connectors

#### Acceptance Criteria

1. WHEN a Target Discovery lab run is submitted, THE system SHALL query OpenTargets, DisGeNET, and UniProt connectors and return ranked targets with composite scores and a PPI network
2. WHEN a Pocket Detection lab run is submitted with a PDB ID, THE system SHALL execute fpocket or p2rank and return detected pockets with druggability scores, residue lists, and center coordinates
3. WHEN a Molecule Generation lab run is submitted, THE system SHALL generate candidate molecules using the diffusion model or RDKit enumeration and return SMILES with predicted properties
4. WHEN an ADMET lab run is submitted with SMILES strings, THE system SHALL compute ADMET predictions using RDKit descriptors with conformal prediction confidence intervals
5. WHEN a Retrosynthesis lab run is submitted, THE system SHALL decompose the molecule using RDKit RECAP and return synthesis routes with feasibility scores
6. WHEN a Vaccine Design lab run is submitted, THE system SHALL predict epitopes using sequence analysis and return ranked vaccine candidates
7. WHEN a Metabolic Engineering lab run is submitted, THE system SHALL perform stoichiometric analysis and return optimized pathway modifications
8. WHEN a Pharmacogenomics lab run is submitted, THE system SHALL query PharmGKB and CPIC and return gene-drug interactions with dosing recommendations
9. WHEN any lab run completes, THE response SHALL include a Provenance_Chain listing all sources queried and their response status
10. IF a required tool is unavailable, THE system SHALL return a structured error with the dependency name, installation instructions, and a degraded result using available alternatives

### Requirement 3: Knowledge Graph Edge Interactivity and Node Coloring

**User Story:** As a researcher, I want knowledge graph nodes colored by entity type and edges that show connection reasons with evidence when clicked, so that I can visually distinguish entity types and understand why nodes are connected.

**Frontend Expected Outcome:**
- Every node in the ForceGraph is colored according to ENTITY_COLORS: protein=#7c3aed (purple), gene=#6366f1 (indigo), disease=#dc2626 (red), drug=#e11d48 (rose), compound=#d97706 (amber), pathway=#0891b2 (cyan), publication=#3b82f6 (blue), clinical_trial=#059669 (emerald), variant=#ea580c (orange)
- Node size is proportional to betweenness centrality (larger = more central)
- Clicking an edge opens a detail panel showing: relationship type, human-readable reason, list of evidence items with source links, provenance info
- Edges are styled by relationship type (solid for direct, dashed for inferred)
- PPI Network mode shows protein-protein interactions with confidence threshold slider

**Backend Expected Outcome:**
- `POST /api/v1/graph/build` returns nodes with `color` field set from ENTITY_COLORS[node.type] and `size` field computed from betweenness centrality
- Every edge includes: `reason` (non-empty string), `evidence_ids` (at least one), `relationship_type`, `source_db`, `confidence`
- `GET /api/v1/graph/edge/{edge_id}` returns full evidence items for the edge

**Data Included:**
```json
{
  "nodes": [{
    "id": "BRCA1", "label": "BRCA1", "type": "gene",
    "color": "#6366f1", "size": 1.8,
    "metadata": {"uniprot_id": "P38398", "description": "..."}
  }],
  "edges": [{
    "source": "BRCA1", "target": "TP53", "label": "interacts_with",
    "weight": 0.95, "reason": "Physical protein-protein interaction confirmed by co-immunoprecipitation",
    "evidence_ids": ["ev_001", "ev_002"], "relationship_type": "physical_interaction",
    "source_db": "STRING", "confidence": 0.95
  }]
}
```

**Best Implementation Approach:**
- The ForceGraph.tsx component already renders nodes and handles edge clicks — add color prop from node data and size prop from centrality
- The graph_service.py already builds graphs — enhance edge construction to populate reason and evidence_ids from connector data
- The entityColors.ts already defines ENTITY_COLORS — import and apply in ForceGraph rendering
- Add a centrality computation step using networkx betweenness_centrality() on the graph before returning

#### Acceptance Criteria

1. WHEN a Knowledge_Graph is rendered, every node SHALL be colored according to ENTITY_COLORS[node.type] with the exact hex values defined in the glossary
2. WHEN a Knowledge_Graph is rendered, node sizes SHALL be computed from betweenness centrality scores (size = 0.5 + centrality * 2.0)
3. WHEN a researcher clicks a Knowledge_Graph edge, THE UI SHALL display a detail panel with the connection reason, relationship type, evidence items, and source provenance
4. WHEN a Knowledge_Graph is constructed, every edge SHALL have a non-empty reason field and at least one evidence_id
5. WHEN the Knowledge_Graph is in PPI Network mode, edges SHALL show confidence scores and interaction type labels

### Requirement 4: Entity Detail Pages

**User Story:** As a researcher, I want to click on any entity and see a comprehensive detail page with AI overview, publications, patents, clinical trials, related entities, and action buttons, so that I can deeply explore any entity from any context in the platform.

**Frontend Expected Outcome:**
- Clicking any entity name (in Cockpit results, KG nodes, entity tables, pathway nodes) opens an EntityDetailDrawer (right-side drawer, 400px wide)
- The drawer has tabs: Overview, Publications, Clinical Trials, Related Entities, Actions
- Overview tab: 2-3 paragraph AI-generated summary of the entity, key identifiers (UniProt, ChEMBL, MONDO, etc.), entity type badge
- Publications tab: Table of papers from PubMed with title, authors, journal, year, PMID link — sortable by year and relevance
- Clinical Trials tab: Table from ClinicalTrials.gov with NCT ID, title, phase, status, conditions — filterable by phase
- Related Entities tab: List of connected entities from the KG with relationship type and confidence
- Actions bar: Buttons "View Structure" → /structure, "Run in Design Studio" → /design, "Add to SynthArena" → /syntharena, "Explore in KG" → /graph — each builds a Handoff_Payload

**Backend Expected Outcome:**
- `GET /api/v1/cockpit/entity/{entity_id}` returns all detail data
- Calls PubMed, ClinicalTrials, and graph connectors in parallel via asyncio.gather
- AI overview generated by LLM if available, otherwise structured summary from connector data
- Response cached for 30 minutes per entity_id

**Data Included:**
```json
{
  "entity_id": "BRCA1", "entity_type": "gene", "entity_name": "BRCA1",
  "identifiers": {"uniprot": "P38398", "ensembl": "ENSG00000012048", "hgnc": "1100"},
  "ai_overview": "BRCA1 (Breast Cancer Type 1 Susceptibility Protein) is a tumor suppressor...",
  "publications": [{"title": "...", "authors": "...", "journal": "Nature", "year": 2024, "pmid": "12345678", "abstract": "..."}],
  "clinical_trials": [{"nct_id": "NCT12345678", "title": "...", "phase": "Phase 3", "status": "Recruiting", "conditions": ["Breast Cancer"]}],
  "related_entities": [{"entity_id": "TP53", "entity_type": "gene", "entity_name": "TP53", "relationship": "interacts_with", "confidence": 0.95}],
  "actions": [
    {"action_id": "view_structure", "label": "View Structure", "target_route": "/structure", "enabled": true},
    {"action_id": "run_design", "label": "Run in Design Studio", "target_route": "/design", "enabled": true},
    {"action_id": "add_syntharena", "label": "Add to SynthArena", "target_route": "/syntharena", "enabled": true},
    {"action_id": "explore_kg", "label": "Explore in KG", "target_route": "/graph", "enabled": true}
  ]
}
```

**Best Implementation Approach:**
- The cockpit.py router already has an entity endpoint — enhance it to call connectors in parallel
- Create `apps/web/src/components/entity/EntityDetailDrawer.tsx` as a reusable drawer component
- Wire the drawer into WorkspacePage, KGPage, EntityIntelligence, and PathwaysPage via a shared context or callback
- Use the existing Handoff_Payload system (persistCockpitHandoff) for action button navigation

#### Acceptance Criteria

1. WHEN a researcher clicks an entity in Cockpit results, THE application SHALL open an EntityDetailDrawer with AI overview, publications, clinical trials, related entities, and action buttons
2. WHEN the Publications tab is shown, THE system SHALL fetch from PubMed and display title, authors, journal, year, and PMID link
3. WHEN the Clinical Trials tab is shown, THE system SHALL fetch from ClinicalTrials.gov and display NCT ID, title, phase, status, and conditions
4. WHEN an action button is clicked, THE system SHALL build a Handoff_Payload with the entity context and navigate to the target page
5. WHEN an entity is clicked in the Knowledge_Graph, THE same EntityDetailDrawer SHALL open with the same content
6. WHEN the entity detail endpoint is called, THE backend SHALL call PubMed, ClinicalTrials, and graph connectors in parallel and return within 5 seconds

### Requirement 5: Pathway Source Attribution and Interactivity

**User Story:** As a researcher, I want pathway nodes and edges to be clickable with source attribution showing which database each element came from, so that I can trace every pathway element to its origin.

**Frontend Expected Outcome:**
- Each pathway node in BiologicalPathwayWorkbench shows a small colored dot indicating source: KEGG=emerald, Reactome=indigo, WikiPathways=purple
- Clicking a node opens a popover with: node name, biological role/function, source database name + link to original, evidence items
- Clicking an edge opens a popover with: connection type (activation/inhibition/phosphorylation/binding/catalysis), mechanism description, source attribution
- Disease-affected nodes highlighted with red border, therapeutic targets with green border
- A legend at the bottom shows source color coding

**Backend Expected Outcome:**
- Pathway detail endpoint returns nodes with `source_db`, `source_url`, `explanation`, `evidence[]` fields
- Pathway edges include `type`, `source_db`, `explanation`, `evidence[]` fields
- Disease context endpoint returns `rewired_genes[]` and `therapeutic_targets[]`

**Data Included:**
```json
{
  "pathway_id": "R-HSA-109582", "name": "Hemostasis", "source": "Reactome",
  "nodes": [{
    "id": "n1", "label": "BRCA1", "type": "gene",
    "source_db": "Reactome", "source_url": "https://reactome.org/content/detail/R-HSA-109582",
    "explanation": "BRCA1 participates in DNA damage response within this pathway",
    "evidence": [{"source": "Reactome", "id": "R-HSA-109582", "title": "Hemostasis pathway"}]
  }],
  "edges": [{
    "source": "n1", "target": "n2", "type": "activation",
    "source_db": "Reactome", "explanation": "BRCA1 activates RAD51 for homologous recombination",
    "evidence": [{"source": "PubMed", "pmid": "12345", "title": "..."}]
  }],
  "disease_context": {
    "rewired_genes": ["BRCA1", "TP53"],
    "therapeutic_targets": ["PARP1"]
  }
}
```

**Best Implementation Approach:**
- Enhance Reactome/KEGG/WikiPathways connectors to return source_db and source_url metadata with each node/edge
- The BiologicalPathwayWorkbench already renders nodes with click handlers — enhance to show popovers with metadata
- The disease-context endpoint already exists — enhance to return real rewired_genes from DisGeNET/OpenTargets

#### Acceptance Criteria

1. WHEN a pathway node is clicked, THE UI SHALL show a popover with node name, biological role, source database, source URL, and evidence items
2. WHEN a pathway edge is clicked, THE UI SHALL show a popover with connection type, mechanism description, source attribution, and evidence
3. WHEN a pathway is rendered, THE UI SHALL display source database indicators on each node
4. WHEN disease context is available, THE UI SHALL highlight affected nodes with red borders and therapeutic targets with green borders
5. WHEN pathway data comes from multiple sources, each node and edge SHALL show which database it originated from

### Requirement 6: 3D Structure Viewer Completeness

**User Story:** As a structural biologist, I want the 3D structure viewer with 7 sub-tabs, ESM/AlphaFold/RCSB fallback chain, and Import to Design Studio, so that I can comprehensively analyze protein structures.

**Frontend Expected Outcome:**
- StructurePage shows 7 sub-tabs: Summary, 3D Structure, Binding Sites, Annotations, Sequence, Genome, Comparison
- Summary: Protein name, organism, function, gene name, sequence length, resolution, confidence (pLDDT for predicted)
- 3D Structure: Mol* viewer with representation controls (cartoon, ball-and-stick, surface, ribbon) and color schemes (chain, residue, bfactor, hydrophobicity)
- Binding Sites: Table of pockets ranked by druggability score with residue lists, center coordinates, volume, source
- Annotations: Domain annotations, PTMs, active sites, disulfide bonds from UniProt/InterPro
- Sequence: Amino acid sequence with secondary structure coloring, residue selection highlights in 3D
- Genome: Genomic context (chromosome, position, gene structure)
- Comparison: Side-by-side two-structure comparison with RMSD
- "Import to Design Studio" button builds Handoff_Payload with target_id, binding_site, structure_source

**Backend Expected Outcome:**
- `GET /api/v1/structure/{target_id}` fetches from ESM first, then AlphaFold, then RCSB PDB
- Returns structure data, binding sites, annotations, sequence, genome context
- Binding sites detected via fpocket if available

**Best Implementation Approach:**
- StructurePage.tsx already has basic Mol* viewer — add 7 sub-tab components
- structure_service.py already fetches from RCSB and AlphaFold — add ESM API with fallback chain
- Use existing MolstarViewer component for 3D rendering

#### Acceptance Criteria

1. THE Structure_Viewer SHALL display 7 sub-tabs: Summary, 3D Structure, Binding Sites, Annotations, Sequence, Genome, Comparison
2. WHEN a protein ID is provided, THE system SHALL fetch from ESM first, AlphaFold second, RCSB PDB third as fallback
3. WHEN Binding Sites tab is shown, pockets SHALL be ranked by druggability score descending
4. WHEN "Import to Design Studio" is clicked, THE system SHALL build a Handoff_Payload and navigate to /design
5. IF ESM fails, THE system SHALL fall back to AlphaFold; IF AlphaFold fails, fall back to RCSB PDB with degraded indicator

### Requirement 7: Clinical Design Workflow Enforcement

**User Story:** As a clinical researcher, I want the 10-step clinical workflow to enforce sequential completion with evidence backing, so that every decision is traceable.

**Frontend Expected Outcome:**
- Vertical stepper with 10 numbered steps, completed=green checkmark, current=highlighted, future=grayed/disabled
- Each step has input fields, evidence attachment area, "Complete Step" button
- Skipping requires justification text
- Step 10 generates Go/No-Go summary with evidence references

**Backend Expected Outcome:**
- POST to complete step N validates steps 1..N-1 are completed/skipped
- Each step stores outputs, evidence_ids, status
- Go/No-Go endpoint aggregates all step data

**Best Implementation Approach:**
- Clinical workflow service already has 10 steps — enhance step execution to validate ordering
- Add evidence attachment to each step
- Create Go/No-Go summary generator

#### Acceptance Criteria

1. THE Clinical_Workflow SHALL present 10 sequential steps with enforced ordering
2. WHEN step N is attempted, THE system SHALL verify steps 1..N-1 are completed or skipped
3. WHEN a step is completed, THE system SHALL require at least one evidence item
4. WHEN a step is skipped, THE system SHALL require written justification
5. WHEN all steps complete, THE system SHALL generate a Go/No-Go decision summary
6. Step progress SHALL persist to backend and survive page reloads

### Requirement 8: SynthArena Debate Engine

**User Story:** As a researcher, I want multi-agent debate simulations where specialist agents argue for/against compounds with evidence, for structured adversarial evaluation.

**Frontend Expected Outcome:**
- "Run Debate" button after scoring
- Debate timeline showing agent arguments with names, roles, evidence citations
- Final consensus with winner, confidence, dissenting opinions

**Backend Expected Outcome:**
- Creates 3 specialist agents (Medicinal Chemist, Toxicologist, Clinical Pharmacologist)
- Each generates evidence-backed arguments
- Consensus computed from agent votes

**Best Implementation Approach:**
- SynthArena service has debate infrastructure — enhance with LLM reasoning when available, rule-based fallback

#### Acceptance Criteria

1. WHEN debate is initiated, THE system SHALL create 3+ specialist agents with distinct roles
2. WHEN agents argue, THE system SHALL provide evidence-backed reasoning with data citations
3. WHEN debate completes, THE system SHALL produce debate_history with all arguments
4. WHEN consensus is reached, THE system SHALL generate winner rationale with confidence and dissenting opinions
5. IF LLM unavailable, THE system SHALL fall back to rule-based scoring

### Requirement 9: Decision Dossier Generation

**User Story:** As a researcher, I want comprehensive decision dossiers with AI analysis, evidence backing, provenance, and PDF/DOCX export.

**Frontend Expected Outcome:**
- "Generate Dossier" button on SynthArena sessions
- Rendered document with sections: Executive Summary, Compound Comparison, Scoring Matrix, Debate Summary, Recommendation, Provenance Appendix
- Export buttons for PDF and DOCX

**Backend Expected Outcome:**
- Assembles session data into structured document
- PDF via WeasyPrint, DOCX via python-docx

**Best Implementation Approach:**
- Create dossier_generator service assembling SynthArena data
- Use Jinja2 templates for HTML→PDF, python-docx for DOCX

#### Acceptance Criteria

1. WHEN dossier generation is requested, THE system SHALL produce a document with executive summary, comparison, scoring, debate, recommendation, and provenance
2. THE dossier SHALL include provenance appendix listing every source consulted
3. WHEN exported to PDF, THE system SHALL generate formatted PDF with tables and citations
4. WHEN exported to DOCX, THE system SHALL generate formatted DOCX preserving structure
5. THE dossier UI SHALL render all sections with expandable evidence citations

### Requirement 10: WebSocket Real-Time Progress

**User Story:** As a researcher, I want real-time progress for long-running operations without polling.

**Frontend Expected Outcome:**
- Progress bar with percentage, stage name, elapsed time for docking, lab runs, deep searches
- Real-time updates without polling
- Reconnection on connection drop

**Backend Expected Outcome:**
- WebSocket manager sends structured progress events
- Events include job_id, event_type, progress_pct, message, timestamp

**Best Implementation Approach:**
- websocket_routes.py and websocket_manager.py exist — enhance to emit from docking_service, labs, search_engine
- useRunProgress hook already consumes events

#### Acceptance Criteria

1. WHEN a docking job runs, THE system SHALL send WebSocket progress events at each stage
2. WHEN a lab run executes, THE system SHALL send progress events including intermediate results
3. WHEN a deep search runs, THE system SHALL stream partial results as connectors respond
4. WHEN connection drops, THE system SHALL allow reconnection with current state recovery
5. WHEN a job completes, THE system SHALL send final event with full result and provenance

### Requirement 11: Frontend Integration Testing with Live Queries

**User Story:** As a developer, I want verified end-to-end testing of all pages with real API data.

**Frontend Expected Outcome:**
- All 13 primary pages verified working with real data
- No blank screens, unhandled errors, or degraded placeholders for core features

**Backend Expected Outcome:**
- All endpoints return real data for test queries
- Integration tests verify response shapes

**Best Implementation Approach:**
- Write pytest integration tests using httpx AsyncClient
- Test each endpoint with real queries (BRCA1, EGFR, aspirin)

#### Acceptance Criteria

1. Cockpit search with "BRCA1" SHALL return proteins, genes, publications with rendered KG
2. Entity Intelligence with "/Gene EGFR" SHALL resolve to canonical identifier
3. Knowledge Graph SHALL render colored nodes and clickable edges
4. Pathways search SHALL render interactive diagram with source attribution
5. Structure page with P38398 SHALL load 3D structure with sub-tabs
6. Design Studio SHALL show accurate plugin status
7. Clinical Design SHALL show 10 steps with enforcement
8. SynthArena with 2 compounds SHALL compute scoring and allow debate
9. At least 2 Research Labs SHALL return real computation results
10. Contradictions with "aspirin cardiovascular" SHALL return results with evidence

### Requirement 12: Provenance and Contradiction Visibility Compliance

**User Story:** As a researcher, I want every response to include provenance and contradictions to be visibly surfaced.

**Frontend Expected Outcome:**
- Every data page shows provenance indicator (source count, success count, degraded sources)
- Contradictions appear as warning cards with both sides, never hidden

**Backend Expected Outcome:**
- Every Response_Envelope includes provenance with sources_queried, sources_succeeded, sources_degraded, generated_at
- Contradiction detection runs on every evidence aggregation

**Best Implementation Approach:**
- Audit all endpoints for provenance compliance
- Add contradiction detection to cockpit analysis pipeline

#### Acceptance Criteria

1. WHEN any endpoint returns connector data, THE Response_Envelope SHALL include provenance with sources_queried, sources_succeeded, sources_degraded, generated_at
2. WHEN contradictions are detected, THE UI SHALL display them visibly with type, severity, and explanation
3. WHEN the Cockpit returns results, THE UI SHALL show provenance summary
4. WHEN entity details are shown, THE UI SHALL show source attribution per section
5. WHEN lab results are returned, THE response SHALL include provenance with computations and API calls
6. THE application SHALL NOT silently flatten contradictions
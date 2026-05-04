# Implementation Plan: Drug Designer Codebase Alignment

## Overview

This plan transforms the Drug Designer platform from ~35% functional scaffolding into a production-grade biomedical research tool by addressing 12 critical functional gaps. Tasks are organized into 12 phases matching the requirements, with property-based tests validating the 22 correctness properties from the design document. The backend uses Python (FastAPI), the frontend uses TypeScript (React 19 / Vite 8 / TailwindCSS 4).

## Tasks

- [ ] 1. NLP Engine Integration (Requirement 1)
  - [ ] 1.1 Wire NLP Contradiction Engine into Contradiction Detector
    - In `apps/api/services/contradiction_detector.py`, ensure `analyze_contradictions_and_similarities()` calls `await get_nlp_engine().initialize()` before first use, then calls `classify_pair()` as the PRIMARY classification method for every claim pair
    - Implement keyword heuristic fallback when `engine._available` is False
    - Set `method_used` field in response to "nlp" or "keyword_fallback" matching engine availability
    - _Requirements: 1.1, 1.2, 1.7_

  - [ ] 1.2 Verify NLP Contradiction Engine lazy loading and fallback
    - In `apps/api/services/nlp_contradiction_engine.py`, verify `initialize()` lazy-loads PubMedBERT and BioNLI, sets `_available` flag, and logs errors without crashing on failure
    - Ensure `classify_pair()` returns `NLIResult` with `label` in {entailment, contradiction, neutral}, `confidence` in [0.0, 1.0], and `method` in {nli_model, keyword_heuristic}
    - _Requirements: 1.2, 1.3_

  - [ ] 1.3 Wire Similarity Analyzer to use cosine similarity
    - In `apps/api/services/similarity_analyzer.py`, verify `_find_similarity_clusters()` uses cosine similarity on PubMedBERT embeddings with configurable threshold (default 0.7) instead of Jaccard overlap
    - Ensure similarity clusters include `similarity_score`, `relationship_type`, `consensus_strength`
    - _Requirements: 1.4_

  - [ ] 1.4 Enhance PICO Extractor with biomedical NER
    - In `apps/api/services/pico_extractor.py`, add spaCy `en_core_sci_sm` model loading with fallback to regex patterns
    - Extract Population, Intervention, Comparison, Outcome with entity type annotations
    - _Requirements: 1.5_

  - [ ] 1.5 Update Contradictions page UI with method badges and confidence
    - In `apps/web/src/pages/Contradictions.tsx`, add method badge (NLP purple / Keyword gray) on each contradiction card
    - Display confidence percentage from NLI model probability
    - Show experimental context (study_type, model_organisms, methodologies) per contradiction
    - Add analysis method banner at top of page
    - _Requirements: 1.6_

  - [ ]* 1.6 Write property test for NLI Classification Output Structure
    - **Property 1: NLI Classification Output Structure**
    - Test that for any two text strings, `classify_pair()` returns label in {entailment, contradiction, neutral}, confidence in [0.0, 1.0], method in {nli_model, keyword_heuristic}
    - Use Hypothesis with `st.text()` strategies
    - File: `apps/api/tests/unit/test_nlp_properties.py`
    - **Validates: Requirements 1.3**

  - [ ]* 1.7 Write property test for Similarity Clustering Threshold
    - **Property 2: Similarity Clustering Respects Threshold**
    - Test that for any set of claims and threshold T, every pair within a cluster has similarity >= T
    - Use Hypothesis with `st.lists(st.text())` and `st.floats(min_value=0.0, max_value=1.0)`
    - File: `apps/api/tests/unit/test_nlp_properties.py`
    - **Validates: Requirements 1.4**

  - [ ]* 1.8 Write property test for Analysis Response Method Field
    - **Property 3: Analysis Response Method Field**
    - Test that for any query, response contains `method_used` matching NLP engine availability
    - Use Hypothesis with `st.booleans()` for engine availability and `st.text()` for queries
    - File: `apps/api/tests/unit/test_nlp_properties.py`
    - **Validates: Requirements 1.1, 1.7**

- [ ] 2. Checkpoint — Verify NLP Engine Integration
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Research Labs Real Computation (Requirement 2)
  - [ ] 3.1 Implement Target Discovery real computation
    - In `apps/api/routers/labs.py` and `apps/api/services/labs/`, enhance `_inline_target_discovery` to call OpenTargets, DisGeNET, UniProt connectors in parallel via `asyncio.gather`
    - Score targets using existing `TargetScorer` service
    - Build PPI network from STRING/IntAct data
    - Return ranked targets with `ProvenanceChain`
    - _Requirements: 2.1, 2.9_

  - [ ] 3.2 Implement Pocket Detection real computation
    - Enhance `_inline_pocket_detection` to call existing `DockingService.detect_pockets()` which invokes fpocket
    - Parse pocket output for residues, coordinates, druggability scores
    - Return ranked pockets with provenance
    - _Requirements: 2.2_

  - [ ] 3.3 Implement Molecule Generation real computation
    - Enhance `_inline_molecule_generation` to use `DLModelService` diffusion model or RDKit enumeration fallback
    - Compute RDKit descriptors (MW, LogP, TPSA, HBD, HBA, RotBonds)
    - Return SMILES with predicted properties and provenance
    - _Requirements: 2.3_

  - [ ] 3.4 Implement ADMET real computation
    - Enhance `_inline_admet` to use `ADMETPredictor` from `molecule_service.py`
    - Compute all 5 ADMET categories with conformal prediction confidence intervals
    - Ensure each prediction has `lower_bound <= prediction <= upper_bound` in [0.0, 1.0]
    - _Requirements: 2.4_

  - [ ] 3.5 Implement Retrosynthesis real computation
    - Enhance `_inline_retrosynthesis` to use RDKit RECAP decomposition
    - Identify retrosynthetic routes and score feasibility
    - Return route trees with provenance
    - _Requirements: 2.5_

  - [ ] 3.6 Implement Vaccine Design computation
    - In `apps/api/services/labs/vaccine_lab.py`, implement epitope prediction using sliding window + hydrophilicity analysis
    - Predict B-cell and T-cell epitopes from antigen sequence
    - Return ranked vaccine candidates with provenance
    - _Requirements: 2.6_

  - [ ] 3.7 Implement Metabolic Engineering computation
    - In `apps/api/services/labs/metabolic_engineering_lab.py`, implement stoichiometric flux analysis
    - Identify bottleneck reactions and suggest pathway modifications
    - Return optimized pathway with provenance
    - _Requirements: 2.7_

  - [ ] 3.8 Implement Pharmacogenomics computation
    - In `apps/api/services/labs/pharmacogenomics_lab.py`, query PharmGKB and CPIC connectors
    - Return gene-drug interactions, variant annotations, dosing recommendations with provenance
    - _Requirements: 2.8_

  - [ ] 3.9 Add structured error handling for unavailable tools
    - In each lab computation module, implement graceful degradation returning `StructuredError` with dependency name, installation instructions, and degraded result using available alternatives
    - _Requirements: 2.10_

  - [ ]* 3.10 Write property test for ADMET Confidence Intervals
    - **Property 4: ADMET Predictions Include Confidence Intervals**
    - Test that for any valid SMILES, ADMET result includes all 5 categories each with lower_bound <= prediction <= upper_bound in [0.0, 1.0]
    - Use Hypothesis with a strategy generating valid SMILES strings
    - File: `apps/api/tests/unit/test_lab_properties.py`
    - **Validates: Requirements 2.4**

  - [ ]* 3.11 Write property test for Lab Response Provenance Invariant
    - **Property 5: Lab Response Provenance Invariant**
    - Test that for any lab run, response includes provenance with non-empty sources_queried, sources_succeeded subset, sources_degraded subset, and ISO timestamp
    - Use Hypothesis with `st.sampled_from` for lab types
    - File: `apps/api/tests/unit/test_lab_properties.py`
    - **Validates: Requirements 2.9, 12.1, 12.5**

- [ ] 4. Checkpoint — Verify Research Labs Computation
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Knowledge Graph Enhancement (Requirement 3)
  - [ ] 5.1 Apply ENTITY_COLORS to ForceGraph nodes
    - In `apps/web/src/components/ui/ForceGraph.tsx`, import `ENTITY_COLORS` from `apps/web/src/lib/entityColors.ts`
    - Set each node's rendered color to `ENTITY_COLORS[node.type]` using the exact hex values: protein=#7c3aed, gene=#6366f1, disease=#dc2626, drug=#e11d48, compound=#d97706, pathway=#0891b2, publication=#3b82f6, clinical_trial=#059669, variant=#ea580c
    - _Requirements: 3.1_

  - [ ] 5.2 Compute and apply betweenness centrality for node sizing
    - In `apps/api/services/graph_service.py`, add networkx `betweenness_centrality()` computation after graph construction
    - Set each node's `size = 0.5 + centrality * 2.0`
    - Pass `color` and `size` fields in graph response
    - In `ForceGraph.tsx`, use `node.size` for rendered node radius
    - _Requirements: 3.2_

  - [ ] 5.3 Populate edge reason and evidence on graph construction
    - In `apps/api/services/graph_service.py`, enhance edge construction to populate `reason` (non-empty human-readable string), `evidence_ids` (at least one), `relationship_type`, `source_db`, and `confidence` from connector data
    - _Requirements: 3.4_

  - [ ] 5.4 Implement edge click detail panel in ForceGraph
    - In `ForceGraph.tsx`, add `onEdgeClick` handler that opens a detail panel showing: relationship type, human-readable reason, evidence items with source links, provenance info
    - Style edges by relationship type (solid for direct, dashed for inferred)
    - _Requirements: 3.3_

  - [ ] 5.5 Add edge detail API endpoint
    - In `apps/api/routers/graph.py`, add `GET /api/v1/graph/edge/{edge_id}` endpoint returning full evidence items for the edge
    - _Requirements: 3.3_

  - [ ]* 5.6 Write property test for Node Color Mapping Invariant
    - **Property 6: Node Color Mapping Invariant**
    - Test that for any entity type in ENTITY_COLORS, the built node's color matches the canonical hex value
    - Use Hypothesis with `st.sampled_from(list(ENTITY_COLORS.keys()))`
    - File: `apps/api/tests/unit/test_graph_properties.py`
    - **Validates: Requirements 3.1**

  - [ ]* 5.7 Write property test for Node Size Formula
    - **Property 7: Node Size Formula**
    - Test that for any centrality score c in [0.0, 1.0], node size equals 0.5 + c * 2.0
    - Use Hypothesis with `st.floats(min_value=0.0, max_value=1.0)`
    - File: `apps/api/tests/unit/test_graph_properties.py`
    - **Validates: Requirements 3.2**

  - [ ]* 5.8 Write property test for Edge Completeness Invariant
    - **Property 8: Edge Completeness Invariant**
    - Test that for any constructed edge, reason has len > 0 and evidence_ids has len >= 1
    - Use Hypothesis to generate edge data
    - File: `apps/api/tests/unit/test_graph_properties.py`
    - **Validates: Requirements 3.4**

- [ ] 6. Checkpoint — Verify Knowledge Graph Enhancement
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 7. Entity Detail Pages (Requirement 4)
  - [ ] 7.1 Create EntityDetailDrawer component
    - Create or enhance `apps/web/src/components/entity/EntityDetailDrawer.tsx` as a right-side drawer (400px wide) with tabs: Overview, Publications, Clinical Trials, Related Entities, Actions
    - Overview tab: AI-generated summary, key identifiers (UniProt, ChEMBL, MONDO), entity type badge
    - Publications tab: sortable table with title, authors, journal, year, PMID link
    - Clinical Trials tab: filterable table with NCT ID, title, phase, status, conditions
    - Related Entities tab: list of connected entities with relationship type and confidence
    - Actions bar: "View Structure", "Run in Design Studio", "Add to SynthArena", "Explore in KG" buttons
    - _Requirements: 4.1, 4.2, 4.3_

  - [ ] 7.2 Enhance entity detail backend endpoint
    - In `apps/api/routers/cockpit.py`, enhance `GET /api/v1/cockpit/entity/{entity_id}` to call PubMed, ClinicalTrials, and graph connectors in parallel via `asyncio.gather`
    - Generate AI overview via LLM if available, otherwise structured summary from connector data
    - Cache response for 30 minutes per entity_id using Redis
    - Return within 5 seconds
    - _Requirements: 4.6_

  - [ ] 7.3 Wire EntityDetailDrawer into platform pages
    - Wire the drawer into `WorkspacePage.tsx`, `KGPage.tsx`, `EntityIntelligence.tsx`, and `PathwaysPage.tsx` via shared context or callback
    - Clicking any entity name in Cockpit results, KG nodes, entity tables, or pathway nodes opens the drawer
    - _Requirements: 4.1, 4.5_

  - [ ] 7.4 Implement Handoff Payload for action buttons
    - Each action button builds a `Handoff_Payload` with `entity_id`, `entity_type`, `entity_name`, and `target_route` using existing `persistCockpitHandoff` system
    - Navigate to target page: /structure, /design, /syntharena, /graph
    - _Requirements: 4.4_

  - [ ]* 7.5 Write property test for Handoff Payload Construction
    - **Property 22: Handoff Payload Construction**
    - Test that for any entity action click, the Handoff_Payload contains entity_id, entity_type, entity_name, and target_route matching the action's destination
    - Use fast-check with `fc.record()` strategies for entity data
    - File: `apps/web/src/components/entity/__tests__/EntityDetailDrawer.property.test.ts`
    - **Validates: Requirements 4.4**

- [ ] 8. Pathway Interactivity (Requirement 5)
  - [ ] 8.1 Add pathway node click popovers
    - In `apps/web/src/components/pathways/BiologicalPathwayWorkbench.tsx`, enhance node click handlers to show a popover with: node name, biological role/function, source database name + link, evidence items
    - Add small colored dot on each node indicating source: KEGG=emerald, Reactome=indigo, WikiPathways=purple
    - _Requirements: 5.1, 5.3_

  - [ ] 8.2 Add pathway edge click popovers
    - In `BiologicalPathwayWorkbench.tsx`, add edge click handler showing popover with: connection type (activation/inhibition/phosphorylation/binding/catalysis), mechanism description, source attribution, evidence
    - _Requirements: 5.2_

  - [ ] 8.3 Enhance pathway backend with source attribution
    - Enhance Reactome/KEGG/WikiPathways connectors to return `source_db`, `source_url`, `explanation`, and `evidence[]` metadata with each node and edge
    - Enhance disease-context endpoint to return real `rewired_genes` from DisGeNET/OpenTargets and `therapeutic_targets`
    - _Requirements: 5.5_

  - [ ] 8.4 Implement disease context highlighting
    - In `BiologicalPathwayWorkbench.tsx`, highlight disease-affected nodes with red border (#dc2626) and therapeutic targets with green border (#059669)
    - Add a legend at the bottom showing source color coding
    - _Requirements: 5.4_

  - [ ]* 8.5 Write property test for Pathway Source Attribution
    - **Property 9: Pathway Source Attribution**
    - Test that for any pathway node/edge with source_db, the rendered output displays the source database name and provides a link
    - File: `apps/api/tests/unit/test_pathway_properties.py`
    - **Validates: Requirements 5.3, 5.5**

  - [ ]* 8.6 Write property test for Disease Context Highlighting
    - **Property 10: Disease Context Highlighting**
    - Test that nodes in rewired_genes get red border (#dc2626) and nodes in therapeutic_targets get green border (#059669)
    - Use fast-check with generated node lists and disease context
    - File: `apps/web/src/components/pathways/__tests__/PathwayHighlighting.property.test.ts`
    - **Validates: Requirements 5.4**

- [ ] 9. Checkpoint — Verify Entity Detail Pages and Pathway Interactivity
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Structure Viewer Completeness (Requirement 6)
  - [ ] 10.1 Implement 7 sub-tab components for StructurePage
    - In `apps/web/src/pages/StructurePage.tsx`, add 7 sub-tab components: StructureSummaryTab, Structure3DTab, BindingSitesTab, AnnotationsTab, SequenceTab, GenomeTab, ComparisonTab
    - Summary: protein name, organism, function, gene name, sequence length, resolution, confidence (pLDDT for predicted)
    - 3D Structure: Mol* viewer with representation controls (cartoon, ball-and-stick, surface, ribbon) and color schemes (chain, residue, bfactor, hydrophobicity)
    - Binding Sites: table ranked by druggability score descending with residue lists, center coordinates, volume, source
    - Annotations: domain annotations, PTMs, active sites, disulfide bonds from UniProt/InterPro
    - Sequence: amino acid sequence with secondary structure coloring
    - Genome: genomic context (chromosome, position, gene structure)
    - Comparison: side-by-side two-structure comparison with RMSD
    - _Requirements: 6.1_

  - [ ] 10.2 Implement ESM → AlphaFold → RCSB fallback chain
    - In `apps/api/services/structure_service.py`, add ESM API as first source, AlphaFold second, RCSB PDB third
    - Return `source` field indicating which source provided the data
    - Add degraded indicator when falling back to lower-priority source
    - _Requirements: 6.2, 6.5_

  - [ ] 10.3 Add "Import to Design Studio" button
    - In `StructurePage.tsx`, add button that builds `Handoff_Payload` with `target_id`, `binding_site`, `structure_source` and navigates to /design
    - _Requirements: 6.4_

  - [ ]* 10.4 Write property test for Structure Source Fallback Chain
    - **Property 11: Structure Source Fallback Chain**
    - Test that for any protein ID, sources are attempted in order ESM → AlphaFold → RCSB, using first success; if all fail, return "no_structure_available"
    - Use Hypothesis with mocked source availability combinations
    - File: `apps/api/tests/unit/test_structure_properties.py`
    - **Validates: Requirements 6.2, 6.5**

  - [ ]* 10.5 Write property test for Binding Site Sort Order
    - **Property 12: Binding Site Sort Order**
    - Test that for any list of binding sites, they are sorted by druggability_score descending
    - Use Hypothesis with `st.lists(st.floats(min_value=0.0, max_value=1.0))`
    - File: `apps/api/tests/unit/test_structure_properties.py`
    - **Validates: Requirements 6.3**

- [ ] 11. Clinical Workflow Enforcement (Requirement 7)
  - [ ] 11.1 Implement workflow step ordering enforcement
    - In `apps/api/services/clinical/` create or enhance `workflow_engine.py` with `ClinicalWorkflowEngine` class
    - `attempt_step(workflow_id, step_number, payload)` validates steps 1..N-1 are completed or skipped before allowing step N
    - Reject step N if any prior step K has status "pending"
    - _Requirements: 7.1, 7.2_

  - [ ] 11.2 Implement evidence requirement for step completion
    - In `workflow_engine.py`, validate that `evidence_ids` list is non-empty for step completion
    - Return validation error if evidence_ids is empty
    - _Requirements: 7.3_

  - [ ] 11.3 Implement justification requirement for step skip
    - In `workflow_engine.py`, validate that `skip_justification` is non-empty and non-whitespace for step skip
    - Return validation error if justification is empty or whitespace-only
    - _Requirements: 7.4_

  - [ ] 11.4 Implement Go/No-Go summary generation
    - In `workflow_engine.py`, add `generate_go_nogo(workflow_id)` that aggregates all step outputs, evidence, and decisions into a structured Go/No-Go summary
    - _Requirements: 7.5_

  - [ ] 11.5 Implement workflow state persistence
    - Persist workflow state (step statuses, evidence_ids, outputs) to PostgreSQL
    - Ensure round-trip consistency: save then retrieve returns identical data
    - Emit WebSocket progress events on step completion
    - _Requirements: 7.6_

  - [ ] 11.6 Update TranslationalResearch page with workflow stepper UI
    - In `apps/web/src/pages/TranslationalResearch.tsx`, implement vertical stepper with 10 numbered steps
    - Completed steps show green checkmark, current step highlighted, future steps grayed/disabled
    - Each step has input fields, evidence attachment area, "Complete Step" button
    - Skip requires justification text input
    - _Requirements: 7.1_

  - [ ]* 11.7 Write property test for Clinical Workflow Step Ordering
    - **Property 13: Clinical Workflow Step Ordering Enforcement**
    - Test that for any workflow state and step N in [2,10], attempting step N is rejected if any step K < N has status "pending"
    - Use Hypothesis with `st.sets(st.integers(1,10))` for completed steps and `st.integers(2,10)` for target
    - File: `apps/api/tests/unit/test_clinical_properties.py`
    - **Validates: Requirements 7.2**

  - [ ]* 11.8 Write property test for Step Completion Requires Evidence
    - **Property 14: Step Completion Requires Evidence**
    - Test that for any step completion with empty evidence_ids, the system rejects with validation error
    - Use Hypothesis with `st.lists(st.text(), max_size=0)` for empty lists
    - File: `apps/api/tests/unit/test_clinical_properties.py`
    - **Validates: Requirements 7.3**

  - [ ]* 11.9 Write property test for Step Skip Requires Justification
    - **Property 15: Step Skip Requires Justification**
    - Test that for any skip with empty or whitespace-only justification, the system rejects
    - Use Hypothesis with `st.text(alphabet=st.characters(whitelist_categories=('Zs',)))` for whitespace strings
    - File: `apps/api/tests/unit/test_clinical_properties.py`
    - **Validates: Requirements 7.4**

  - [ ]* 11.10 Write property test for Workflow State Persistence Round-Trip
    - **Property 16: Clinical Workflow State Persistence Round-Trip**
    - Test that for any workflow state saved, retrieving by ID returns identical step statuses, evidence_ids, and outputs
    - Use Hypothesis to generate workflow states
    - File: `apps/api/tests/unit/test_clinical_properties.py`
    - **Validates: Requirements 7.6**

- [ ] 12. Checkpoint — Verify Structure Viewer and Clinical Workflow
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 13. SynthArena Debate Engine (Requirement 8)
  - [ ] 13.1 Implement multi-agent debate engine
    - In `apps/api/services/syntharena/engine.py`, implement `DebateEngine` with 3 specialist agents: Medicinal Chemist, Toxicologist, Clinical Pharmacologist
    - Each agent generates evidence-backed arguments citing specific data (IC50, LD50, clinical outcomes)
    - Use LLM reasoning when available, fall back to rule-based scoring
    - _Requirements: 8.1, 8.2, 8.5_

  - [ ] 13.2 Implement debate consensus computation
    - In `engine.py`, compute consensus from agent votes
    - Generate `winner_compound_id`, `winner_rationale` (non-empty), `confidence` in [0.0, 1.0], and `dissenting_opinions` array
    - Produce complete `debate_history` with all arguments from each agent
    - _Requirements: 8.3, 8.4_

  - [ ] 13.3 Add debate UI to SynthArena page
    - In `apps/web/src/pages/SynthArenaPage.tsx`, add "Run Debate" button after scoring
    - Show debate timeline with agent arguments, names, roles, evidence citations
    - Display final consensus with winner, confidence, dissenting opinions
    - _Requirements: 8.1, 8.4_

  - [ ]* 13.4 Write property test for Debate Agent Minimum and Uniqueness
    - **Property 17: Debate Agent Minimum and Uniqueness**
    - Test that for any debate initiation, at least 3 agents are created with distinct role strings
    - Use Hypothesis to generate debate inputs
    - File: `apps/api/tests/unit/test_debate_properties.py`
    - **Validates: Requirements 8.1**

  - [ ]* 13.5 Write property test for Debate Completeness
    - **Property 18: Debate Completeness**
    - Test that for any completed debate, debate_history has at least one argument per agent, and consensus has winner_compound_id, non-empty winner_rationale, confidence in [0.0, 1.0], and dissenting_opinions array
    - Use Hypothesis to generate debate sessions
    - File: `apps/api/tests/unit/test_debate_properties.py`
    - **Validates: Requirements 8.3, 8.4**

- [ ] 14. Decision Dossier Generation (Requirement 9)
  - [ ] 14.1 Implement dossier content assembly
    - In `apps/api/services/dossier_generator.py`, implement `DossierGenerator.generate(session_id)` that assembles SynthArena session data into structured document
    - Sections: Executive Summary, Compound Comparison, Scoring Matrix, Debate Summary, Recommendation, Provenance Appendix
    - Provenance appendix lists every source consulted during generation
    - _Requirements: 9.1, 9.2_

  - [ ] 14.2 Implement PDF export via WeasyPrint
    - In `dossier_generator.py`, implement `export_pdf(dossier)` using Jinja2 HTML templates rendered to PDF via WeasyPrint
    - Include formatted tables and citations
    - _Requirements: 9.3_

  - [ ] 14.3 Implement DOCX export via python-docx
    - In `dossier_generator.py`, implement `export_docx(dossier)` using python-docx for structured document generation
    - Preserve section structure, tables, and formatting
    - _Requirements: 9.4_

  - [ ] 14.4 Add dossier UI to SynthArena and Dossiers pages
    - In `SynthArenaPage.tsx`, add "Generate Dossier" button on sessions
    - In `apps/web/src/pages/DossiersPage.tsx`, render dossier sections with expandable evidence citations
    - Add PDF and DOCX export buttons
    - _Requirements: 9.5_

  - [ ]* 14.5 Write property test for Dossier Section Completeness
    - **Property 19: Dossier Section Completeness**
    - Test that for any valid session data, generated dossier contains all required sections (executive_summary, compound_comparison, scoring_matrix, debate_summary, recommendation, provenance_appendix) and provenance_appendix lists every source consulted
    - Use Hypothesis to generate session data
    - File: `apps/api/tests/unit/test_dossier_properties.py`
    - **Validates: Requirements 9.1, 9.2**

- [ ] 15. Checkpoint — Verify SynthArena and Dossier Generation
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 16. WebSocket Real-Time Progress (Requirement 10)
  - [ ] 16.1 Enhance WebSocket manager with structured progress events
    - In `apps/api/core/websocket_manager.py`, ensure `emit()` sends structured events with `job_id`, `event_type`, `progress_pct`, `message`, `timestamp`
    - Maintain in-memory event history (max 200 events per run_id) for reconnection replay
    - _Requirements: 10.1, 10.2_

  - [ ] 16.2 Wire progress emission into lab services
    - In each lab computation module (`apps/api/services/labs/`), emit progress events at each computation stage via `ws_manager.emit()`
    - Include intermediate results in progress events
    - _Requirements: 10.2_

  - [ ] 16.3 Wire progress emission into docking and search services
    - In `apps/api/services/docking_service.py`, emit progress events at each docking stage
    - In `apps/api/services/search_engine.py`, stream partial results as connectors respond
    - _Requirements: 10.1, 10.3_

  - [ ] 16.4 Implement WebSocket reconnection with state recovery
    - In `apps/api/routers/websocket_routes.py`, handle reconnection with `last_seen_ts` parameter
    - Replay all events since `last_seen_ts` from in-memory history in chronological order
    - Implement exponential backoff reconnection on client side in `apps/web/src/lib/websocket.ts`
    - _Requirements: 10.4_

  - [ ] 16.5 Send final completion event with full result
    - Ensure all long-running operations send a final `run.completed` event with full result and provenance
    - _Requirements: 10.5_

  - [ ]* 16.6 Write property test for WebSocket Reconnection Replay
    - **Property 20: WebSocket Reconnection Replay**
    - Test that for any event history and last_seen_ts, replay returns exactly events with timestamp > last_seen_ts in chronological order
    - Use Hypothesis with `st.lists(st.datetimes())` for event timestamps
    - File: `apps/api/tests/unit/test_websocket_properties.py`
    - **Validates: Requirements 10.4**

- [ ] 17. Checkpoint — Verify WebSocket Real-Time Progress
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 18. Integration Testing (Requirement 11)
  - [ ] 18.1 Write integration tests for Cockpit and Entity Intelligence
    - In `apps/api/tests/integration/`, write pytest tests using `httpx.AsyncClient`
    - Test Cockpit search with "BRCA1" returns proteins, genes, publications
    - Test Entity Intelligence with "/Gene EGFR" resolves to canonical identifier
    - _Requirements: 11.1, 11.2_

  - [ ] 18.2 Write integration tests for Knowledge Graph and Pathways
    - Test Knowledge Graph renders colored nodes and clickable edges
    - Test Pathways search renders interactive diagram with source attribution
    - _Requirements: 11.3, 11.4_

  - [ ] 18.3 Write integration tests for Structure and Design Studio
    - Test Structure page with P38398 loads 3D structure with sub-tabs
    - Test Design Studio shows accurate plugin status
    - _Requirements: 11.5, 11.6_

  - [ ] 18.4 Write integration tests for Clinical Workflow and SynthArena
    - Test Clinical Design shows 10 steps with enforcement
    - Test SynthArena with 2 compounds computes scoring and allows debate
    - _Requirements: 11.7, 11.8_

  - [ ] 18.5 Write integration tests for Research Labs and Contradictions
    - Test at least 2 Research Labs return real computation results
    - Test Contradictions with "aspirin cardiovascular" returns results with evidence
    - _Requirements: 11.9, 11.10_

- [ ] 19. Provenance Compliance Audit (Requirement 12)
  - [ ] 19.1 Audit all endpoints for provenance compliance
    - Review all API endpoints that return connector data
    - Ensure every `Response_Envelope` includes `provenance` with `sources_queried`, `sources_succeeded`, `sources_degraded`, `generated_at`
    - Add missing provenance fields where needed
    - _Requirements: 12.1_

  - [ ] 19.2 Add contradiction detection to cockpit analysis pipeline
    - Ensure contradiction detection runs on every evidence aggregation in the cockpit
    - Contradictions appear as warning cards with both sides, never hidden or silently flattened
    - _Requirements: 12.2, 12.6_

  - [ ] 19.3 Add provenance UI indicators to data pages
    - In Cockpit results, show provenance summary (source count, success count, degraded sources)
    - In entity details, show source attribution per section
    - In lab results, show provenance with computations and API calls
    - _Requirements: 12.3, 12.4, 12.5_

  - [ ]* 19.4 Write property test for Contradiction Visibility
    - **Property 21: Contradiction Visibility**
    - Test that for any analysis result with contradiction count > 0, all contradictions are included without filtering, each with non-empty type, severity, and explanation
    - Use Hypothesis to generate analysis results with contradictions
    - File: `apps/api/tests/unit/test_provenance_properties.py`
    - **Validates: Requirements 12.2, 12.6**

- [ ] 20. Final Checkpoint — Full Integration Verification
  - Ensure all tests pass, ask the user if questions arise.
  - Verify all 12 requirements have been addressed
  - Verify all 22 correctness properties have corresponding property tests

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each major phase
- Property tests validate universal correctness properties from the design document (22 properties total)
- Unit tests validate specific examples and edge cases
- Backend uses Python (FastAPI, Hypothesis for PBT), frontend uses TypeScript (React 19, fast-check for PBT)
- All lab computations follow the graceful degradation pattern: primary tool → fallback → structured error
- WebSocket progress events use the existing `websocket_manager.py` infrastructure

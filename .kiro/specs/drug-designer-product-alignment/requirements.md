# Requirements Document

## Introduction

Drug Designer is a browser-native scientific research platform for drug discovery. The existing codebase (~60 frontend pages, ~43 API routers, ~158 connectors) claims 97% completion but the application is not functional as a cohesive product. This requirements document defines the complete set of functional and non-functional requirements to transform the codebase into a fully working product aligned with the Drug_Designer.md master specification (11,350 lines).

The requirements cover 14 major subsystems: Cockpit (agentic search hub), Disease Intelligence + Target Prioritization (merged), Knowledge Graphs, Pathways, PPI/Gene/Protein merge, 3D Structure Tab, Design Studio, Clinical Design, SynthArena, Research Labs, Contradiction & Similarity, PICO, page removals, and Settings elaboration. The tech stack is React/TypeScript/Vite (frontend), FastAPI/Python (backend), PostgreSQL + Qdrant + Redis + Neo4j (data layer).

## Glossary

- **Cockpit**: The main search hub page acting as an agentic extension of every page, supporting general queries and slash commands
- **Slash_Command**: A query prefixed with `/` (e.g., `/disease`, `/structure`, `/kg`) that routes to a specific page with pre-loaded context
- **Entity_Intelligence**: The merged Disease Intelligence + Target Prioritization page with 5 input slots
- **Knowledge_Graph**: An interactive graph visualization with colored nodes by entity type and clickable edges showing connection reasons
- **PPI_Network**: Protein-Protein Interaction network, merged as a mode within the Knowledge Graph
- **Pathway_Explorer**: Interactive pathway visualization with source attribution and clickable explanations
- **Structure_Viewer**: 3D molecular structure viewer using Mol* with ESM, AlphaFold, and RCSB PDB sources
- **Design_Studio**: Molecule design workbench with RDKit, AutoDock Vina, fpocket, GPU Acceleration, and Diffusion Model plugins
- **Clinical_Workflow**: The 10-step clinical design workflow from Drug_Designer.md
- **SynthArena**: Drug candidate comparison arena with scenario simulation, debate, and scoring
- **Research_Lab**: One of 8 specialized computational labs (Target Discovery, Pocket, Molecule Generation, ADMET, Retrosynthesis, Vaccine, Metabolic Engineering, Pharmacogenomics)
- **Contradiction_Engine**: The system that finds contradictions AND similarities across evidence sources
- **PICO_Extractor**: The system that extracts Population, Intervention, Comparison, Outcome elements from literature
- **Connector**: A backend module that fetches data from an external scientific data source
- **Provenance_Chain**: Metadata tracking which sources were queried, which succeeded, and which degraded
- **Response_Envelope**: The universal wrapper for all API responses containing status, data, provenance, and timing
- **Entity_Type**: One of: protein, gene, disease, drug, compound, pathway, publication, clinical_trial, variant, molecule
- **ENTITY_COLORS**: The fixed color mapping from Entity_Type to hex color for graph visualization
- **Scoring_Matrix**: A weighted multi-criteria scoring table used in SynthArena to rank compounds
- **Handoff_Payload**: A structured data object passed between pages/components to preserve context during navigation

## Requirements

### Requirement 1: Cockpit Agentic Search Hub

**User Story:** As a researcher, I want a single search bar that acts as an intelligent hub for all platform capabilities, so that I can search across 30+ databases with AI summaries or use slash commands to navigate directly to specific tools with pre-loaded context.

#### Acceptance Criteria

1. WHEN a researcher enters a general query into the Cockpit search bar, THE Cockpit SHALL classify the query, orchestrate parallel fetching across 30+ data source Connectors, and return a unified analysis result within 3000ms for the first partial response
2. WHEN a researcher enters a Slash_Command (e.g., `/disease`, `/structure`, `/kg`, `/Drug`, `/Molecule`, `/Gene`, `/Protein`), THE Cockpit SHALL parse the command, build a Handoff_Payload with the resolved context, and redirect to the target page within 500ms
3. WHEN a general query returns results, THE Cockpit SHALL display an AI-generated summary with traceable evidence citations linking back to specific source publications
4. WHEN a general query returns results, THE Cockpit SHALL display categorized entity tables (Proteins, Genes, Publications, Drugs, Diseases, Clinical Trials, Pathways, Variants, Compounds, Molecules) with each entity clickable to an Entity Detail Page
5. WHEN a general query returns results, THE Cockpit SHALL build and display a connected Knowledge_Graph with nodes colored by Entity_Type using the ENTITY_COLORS mapping
6. WHEN a general query returns results, THE Cockpit SHALL build and display a unified pathway map combining all pathway data relevant to the query terms
7. WHEN a general query returns results, THE Cockpit SHALL detect and display both contradictions and similarities across evidence sources
8. WHEN a researcher clicks on an entity in the results, THE Cockpit SHALL display an Entity Detail Page containing an AI overview, publications, patents, citations, clinical trials, related entities, and action buttons (e.g., "View Structure", "Run in Design Studio")
9. IF one or more Connectors fail or time out during a general query, THEN THE Cockpit SHALL return a response with status "degraded", include results from successful sources, and list the failed sources in the Provenance_Chain
10. WHEN the Cockpit returns any response, THE Response_Envelope SHALL include a valid Provenance_Chain with sources_queried > 0, a generated_at timestamp, and timing information

### Requirement 2: Disease Intelligence + Target Prioritization (Merged)

**User Story:** As a researcher, I want a unified entity intelligence workbench with 5 input boxes supporting slash commands, so that I can resolve entities across databases, analyze PPI networks, view knowledge graphs, explore pathways, and prioritize drug targets in a single workflow.

#### Acceptance Criteria

1. THE Entity_Intelligence page SHALL display 5 input slots, each accepting one of the Slash_Commands: /Drug, /Disease, /Molecule, /Gene, /Protein, or /Blank
2. WHEN a researcher enters a value with a Slash_Command in an input slot, THE Entity_Intelligence SHALL resolve the input to a canonical database identifier (MONDO, UniProt, ChEMBL, Ensembl, etc.) with cross-references from at least 2 databases when available
3. WHEN entity resolution fails with confidence below 0.5 for all resolvers, THE Entity_Intelligence SHALL return a structured error with did-you-mean suggestions, alternative spellings, and related entities
4. WHEN entities are resolved, THE Entity_Intelligence SHALL provide Cytoscape-like graph analysis tools including centrality computation, community detection, shortest path finding, and subgraph extraction
5. WHEN entities are resolved, THE Entity_Intelligence SHALL display a PPI_Network view showing protein-protein interactions with configurable confidence thresholds and interaction type filters (physical, genetic, coexpression, predicted)
6. WHEN entities are resolved, THE Entity_Intelligence SHALL compute and display ranked drug targets with a composite score breakdown across GWAS, pathway, druggability, safety, and literature dimensions
7. WHEN target ranking is computed, THE Entity_Intelligence SHALL provide an explanation for each target's score and flag any contradictions in the supporting evidence
8. WHEN the same entity input and Slash_Command are provided, THE Entity_Intelligence SHALL return the same canonical_id deterministically

### Requirement 3: Knowledge Graphs (Connected, Colored, Clickable)

**User Story:** As a researcher, I want interactive knowledge graphs with colored nodes by entity type and clickable edges showing why nodes are connected, so that I can visually explore relationships and understand the evidence behind each connection.

#### Acceptance Criteria

1. THE Knowledge_Graph SHALL render nodes with colors derived from the ENTITY_COLORS mapping: protein (#7c3aed), gene (#6366f1), disease (#dc2626), drug (#e11d48), compound (#d97706), pathway (#0891b2), publication (#3b82f6), clinical_trial (#059669), variant (#ea580c)
2. THE Knowledge_Graph SHALL size each node based on its betweenness centrality score within the graph
3. WHEN a researcher clicks on a Knowledge_Graph edge, THE Knowledge_Graph SHALL display the reason why the two nodes are connected, the supporting evidence items, and the source provenance
4. THE Knowledge_Graph SHALL support multiple layout modes: force-directed, hierarchical, circular, and dagre
5. WHEN the Knowledge_Graph is in PPI_Network mode, THE Knowledge_Graph SHALL display protein-protein interactions with configurable confidence thresholds and interaction type filters
6. THE Knowledge_Graph SHALL render up to 500 nodes within 500ms using WebGL-accelerated force graph rendering
7. WHEN a Knowledge_Graph is constructed, every edge SHALL have a non-empty reason field and at least one evidence_id

### Requirement 4: Pathways (Redesigned with Source Attribution)

**User Story:** As a researcher, I want properly displayed pathway visualizations with source attribution and clickable explanations at every point, so that I can understand biological pathways in the context of my research with full traceability.

#### Acceptance Criteria

1. THE Pathway_Explorer SHALL render interactive pathway diagrams with nodes (genes, proteins, compounds, reactions, complexes) and edges (activation, inhibition, phosphorylation, binding, catalysis)
2. WHEN a researcher clicks on any pathway node, THE Pathway_Explorer SHALL display an explanation of the node's role, supporting evidence items, and source attribution (KEGG, Reactome, WikiPathways, SIGNOR, or NetPath)
3. WHEN a researcher clicks on any pathway edge, THE Pathway_Explorer SHALL display an explanation of the connection type, supporting evidence, and source attribution
4. THE Pathway_Explorer SHALL display source attribution for the entire pathway including the source database name and a link to the original source URL
5. WHEN a disease context is provided, THE Pathway_Explorer SHALL highlight affected nodes, dysregulated edges, and therapeutic targets within the pathway

### Requirement 5: PPI Network, Gene/Protein Merge and Interactions Tab Removal

**User Story:** As a researcher, I want PPI Network and Gene/Protein views merged into the Knowledge Graph as modes rather than separate pages, and the Interactions tab removed, so that the navigation is streamlined and related functionality is consolidated.

#### Acceptance Criteria

1. THE Knowledge_Graph SHALL include a PPI_Network mode toggle that switches the graph view to display protein-protein interaction data
2. THE Knowledge_Graph SHALL include gene and protein entity data within the same graph view, using ENTITY_COLORS to distinguish them visually
3. THE application SHALL NOT display a separate Interactions tab in the primary navigation
4. WHEN a researcher switches between Knowledge_Graph mode and PPI_Network mode, THE Knowledge_Graph SHALL preserve the current entity context and re-render the graph with the appropriate data source

### Requirement 6: 3D Structure Tab

**User Story:** As a researcher, I want a comprehensive 3D molecular structure viewer with data from ESM Models API, AlphaFold, and RCSB PDB, so that I can analyze protein structures, binding sites, annotations, sequences, and genome context, and import structures directly into Design Studio.

#### Acceptance Criteria

1. THE Structure_Viewer SHALL display 8 sub-tabs: Summary, 3D Structure, Binding Sites, Annotations, Sequence, Genome, and Comparison
2. WHEN a valid PDB ID or UniProt ID is provided, THE Structure_Viewer SHALL fetch structure data from RCSB PDB, AlphaFold DB, and ESM Models API in parallel
3. THE Structure_Viewer SHALL render 3D molecular structures using the Mol* viewer with representation options: cartoon, ball-and-stick, surface, and ribbon
4. THE Structure_Viewer SHALL support color schemes: chain, residue, bfactor, hydrophobicity, and secondary_structure
5. WHEN binding sites are detected, THE Structure_Viewer SHALL display them ranked by druggability_score in descending order with residue lists, center coordinates, volume, and source (fpocket, p2rank, or ligand-based)
6. WHEN a researcher clicks "Import to Design Studio", THE Structure_Viewer SHALL build a Handoff_Payload containing the target_id, selected binding_site, and structure_source, and navigate to the Design_Studio page
7. IF the ESM Models API fails, THEN THE Structure_Viewer SHALL fall back to AlphaFold DB, then RCSB PDB, and display a degraded status indicator if all sources fail
8. WHEN structure data is fetched, THE Structure_Viewer SHALL always populate the Sequence sub-tab with protein sequence data regardless of which structure source succeeded
9. THE Structure_Viewer SHALL load and render a 3D structure within 2000ms

### Requirement 7: Design Studio (All Plugins Working)

**User Story:** As a researcher, I want a fully functional molecule design studio where all plugins (RDKit, AutoDock Vina, fpocket, GPU Acceleration, Diffusion Model) are operational, so that I can design, dock, score, and optimize drug candidates, and send results to Research Labs.

#### Acceptance Criteria

1. THE Design_Studio SHALL display a plugin status panel showing the availability status of each plugin: RDKit, AutoDock Vina, fpocket, GPU Acceleration, and Diffusion Model
2. WHEN the RDKit plugin is available, THE Design_Studio SHALL compute molecular descriptors, generate analogs (scaffold hopping, R-group enumeration), validate SMILES strings, and compute molecular fingerprints
3. WHEN the AutoDock Vina plugin is available, THE Design_Studio SHALL prepare ligands and receptors (PDBQT format) and execute molecular docking with configurable search parameters
4. WHEN the fpocket plugin is available, THE Design_Studio SHALL detect and rank binding site pockets from PDB structures by druggability score
5. WHEN the Diffusion Model plugin is available, THE Design_Studio SHALL generate de novo molecule candidates conditioned on a binding site pocket geometry
6. WHEN a docking job is submitted, THE Design_Studio SHALL run it as a background job and report progress via WebSocket events within 30000ms
7. WHEN a researcher clicks "Send to Research Lab", THE Design_Studio SHALL build a SendToLabPayload containing the SMILES, target PDB, binding site, scores, and ADMET results, and navigate to the selected Research_Lab
8. IF a plugin is not detected, THEN THE Design_Studio SHALL display a clear "not detected" status with installation instructions and provide degraded alternatives where possible (e.g., CPU-only mode for GPU)

### Requirement 8: Clinical Design (10-Step Workflow)

**User Story:** As a clinical researcher, I want a structured 10-step clinical design workflow, so that I can systematically progress from disease context through trial design to a go/no-go decision with evidence backing at each step.

#### Acceptance Criteria

1. THE Clinical_Workflow SHALL present 10 sequential steps: Disease Context & Unmet Need, Target Validation Evidence, Biomarker Strategy, Patient Population Definition, Endpoint Selection, Comparator & Control Strategy, Safety Signal Assessment, Regulatory Pathway Analysis, Trial Design Parameters, and Go/No-Go Decision Framework
2. WHEN a researcher completes a Clinical_Workflow step, THE Clinical_Workflow SHALL save the step outputs with evidence backing and update the step status to "completed"
3. WHEN a researcher attempts to start a Clinical_Workflow step, THE Clinical_Workflow SHALL verify that all previous steps are either "completed" or "skipped"
4. IF a Clinical_Workflow step fails due to missing evidence or computation error, THEN THE Clinical_Workflow SHALL mark the step as "error" with a detailed error message and allow retry or skip with justification
5. WHEN a Clinical_Workflow step is completed, THE Clinical_Workflow SHALL preserve the Provenance_Chain from all previous steps in the workflow
6. THE Clinical_Workflow SHALL complete each individual step within 5000ms

### Requirement 9: SynthArena (Fully Populated)

**User Story:** As a researcher, I want a fully functional drug candidate comparison arena with scenario simulation, evidence-backed scoring, debate simulation, and dossier generation, so that I can systematically evaluate and compare drug candidates.

#### Acceptance Criteria

1. THE SynthArena SHALL allow creation of sessions with at least 2 compounds, each with a name, SMILES string, source, and evidence note
2. THE SynthArena SHALL compute a Scoring_Matrix with configurable criteria and weights, where each compound is scored across all criteria
3. WHEN scoring is computed, THE SynthArena SHALL calculate the overall score for each compound as the weighted average of individual criterion scores
4. THE SynthArena SHALL support scenario simulation where researchers define scenarios with seed entities, weights, and run simulations that produce trajectories, risk factors, contradictions, and evidence support scores
5. THE SynthArena SHALL execute multi-agent debate simulations where specialist agents argue for and against each compound with evidence-backed reasoning
6. WHEN a debate completes, THE SynthArena SHALL produce a dossier_consensus with an evidence-backed winner rationale and full debate_history
7. IF the AI debate simulation fails, THEN THE SynthArena SHALL return partial scores from available criteria and mark the debate as "incomplete"

### Requirement 10: Research Labs (Radical Redesign)

**User Story:** As a researcher, I want all 8 research labs fully functional with real computation, so that I can run specialized analyses (target discovery, pocket detection, molecule generation, ADMET prediction, retrosynthesis, vaccine design, metabolic engineering, pharmacogenomics) and get actionable results.

#### Acceptance Criteria

1. THE application SHALL provide 8 Research_Labs: Target Discovery, Pocket, Molecule Generation, ADMET, Retrosynthesis, Vaccine, Metabolic Engineering, and Pharmacogenomics
2. WHEN a Target Discovery lab run is submitted with a disease_id, THE Research_Lab SHALL return ranked targets, a PPI network, and relevant pathways
3. WHEN a Pocket lab run is submitted with a pdb_id, THE Research_Lab SHALL return detected binding site pockets with druggability scores and visualization data
4. WHEN a Molecule Generation lab run is submitted with a target PDB and binding site, THE Research_Lab SHALL generate candidate molecules using the selected method (reinforcement learning, diffusion, or enumeration) with optimization history
5. WHEN an ADMET lab run is submitted with a list of SMILES strings, THE Research_Lab SHALL return ADMET predictions with conformal prediction confidence intervals
6. WHEN a Retrosynthesis lab run is submitted with a target SMILES, THE Research_Lab SHALL return synthesis routes with feasibility scores
7. WHEN a Vaccine lab run is submitted with an antigen sequence and target pathogen, THE Research_Lab SHALL return predicted epitopes and vaccine candidates
8. WHEN a Metabolic Engineering lab run is submitted with an organism and target metabolite, THE Research_Lab SHALL return flux analysis results and optimized pathway modifications
9. WHEN a Pharmacogenomics lab run is submitted with a drug_id, THE Research_Lab SHALL return pharmacogene interactions and dosing recommendations
10. WHEN any Research_Lab run completes, THE Research_Lab SHALL include a Provenance_Chain tracking all data sources and computations performed

### Requirement 11: Contradiction & Similarity

**User Story:** As a researcher, I want to find both contradictions AND similarities across evidence sources for a given query, so that I can identify conflicting claims and consensus patterns in the scientific literature.

#### Acceptance Criteria

1. WHEN a researcher submits a query, THE Contradiction_Engine SHALL search across evidence sources and return both contradiction pairs and similarity clusters
2. WHEN contradictions are found, THE Contradiction_Engine SHALL classify each contradiction by type (directional, temporal, magnitude, causal) and severity (high, medium, low)
3. WHEN contradictions are found, THE Contradiction_Engine SHALL provide an explanation of the contradiction and a resolution suggestion when possible
4. WHEN contradictions are found, each ContradictionPair SHALL reference claims from two different sources, not from the same source
5. WHEN similarities are found, THE Contradiction_Engine SHALL group similar claims into clusters with a similarity score, shared entities, and consensus strength (strong, moderate, weak)
6. WHEN results are returned, THE Contradiction_Engine SHALL include an evidence landscape summary with the overall distribution of supporting and contradicting evidence

### Requirement 12: PICO Verification

**User Story:** As a clinical researcher, I want working PICO extraction from scientific literature, so that I can systematically extract Population, Intervention, Comparison, and Outcome elements to evaluate clinical evidence quality.

#### Acceptance Criteria

1. WHEN a researcher submits a query, THE PICO_Extractor SHALL search relevant publications and extract PICO elements (Population, Intervention, Comparison, Outcome) from each
2. WHEN PICO elements are extracted, each PICOElement SHALL include the extracted text, associated entities, qualifiers, and a confidence score
3. WHEN PICO extractions are returned, THE PICO_Extractor SHALL include the study design, sample size (when available), and overall extraction confidence for each publication
4. WHEN PICO extractions are complete, THE PICO_Extractor SHALL generate a summary and an evidence quality assessment across all extracted publications

### Requirement 13: Page Removals

**User Story:** As a platform user, I want the Operations, Reports & Export, and Notes tabs removed from the navigation, so that the interface is streamlined to focus on core research functionality.

#### Acceptance Criteria

1. THE application SHALL NOT display an "Operations" tab or page in the primary navigation
2. THE application SHALL NOT display a "Reports & Export" tab or page in the primary navigation
3. THE application SHALL NOT display a "Notes" tab or page in the primary navigation
4. WHEN a user navigates to a removed page URL directly, THE application SHALL redirect to the Cockpit page

### Requirement 14: Settings (Elaborated)

**User Story:** As a platform user, I want comprehensive settings covering all platform configuration areas, so that I can customize the platform behavior, manage data sources, configure runtime options, and monitor system health.

#### Acceptance Criteria

1. THE Settings page SHALL include sections for: General, Sources, Runtime, Security, Storage, Notifications, Export, Accessibility, Advanced, and Diagnostics
2. WHEN a researcher opens the Sources section, THE Settings page SHALL display the health status and configuration of all Connectors with the ability to enable/disable individual sources and manage API keys
3. WHEN a researcher opens the Runtime section, THE Settings page SHALL allow selection between hosted and local inference modes and model selection
4. WHEN a researcher opens the Security section, THE Settings page SHALL display authentication settings, RBAC role management, and session configuration
5. WHEN a researcher opens the Diagnostics section, THE Settings page SHALL display system health metrics, performance data, and database connection status
6. WHEN a researcher opens the Accessibility section, THE Settings page SHALL provide font size, contrast, and other A11Y preference controls


### Requirement 15: Universal API Response Envelope

**User Story:** As a frontend developer, I want every API response wrapped in a consistent envelope with status, data, provenance, and timing, so that I can handle success, partial, degraded, and error states uniformly across the application.

#### Acceptance Criteria

1. THE Response_Envelope SHALL include fields: request_id, trace_id, status (ok | partial | degraded | error), data, warnings, errors, provenance, runtime_context, and timing
2. WHEN an API response has status "error", THE Response_Envelope SHALL include at least one ErrorDetail with code, message, recoverable flag, and suggested_action
3. WHEN an API response has status "degraded", THE Response_Envelope SHALL list the degraded sources in provenance.sources_degraded with a count greater than zero
4. THE Response_Envelope SHALL never expose raw tracebacks or internal error details to the client; all errors SHALL use structured ErrorDetail objects
5. THE Response_Envelope SHALL always include timing information with started_at, finished_at, and elapsed_ms fields

### Requirement 16: Data Source Connectors

**User Story:** As a researcher, I want the platform to fetch data from 140+ scientific data sources across 9 evidence families, so that I can access comprehensive biomedical evidence for my research.

#### Acceptance Criteria

1. THE Connector system SHALL support data sources across 9 evidence families: literature, disease, target, pathway, compound, genetics, clinical, population, and regulatory
2. WHEN a Connector is queried, THE Connector SHALL return results with source attribution including the source name, external record ID, URL, and retrieval timestamp
3. IF a Connector does not respond within 8000ms, THEN THE Connector system SHALL mark the source as degraded and continue with results from other sources
4. IF a Connector fails 3 consecutive times, THEN THE Connector system SHALL activate a circuit breaker that skips the source for 60 seconds before retrying
5. WHEN Connectors are queried in parallel, THE Connector system SHALL aggregate results from all successful sources and include degraded source information in the Provenance_Chain

### Requirement 17: Authentication, Authorization, and Security

**User Story:** As a platform administrator, I want JWT + OAuth2 authentication with role-based access control enforced at every API endpoint, so that the platform is secure and access is properly controlled.

#### Acceptance Criteria

1. THE application SHALL authenticate users via JWT tokens with OAuth2 support
2. THE application SHALL enforce RBAC at every API endpoint via JWT dependency injection
3. THE application SHALL rate-limit API requests to 120 requests per minute for authenticated users and 10 requests per minute for unauthenticated users
4. THE application SHALL store all API keys (including the ESM Models API key) in environment variables, never exposing them to the frontend
5. THE application SHALL validate and sanitize all user inputs including SMILES strings, entity names, and search queries
6. THE application SHALL log all data access and modifications with user ID and timestamp for audit purposes
7. THE application SHALL use HTTPS for all external API calls to Connectors
8. IF an unauthenticated user attempts to access a protected endpoint, THEN THE application SHALL return a 401 status with a structured ErrorDetail

### Requirement 18: Performance SLAs

**User Story:** As a researcher, I want the platform to meet defined performance targets for all major operations, so that the research workflow is responsive and productive.

#### Acceptance Criteria

1. WHEN a Cockpit general query is submitted, THE Cockpit SHALL return the first partial response (via SSE streaming) within 3000ms
2. WHEN a Knowledge_Graph with up to 500 nodes is rendered, THE Knowledge_Graph SHALL complete rendering within 500ms
3. WHEN a 3D structure is loaded, THE Structure_Viewer SHALL complete loading and rendering within 2000ms
4. WHEN a Design_Studio docking job is submitted, THE Design_Studio SHALL complete the job within 30000ms and report progress via WebSocket
5. WHEN a Clinical_Workflow step is executed, THE Clinical_Workflow SHALL complete the step within 5000ms
6. THE application SHALL use Redis caching with appropriate TTLs: connector responses (30 min), embeddings (24 hours), HTTP responses (5 min), graph queries (15 min)

### Requirement 19: Knowledge Graph Construction Invariants

**User Story:** As a researcher, I want knowledge graphs to always have properly colored nodes and evidence-backed edges, so that the visualization is consistent and every connection is traceable to its source.

#### Acceptance Criteria

1. WHEN a Knowledge_Graph is constructed, every node SHALL have a color field set to the value from ENTITY_COLORS corresponding to the node's Entity_Type
2. WHEN a Knowledge_Graph is constructed, every edge SHALL have a non-empty reason field explaining why the two nodes are connected
3. WHEN a Knowledge_Graph is constructed, every edge SHALL have at least one evidence_id linking to the source evidence
4. WHEN a Knowledge_Graph is constructed, node sizes SHALL be computed based on betweenness centrality scores

### Requirement 20: Real-Time Progress and WebSocket Communication

**User Story:** As a researcher, I want real-time progress updates for long-running operations via WebSocket, so that I can monitor the status of background jobs without polling.

#### Acceptance Criteria

1. WHEN a long-running background job is started (docking, lab run, deep evidence search), THE application SHALL send progress events via WebSocket to the requesting client
2. WHEN a background job completes, THE application SHALL send a completion event via WebSocket with the final result or a reference to retrieve it
3. IF a WebSocket connection is lost during a background job, THEN THE application SHALL allow the client to reconnect and retrieve the current job status via a REST endpoint

### Requirement 21: Database Schema and Data Integrity

**User Story:** As a platform developer, I want all database schema changes managed via Alembic migrations with proper constraints, so that data integrity is maintained across deployments.

#### Acceptance Criteria

1. THE application SHALL manage all PostgreSQL schema changes via Alembic migrations, never manual DDL
2. THE application SHALL use parameterized queries or SQLAlchemy ORM for all database operations, never string concatenation
3. THE application SHALL use database transactions for multi-step operations to ensure atomicity
4. THE application SHALL maintain indexes on frequently queried columns for entity lookups, evidence searches, and graph traversals

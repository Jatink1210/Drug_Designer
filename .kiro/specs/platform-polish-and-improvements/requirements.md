# Requirements Document

## Introduction

The Drug Designer platform has multiple critical issues affecting usability, visual quality, and functional correctness. This spec addresses seven areas: UI text overflow and professional polish, Pathway page redesign, Settings page functional feedback, AutoDock Vina integration, improved contradiction and similarity detection using biomedical NLP, Playwright visual regression testing, and backend correctness verification. The goal is to transform the platform from a functional prototype into a polished, minimalistic, production-quality biomedical research tool.

## Glossary

- **Platform**: The Drug Designer web application comprising a React 19 / TailwindCSS 4 frontend and a FastAPI / PostgreSQL backend.
- **UI_Shell**: The top-level layout components including LeftRail navigation, page headers, and content containers.
- **Card_Container**: A bounded rectangular UI element used to display discrete information (pathway results, contradiction claims, entity details, metric summaries).
- **Text_Overflow_Guard**: A CSS utility pattern combining `overflow-hidden`, `text-ellipsis`, and `line-clamp` to prevent text from exceeding its container boundaries.
- **Pathway_Explorer**: The PathwaysPage.tsx component providing multi-source pathway search, enrichment, and interactive visualization via BiologicalPathwayWorkbench.
- **Settings_Engine**: The combined frontend SettingsPage.tsx and backend `/api/v1/settings` system that persists and applies user preferences.
- **Docking_Engine**: The backend DockingService class that integrates AutoDock Vina, smina, or gnina for molecular docking calculations.
- **Contradiction_Detector**: The backend `contradiction_detector.py` service that identifies conflicting claims across biomedical evidence sources.
- **Similarity_Analyzer**: The component within the contradiction detection system that clusters evidence items by shared entities and semantic similarity.
- **NLI_Model**: A Natural Language Inference model (e.g., BioNLI, SciNLI) that classifies sentence pairs as entailment, contradiction, or neutral.
- **Biomedical_Embeddings**: Dense vector representations of biomedical text produced by models such as PubMedBERT, BioBERT, or BioSentVec.
- **Visual_Test_Suite**: A Playwright-based test harness that captures screenshots and validates layout properties across pages and viewports.
- **Toast_Notification**: A transient UI message that appears briefly to confirm an action was completed or report an error.
- **Viewport_Breakpoint**: A screen width threshold (320px, 768px, 1024px, 1440px) at which the layout adapts its structure.

## Requirements

### Requirement 1: Text Overflow Prevention Across All Pages

**User Story:** As a researcher, I want all text content to remain within its container boundaries, so that the interface looks professional and information is readable without visual artifacts.

#### Acceptance Criteria

1. THE Platform SHALL apply Text_Overflow_Guard (overflow-hidden, text-ellipsis, or line-clamp) to every Card_Container that displays dynamic text content.
2. WHEN a navigation badge in the LeftRail exceeds 3 characters, THE UI_Shell SHALL truncate the badge text with ellipsis and display the full value on hover via a tooltip.
3. WHEN a pathway result card title exceeds the card width, THE Pathway_Explorer SHALL truncate the title with ellipsis and expose the full title via a title attribute or tooltip.
4. WHEN a contradiction claim text exceeds 3 lines within a claim card, THE Contradiction_Detector UI SHALL clamp the text to 3 lines with a visual overflow indicator and provide expand-on-click behavior.
5. WHEN an entity name in EntityIntelligence or KnowledgeGraph exceeds its label container width, THE Platform SHALL truncate the name with ellipsis.
6. WHEN a WorkspacePage metric card title or value exceeds the card width, THE Platform SHALL truncate the content with ellipsis.
7. THE Platform SHALL wrap all data tables in a horizontally scrollable container so that table content is accessible on viewports narrower than the table's natural width.

### Requirement 2: Minimalistic Professional Visual Design

**User Story:** As a researcher, I want the platform to have a clean, minimalistic design, so that I can focus on scientific data without visual clutter.

#### Acceptance Criteria

1. THE Platform SHALL use a consistent spacing scale derived from the existing CSS custom properties (--shadow-xs through --shadow-lg, --radius through --radius-xl) across all pages.
2. THE Platform SHALL limit the color palette to the defined design tokens (--accent, --text-primary, --text-secondary, --text-muted, --bg-app, --bg-surface, --bg-elevated) and semantic status colors (--success, --warning, --error, --info).
3. THE Platform SHALL use the defined font stack (Inter for display, JetBrains Mono for code) consistently across all pages without introducing additional typefaces.
4. WHEN a page contains more than 5 Card_Containers, THE Platform SHALL organize them in a grid layout with consistent gap spacing rather than a single vertical stack.
5. THE Platform SHALL apply consistent border-radius values (--radius for small elements, --radius-lg for cards, --radius-xl for modals) across all interactive elements.
6. WHEN the user switches between light and dark themes, THE Platform SHALL update all surface colors, text colors, border colors, and shadow values to their dark-mode equivalents defined in the [data-theme="dark"] CSS block.

### Requirement 3: Responsive Layout Across Viewport Breakpoints

**User Story:** As a researcher using different devices, I want the platform to adapt its layout to my screen size, so that I can work effectively on mobile, tablet, and desktop.

#### Acceptance Criteria

1. WHEN the viewport width is below 768px, THE UI_Shell SHALL collapse the LeftRail navigation into a hamburger menu overlay.
2. WHEN the viewport width is below 768px, THE Platform SHALL stack multi-column card grids into a single column layout.
3. WHEN the viewport width is between 768px and 1024px, THE Platform SHALL display card grids in a 2-column layout.
4. WHEN the viewport width is above 1024px, THE Platform SHALL display card grids in a 3-column or wider layout as appropriate for the content density.
5. THE Platform SHALL render all modal and drawer components at a maximum width of 90vw on viewports below 768px.
6. WHEN the viewport width is 320px, THE Platform SHALL remain fully functional with no horizontal page-level scrollbar.

### Requirement 4: Pathway Page Redesign

**User Story:** As a researcher, I want the Pathway Explorer to provide paginated results, side-by-side comparison, persistent enrichment results, and improved visualization, so that I can efficiently analyze biological pathways.

#### Acceptance Criteria

1. WHEN a pathway search returns more than 25 results per source, THE Pathway_Explorer SHALL provide pagination controls (next, previous, page number) to navigate through the full result set.
2. WHEN the user selects compare mode with two pathways, THE Pathway_Explorer SHALL display a side-by-side diff view highlighting genes and interactions unique to each pathway and those shared between them.
3. WHEN the user runs a gene list enrichment analysis, THE Pathway_Explorer SHALL persist the enrichment results to the backend so they are available on page reload.
4. THE Pathway_Explorer SHALL display disease context information (affected genes, therapeutic targets) as visual annotations on the pathway diagram when disease context is available from the cockpit handoff.
5. THE Pathway_Explorer SHALL render the BiologicalPathwayWorkbench with a force-directed or hierarchical layout algorithm that minimizes edge crossings and provides zoom and pan controls.
6. WHEN the user exports a pathway, THE Pathway_Explorer SHALL offer SVG, PNG, and JSON export formats.

### Requirement 5: Settings Page Functional Feedback

**User Story:** As a user, I want to see immediate, visible confirmation that my settings changes take effect, so that I trust the platform is responding to my configuration.

#### Acceptance Criteria

1. WHEN the user saves settings changes, THE Settings_Engine SHALL display a Toast_Notification confirming the save was successful, including which settings category was updated.
2. WHEN the user changes the theme (light, dark, system), THE Settings_Engine SHALL apply the theme change to all visible components within 200ms without requiring a page reload.
3. WHEN the user changes the runtime mode (hosted, local, auto), THE Settings_Engine SHALL display the current active runtime status and update it within 5 seconds of saving.
4. WHEN the user navigates to the Sources tab, THE Settings_Engine SHALL fetch and display real-time connector health status with a visible timestamp showing when the health check was last performed.
5. IF the settings save request fails, THEN THE Settings_Engine SHALL display an error Toast_Notification with the failure reason and retain the user's unsaved changes in the form.
6. WHEN the user changes the font size setting, THE Settings_Engine SHALL apply the font size change to all text elements immediately as a preview before saving.
7. WHEN the user enables reduced motion, THE Settings_Engine SHALL disable all CSS animations and transitions across the Platform immediately.

### Requirement 6: AutoDock Vina Automatic Installation and Integration

**User Story:** As a computational chemist, I want AutoDock Vina to be automatically installed and functional without manual setup, so that I can run molecular docking calculations immediately from the platform.

#### Acceptance Criteria

1. THE Docking_Engine SHALL automatically download and install the AutoDock Vina binary (version 1.2.5 or latest stable) on first startup if the binary is not found on the system PATH or in the platform's local tools directory.
2. THE Docking_Engine SHALL download the Vina binary from the official GitHub releases (https://github.com/ccsb-scripps/AutoDock-Vina/releases) and place it in a platform-managed tools directory (e.g., `apps/api/tools/bin/`) with executable permissions.
3. THE Docking_Engine SHALL detect the host operating system (Windows, Linux, macOS) and download the appropriate platform-specific Vina binary.
4. THE Docking_Engine SHALL also automatically install fpocket via conda-forge or download the pre-built binary if not found on the system.
5. THE Docking_Engine SHALL check for the presence of the Vina and fpocket binaries on startup and report their availability status via the `/api/v1/design/plugins` endpoint.
6. WHEN the automatic download fails (network error, permission denied), THE Docking_Engine SHALL log the error, report the plugin as "Not Available — Auto-Install Failed" with the specific error reason, and provide manual installation instructions as a fallback.
7. WHEN the user initiates a docking run, THE Docking_Engine SHALL validate that the receptor file (PDB/PDBQT), ligand file (PDBQT/SDF), grid center coordinates, and box dimensions are all provided before execution.
8. WHEN a docking run completes, THE Docking_Engine SHALL parse the output PDBQT file and return ranked poses with binding affinity (kcal/mol), RMSD lower bound, and RMSD upper bound for each pose.
9. WHEN a docking run exceeds the 600-second timeout, THE Docking_Engine SHALL terminate the process and return a timeout error with the partial log output.
10. THE Docking_Engine SHALL provide a `/api/v1/design/plugins/install` endpoint that triggers on-demand re-installation of missing tool binaries (Vina, fpocket) and returns the installation status.

### Requirement 7: Improved Contradiction Detection Using Biomedical NLP

**User Story:** As a biomedical researcher, I want contradiction detection to use semantic understanding rather than keyword matching, so that nuanced contradictions in the literature are accurately identified.

#### Acceptance Criteria

1. THE Contradiction_Detector SHALL use Biomedical_Embeddings (PubMedBERT or BioSentVec) to compute semantic similarity between claim pairs, replacing the Jaccard similarity threshold of 0.3 with a cosine similarity threshold on dense vectors.
2. THE Contradiction_Detector SHALL use an NLI_Model fine-tuned on biomedical text to classify claim pairs as entailment, contradiction, or neutral, replacing the keyword-based opposing word pair heuristic as the primary detection method.
3. WHEN the NLI_Model is not available (model not downloaded or inference fails), THE Contradiction_Detector SHALL fall back to the existing keyword heuristic and report that results are from the fallback method.
4. THE Contradiction_Detector SHALL extract experimental context (in vivo vs in vitro, model organism, cell line, methodology) from each claim and include context differences as an explanatory factor in contradiction reports.
5. THE Contradiction_Detector SHALL perform temporal reasoning by comparing publication dates and noting when contradictions may reflect evolving scientific understanding rather than genuine disagreement.
6. THE Similarity_Analyzer SHALL cluster evidence items using cosine similarity on Biomedical_Embeddings with a configurable threshold (default 0.7), replacing the Jaccard similarity approach.
7. THE Contradiction_Detector SHALL assign a confidence score (0.0 to 1.0) to each detected contradiction based on the NLI_Model probability, context alignment, and source quality weighting.

### Requirement 8: Improved Similarity Detection for Biomedicine

**User Story:** As a biomedical researcher, I want similarity detection to find semantically related findings across sources with high accuracy, so that I can identify corroborating evidence and complementary research.

#### Acceptance Criteria

1. THE Similarity_Analyzer SHALL identify shared findings across evidence sources by computing pairwise cosine similarity on Biomedical_Embeddings for all claim pairs.
2. WHEN two claims have a cosine similarity above the configurable threshold, THE Similarity_Analyzer SHALL classify the relationship as "shared_finding" (same conclusion) or "complementary_evidence" (different angle, compatible conclusion).
3. THE Similarity_Analyzer SHALL extract and compare entity mentions (genes, proteins, drugs, diseases, pathways) between similar claims to provide structured explanations of why claims are related.
4. THE Similarity_Analyzer SHALL group similar claims into clusters and assign a representative summary to each cluster.
5. WHEN the user searches for contradictions, THE Similarity_Analyzer SHALL also return similarity results in a separate tab, ranked by confidence score.
6. THE Similarity_Analyzer SHALL support filtering results by entity type (gene, protein, drug, disease, pathway) and by source database (PubMed, ClinicalTrials, ChEMBL, OpenTargets).

### Requirement 9: Playwright Visual Regression Testing

**User Story:** As a developer, I want automated visual tests that detect layout regressions, so that UI issues like text overflow and broken responsive layouts are caught before deployment.

#### Acceptance Criteria

1. THE Visual_Test_Suite SHALL capture full-page screenshots of every primary page (Cockpit, Evidence Search, Entity Intelligence, Knowledge Graph, Pathways, Structure, Design Studio, Clinical Design, SynthArena, Labs, Contradiction & Similarity, PICO, Settings) at 1440px viewport width.
2. THE Visual_Test_Suite SHALL capture screenshots of every primary page at 768px and 320px viewport widths to verify responsive layout behavior.
3. THE Visual_Test_Suite SHALL verify that no element on any page has visible horizontal overflow by checking that no element's scrollWidth exceeds its clientWidth by more than 1px.
4. THE Visual_Test_Suite SHALL verify that the LeftRail navigation collapses to a hamburger menu at viewports below 768px.
5. THE Visual_Test_Suite SHALL verify that all Card_Containers have text content that does not exceed the container's bounding box.
6. WHEN a visual regression test fails, THE Visual_Test_Suite SHALL produce a diff image highlighting the changed regions and save it to the test artifacts directory.
7. THE Visual_Test_Suite SHALL complete a full test run across all pages and viewports within 120 seconds.

### Requirement 10: Backend Health Verification and Error Reporting

**User Story:** As a user, I want the platform to honestly report which backend services are available and which are not, so that I understand what functionality is operational.

#### Acceptance Criteria

1. THE Platform SHALL provide a `/api/v1/health` endpoint that reports the availability status of PostgreSQL, Redis, Qdrant, and all external connector services.
2. WHEN a backend service is unavailable, THE Platform SHALL display a degraded status indicator on the relevant page rather than showing a blank screen or unhandled error.
3. THE Platform SHALL report plugin availability (Vina, fpocket, RDKit, Mol*) accurately in the Design Studio, reflecting actual binary presence on the system rather than hardcoded status values.
4. WHEN an API request fails due to a backend service being unavailable, THE Platform SHALL return a structured error response with error code, human-readable message, and suggested remediation action.
5. IF the database connection fails, THEN THE Platform SHALL display a connection error page with retry functionality rather than an unhandled exception.
6. THE Platform SHALL log all backend service health check results with timestamps so that intermittent failures can be diagnosed from the log history.

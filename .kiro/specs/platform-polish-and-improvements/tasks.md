# Implementation Plan: Platform Polish and Improvements

## Overview

This plan transforms the Drug Designer platform from a functional prototype into a polished, production-quality biomedical research tool. Implementation is organized in 10 phases: CSS overflow utilities, responsive layout, pathway page redesign, settings feedback, tool auto-installer, NLP contradiction engine, similarity analyzer, health router enhancement, Playwright visual tests, and backend error reporting. Each phase builds incrementally on the previous, with checkpoints to validate progress.

**Tech Stack:** React 19 / TypeScript / Vite 8 / TailwindCSS 4 (frontend), FastAPI / Python (backend), Vitest + fast-check (frontend tests), pytest + Hypothesis (backend tests), Playwright (visual tests).

## Tasks

- [x] 1. Text Overflow Guard System and CSS Utilities
  - [x] 1.1 Add global text overflow utility classes to `apps/web/src/index.css`
    - Add `.text-overflow-guard` (overflow-hidden, text-ellipsis, whitespace-nowrap)
    - Add `.text-clamp-2` and `.text-clamp-3` (line-clamp utilities)
    - Add `.table-scroll-container` (overflow-x-auto with -webkit-overflow-scrolling: touch)
    - Add `.reduce-motion` class that disables all CSS animations and transitions
    - _Requirements: 1.1, 1.7, 5.7_

  - [x] 1.2 Implement badge truncation with tooltip in `apps/web/src/components/shell/LeftRail.tsx`
    - When badge value exceeds 3 characters, truncate with ellipsis
    - Add `title` attribute with full value for native tooltip
    - Wrap badge in a Radix Tooltip component for hover display
    - Apply `max-w-[40px] truncate` to the badge `<span>`
    - _Requirements: 1.2_

  - [ ]* 1.3 Write property test for badge truncation (fast-check)
    - **Property 1: Badge Truncation**
    - For any string value longer than 3 characters, verify the rendered badge text is truncated and the tooltip contains the full original value
    - **Validates: Requirements 1.2**

  - [x] 1.4 Apply text overflow guards to all page components
    - `PathwaysPage.tsx`: Add `truncate` to pathway result card titles, add `title` attribute with full name
    - `Contradictions.tsx`: Add `line-clamp-3` to claim card text with expand-on-click behavior
    - Entity Intelligence / Knowledge Graph pages: Add `truncate` to entity name labels
    - Workspace/Cockpit page: Add `truncate` to metric card titles and values
    - Wrap all `<table>` elements in `.table-scroll-container` div across all pages
    - _Requirements: 1.1, 1.3, 1.4, 1.5, 1.6, 1.7_

- [x] 2. Responsive Layout System
  - [x] 2.1 Add responsive card grid CSS and breakpoint utilities to `apps/web/src/index.css`
    - Add `.card-grid` class with mobile-first responsive columns (1-col → 2-col at 768px → 3-col at 1024px)
    - Ensure modal/drawer max-width is 90vw on viewports below 768px
    - Verify no horizontal page-level scrollbar at 320px viewport
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6_

  - [x] 2.2 Apply responsive card grid to all pages with multiple Card_Containers
    - Replace single-column stacks with `.card-grid` on Cockpit, Evidence Search, Entity Intelligence, Design Studio, and other pages with 5+ cards
    - Ensure consistent gap spacing using design tokens
    - _Requirements: 2.4, 3.2, 3.3, 3.4_

  - [x] 2.3 Verify LeftRail hamburger collapse behavior at mobile breakpoints
    - Confirm `sidebar-desktop` transforms to hamburger overlay below 768px (already partially implemented in CSS)
    - Ensure hamburger button is visible and functional at mobile viewports
    - Test overlay dismiss on click
    - _Requirements: 3.1_

- [x] 3. Checkpoint — Verify UI overflow and responsive layout
  - Ensure all text overflow guards are applied, responsive grids work at all breakpoints, and no horizontal scrollbar appears at 320px. Ask the user if questions arise.

- [x] 4. Settings Page Feedback System
  - [x] 4.1 Implement toast notification system in `apps/web/src/components/ui/Toast.tsx` (NEW)
    - Create a `ToastProvider` context and `useToast` hook
    - Support types: success, error, info, warning
    - Each toast shows title, optional description, auto-dismisses after 4000ms
    - Position toasts in bottom-right corner with stacking
    - Respect reduced-motion preference (no slide animation when enabled)
    - _Requirements: 5.1, 5.5_

  - [x] 4.2 Integrate toast notifications into `apps/web/src/pages/SettingsPage.tsx`
    - On successful save: show success toast with category name (e.g., "General settings saved")
    - On save failure: show error toast with failure reason, retain unsaved form state
    - Wire toast into the existing `saveMut.onSuccess` and `saveMut.onError` callbacks
    - _Requirements: 5.1, 5.5_

  - [x] 4.3 Implement immediate theme application in SettingsPage
    - Apply theme change to `document.documentElement` via `data-theme` attribute within 200ms
    - No page reload required — CSS variables update instantly via attribute selector
    - Wire into the theme selector `handleChange` so preview is immediate (before save)
    - _Requirements: 5.2_

  - [x] 4.4 Implement font size preview and reduced motion toggle
    - Font size change: immediately set `document.documentElement.style.fontSize` as preview before save
    - Reduced motion: toggle `.reduce-motion` class on `<html>` element immediately
    - The `.reduce-motion` class (added in task 1.1) disables all CSS animations/transitions
    - _Requirements: 5.6, 5.7_

  - [x] 4.5 Add runtime status display and connector health to Settings Sources tab
    - After saving runtime mode, display current active runtime status and update within 5 seconds
    - In Sources tab, fetch real-time connector health status with visible timestamp
    - Use the existing `/api/v1/diagnostics` endpoint connector pings data
    - _Requirements: 5.3, 5.4_

  - [ ]* 4.6 Write unit tests for toast notification and theme application (Vitest)
    - Test toast renders with correct type, title, description
    - Test toast auto-dismisses after duration
    - Test theme application sets correct data-theme attribute
    - Test font size preview updates document root font size
    - Test reduced motion toggles class on html element
    - _Requirements: 5.1, 5.2, 5.5, 5.6, 5.7_

- [x] 5. Checkpoint — Verify settings feedback
  - Ensure toast notifications appear on save/error, theme switches instantly, font size previews correctly, and reduced motion disables animations. Ask the user if questions arise.

- [x] 6. ToolInstaller Service (Backend)
  - [x] 6.1 Create `apps/api/services/tool_installer.py` with ToolInstaller class
    - Implement `detect_os()` returning (system, machine) tuple
    - Implement `PLATFORM_MAP` for Vina binaries (Linux/x86_64, Darwin/x86_64, Darwin/arm64, Windows/AMD64)
    - Implement `get_download_url(tool)` resolving platform-specific GitHub release URL
    - Implement `install_tool(tool)` with httpx streaming download, checksum verification, chmod 755
    - Implement `check_availability()` checking PATH and `apps/api/tools/bin/` directory
    - Implement `ensure_tools_available()` for startup auto-install
    - Handle fpocket installation via conda-forge or pre-built binary download
    - Log errors and provide manual installation instructions on failure
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [ ]* 6.2 Write property test for OS detection to download URL mapping (Hypothesis)
    - **Property 4: OS Detection Maps to Correct Download URL**
    - For any supported (system, machine) tuple, verify `get_download_url` returns a valid URL containing the platform-specific binary name
    - **Validates: Requirements 6.3**

  - [x] 6.3 Integrate ToolInstaller into DockingService at `apps/api/services/docking_service.py`
    - Replace `_find_executable` to check `apps/api/tools/bin/` in addition to PATH
    - Add docking input validation: require receptor_path, ligand_path, center, box_size before execution
    - Add 600-second timeout with process termination and partial log return
    - Enhance `_parse_vina_output` to return rank, affinity_kcal, rmsd_lb, rmsd_ub per pose
    - _Requirements: 6.7, 6.8, 6.9_

  - [ ]* 6.4 Write property test for docking input validation (Hypothesis)
    - **Property 5: Docking Input Validation Rejects Incomplete Requests**
    - For any DockingRequest missing required fields, verify a validation error is returned
    - **Validates: Requirements 6.7**

  - [ ]* 6.5 Write property test for Vina output parsing (Hypothesis)
    - **Property 6: Vina Output Parsing Extracts Complete Pose Data**
    - For any valid PDBQT output with MODEL/REMARK VINA RESULT lines, verify parsing produces poses with rank, affinity_kcal, rmsd_lb, rmsd_ub
    - **Validates: Requirements 6.8**

  - [x] 6.6 Add plugin install endpoint to `apps/api/routers/design.py`
    - Add `POST /api/v1/design/plugins/install` endpoint accepting `{ "tools": ["vina", "fpocket"] }`
    - Return installation status per tool: installed, already_available, or failed with error
    - Update existing `get_plugin_status` to use ToolInstaller.check_availability() for real binary detection
    - _Requirements: 6.5, 6.10, 10.3_

- [x] 7. Checkpoint — Verify tool installer and docking integration
  - Ensure ToolInstaller detects OS correctly, plugin status endpoint reports real binary presence, and docking input validation rejects incomplete requests. Ask the user if questions arise.

- [x] 8. NLP Contradiction Detection Engine (Backend)
  - [x] 8.1 Create `apps/api/services/nlp_contradiction_engine.py` with NLPContradictionEngine class
    - Implement lazy model loading: PubMedBERT via `sentence-transformers`, BioNLI via `transformers` pipeline
    - Implement `compute_similarity(text_a, text_b)` returning cosine similarity float
    - Implement `classify_pair(premise, hypothesis)` returning NLIResult (label + confidence)
    - Implement `extract_context(text)` extracting study_type, model_organisms, cell_lines, methodologies
    - Implement `compute_confidence(nli_score, context_alignment, source_quality)` with weighted formula (0.5*NLI + 0.3*context + 0.2*source)
    - Implement graceful fallback: when models unavailable, use existing keyword heuristic from `contradiction_detector.py`
    - Set `_available` flag and report method used (nlp vs keyword_fallback)
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.7_

  - [x] 8.2 Add Pydantic data models for NLP results
    - Create `NLIResult`, `ExperimentalContext`, `ContradictionResult`, `EvidenceLandscape` models
    - Add temporal reasoning: compare publication dates, note evolving understanding vs genuine disagreement
    - Add contradiction type classification: directional, temporal, magnitude, causal
    - _Requirements: 7.2, 7.4, 7.5, 7.7_

  - [ ]* 8.3 Write property test for similarity computation bounds (Hypothesis)
    - **Property 7: Similarity Computation Produces Valid Cosine Scores**
    - For any two non-empty biomedical text strings, verify cosine similarity is in [-1.0, 1.0] and identical strings return > 0.99
    - **Validates: Requirements 7.1, 8.1**

  - [ ]* 8.4 Write property test for NLI classification labels (Hypothesis)
    - **Property 8: NLI Classification Returns Valid Labels**
    - For any pair of non-empty claim strings, verify label is one of {entailment, contradiction, neutral} and confidence is in [0.0, 1.0]
    - **Validates: Requirements 7.2**

  - [ ]* 8.5 Write property test for experimental context extraction (Hypothesis)
    - **Property 9: Experimental Context Extraction**
    - For any text containing known context markers, verify at least one matching field in ExperimentalContext
    - **Validates: Requirements 7.4**

  - [ ]* 8.6 Write property test for contradiction confidence score bounds (Hypothesis)
    - **Property 11: Contradiction Confidence Score Bounds**
    - For any detected contradiction, verify confidence is in [0.0, 1.0]
    - **Validates: Requirements 7.7**

  - [x] 8.7 Integrate NLP engine into existing `apps/api/services/contradiction_detector.py`
    - Replace `_keyword_heuristic` as primary method with NLP engine's `classify_pair`
    - Replace Jaccard similarity in `_find_similarity_clusters` with cosine similarity from NLP engine
    - Keep keyword heuristic as fallback when NLP models unavailable
    - Update `analyze_contradictions_and_similarities` to use NLP engine and report method used
    - _Requirements: 7.1, 7.2, 7.3_

- [x] 9. Similarity Analyzer (Backend)
  - [x] 9.1 Create `apps/api/services/similarity_analyzer.py` with SimilarityAnalyzer class
    - Implement `find_similarities(claims)` computing pairwise cosine similarity matrix
    - Implement `classify_relationship(sim_score, entities_a, entities_b)` returning shared_finding or complementary_evidence
    - Implement agglomerative clustering with configurable threshold (default 0.7)
    - Generate representative summary per cluster
    - Extract and compare entity mentions (genes, proteins, drugs, diseases, pathways) between similar claims
    - Implement `filter_results(results, entity_type, source_db)` for filtering by entity type or source
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [ ]* 9.2 Write property test for evidence clustering (Hypothesis)
    - **Property 10: Evidence Clustering Groups Similar Items**
    - For any set of evidence items where at least two have cosine similarity above threshold, verify they appear in the same cluster with non-empty representative summary
    - **Validates: Requirements 7.6, 8.4**

  - [ ]* 9.3 Write property test for similarity relationship classification (Hypothesis)
    - **Property 12: Similarity Relationship Classification**
    - For any claim pair above threshold, verify classification is exactly one of {shared_finding, complementary_evidence}
    - **Validates: Requirements 8.2**

  - [ ]* 9.4 Write property test for biomedical entity extraction (Hypothesis)
    - **Property 13: Biomedical Entity Extraction**
    - For any biomedical text, verify entity extraction returns entities with type from {gene, protein, drug, disease, pathway} and non-empty name
    - **Validates: Requirements 8.3**

  - [ ]* 9.5 Write property test for similarity filtering correctness (Hypothesis)
    - **Property 14: Similarity Filtering Correctness**
    - For any entity type or source database filter, verify all returned clusters contain only matching members
    - **Validates: Requirements 8.6**

  - [x] 9.6 Update `apps/web/src/pages/Contradictions.tsx` to display NLP-enhanced results
    - Show confidence scores on contradiction cards
    - Display method indicator (NLP vs keyword fallback)
    - Add separate Similarities tab with clusters ranked by confidence
    - Show shared entities and relationship type per cluster
    - Add entity type and source database filter controls
    - _Requirements: 7.7, 8.2, 8.5, 8.6_

- [x] 10. Checkpoint — Verify NLP contradiction and similarity engines
  - Ensure NLP engine initializes with graceful fallback, contradiction detection uses NLI classification, similarity analyzer clusters correctly, and frontend displays enhanced results. Ask the user if questions arise.

- [x] 11. Pathway Explorer v2 (Frontend)
  - [x] 11.1 Add pagination to PathwaysPage search results
    - Add `PaginationState` with page, pageSize (25), totalBySource
    - Render pagination controls (next, previous, page number) when a source returns > 25 results
    - Pass page/offset to `pathwaysSearchAPI` calls
    - _Requirements: 4.1_

  - [ ]* 11.2 Write property test for pagination controls (fast-check)
    - **Property 2: Pagination Controls Appear for Large Result Sets**
    - For any result set where a source returns > 25 results, verify pagination controls are rendered
    - **Validates: Requirements 4.1**

  - [x] 11.3 Implement side-by-side pathway comparison diff view
    - Compute `PathwayDiff`: sharedGenes, uniqueToA, uniqueToB, sharedInteractions
    - Display diff in the existing compare ViewMode with color-coded gene lists
    - Highlight shared genes in one color, unique genes in contrasting colors
    - _Requirements: 4.2_

  - [x] 11.4 Implement enrichment result persistence
    - Add `POST /api/v1/pathways/enrichment` backend endpoint to run and persist enrichment results
    - Add `GET /api/v1/pathways/enrichment/{id}` to retrieve persisted results
    - On frontend, store enrichment result ID and reload persisted results on page mount
    - _Requirements: 4.3_

  - [ ]* 11.5 Write property test for enrichment persistence round-trip (fast-check / integration)
    - **Property 3: Enrichment Persistence Round-Trip**
    - For any valid gene list, verify persisting and retrieving enrichment results produces equivalent data
    - **Validates: Requirements 4.3**

  - [x] 11.6 Add disease context annotations and export functionality
    - Display disease context (affected genes, therapeutic targets) as visual annotations on pathway diagram when available from cockpit handoff
    - Add export button with format selector: SVG, PNG, JSON
    - Wire export to `POST /api/v1/pathways/export` endpoint
    - _Requirements: 4.4, 4.5, 4.6_

- [x] 12. Backend Health Verification and Error Reporting
  - [x] 12.1 Enhance `/api/v1/health` endpoint in `apps/api/routers/health.py`
    - Add PostgreSQL connection check (lightweight query)
    - Add Redis ping check (reuse existing `_check_redis`)
    - Add Qdrant availability check (reuse existing `_check_qdrant`)
    - Add plugin status check (Vina, fpocket, RDKit) via ToolInstaller
    - Return structured response with per-service status, timestamp, and failed_services list
    - Log all health check results with timestamps for intermittent failure diagnosis
    - _Requirements: 10.1, 10.3, 10.6_

  - [x] 12.2 Implement structured error response pattern
    - Create `StructuredError` Pydantic model with error_code, message, suggested_remediation, service, retry_after_seconds
    - Add FastAPI exception handler that returns StructuredError for service unavailability errors
    - Ensure database connection failures return connection error with retry functionality
    - _Requirements: 10.4, 10.5_

  - [ ]* 12.3 Write property test for structured error response format (Hypothesis)
    - **Property 16: Structured Error Response Format**
    - For any API request failing due to service unavailability, verify response contains non-empty error_code, message, and suggested_remediation
    - **Validates: Requirements 10.4**

  - [x] 12.4 Add degraded status indicators to frontend pages
    - When a backend service is unavailable, show degraded status indicator on the relevant page instead of blank screen
    - Display plugin availability accurately in Design Studio using real binary detection from health endpoint
    - _Requirements: 10.2, 10.3_

- [x] 13. Checkpoint — Verify health checks and error reporting
  - Ensure health endpoint reports all subsystem statuses, structured errors are returned for unavailable services, and frontend shows degraded indicators. Ask the user if questions arise.

- [x] 14. Playwright Visual Regression Test Suite
  - [x] 14.1 Create Playwright visual test configuration and page definitions
    - Create `tests/visual/visual-regression.spec.ts` with 13 primary pages and 3 viewports (1440px, 768px, 320px)
    - Configure screenshot comparison with diff image output to test artifacts directory
    - Set test timeout to ensure full suite completes within 120 seconds
    - _Requirements: 9.1, 9.2, 9.6, 9.7_

  - [x] 14.2 Implement overflow and layout assertions in visual tests
    - For each page × viewport: assert no element has scrollWidth exceeding clientWidth by more than 1px
    - At mobile viewport (320px): verify no page-level horizontal scrollbar
    - At mobile viewport: verify hamburger menu is visible and LeftRail is collapsed
    - Verify all Card_Containers have text content within bounding box
    - _Requirements: 9.3, 9.4, 9.5_

- [x] 15. Final checkpoint — Ensure all tests pass
  - Run full Vitest suite, pytest suite, and Playwright visual tests. Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation at logical phase boundaries
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- The NLP engine (tasks 8-9) uses lazy model loading — models download on first use, not at startup
- The ToolInstaller (task 6) runs on startup but gracefully handles failures without blocking the API
- Frontend changes (tasks 1-2, 4, 11) use TailwindCSS 4 utilities and existing design tokens
- Backend changes (tasks 6, 8-9, 12) follow existing FastAPI patterns with Pydantic models

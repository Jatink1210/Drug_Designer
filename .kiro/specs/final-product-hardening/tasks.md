# Implementation Plan: Final Product Hardening

## Overview

This plan addresses 8 critical gaps preventing the Drug Designer platform from passing the §11 acceptance gates. Tasks are organized in 8 phases matching the requirements, with property-based tests and unit tests as sub-tasks close to their implementation targets. The frontend uses React 19 / TypeScript / Vite 8 / TailwindCSS 4; the backend uses FastAPI / Python.

## Tasks

- [x] 1. Cockpit Query Lifecycle Stabilization
  - [x] 1.1 Implement `cockpitReducer` state machine in `WorkspacePage.tsx`
    - Define `CockpitQueryState` interface and `CockpitAction` discriminated union type
    - Implement `cockpitReducer` function with `START_ANALYSIS`, `PROGRESS`, `COMPLETE`, `ERROR`, `TIMEOUT`, `RESET`, and `RESTORE` actions
    - Replace existing `useState` calls for query/result/progress with `useReducer(cockpitReducer, initialState)`
    - Key invariant: only the `RESET` action sets `result` to `null`; no other action clears it
    - _Requirements: 1.2, 1.3_

  - [ ]* 1.2 Write property test for result state stability (Property 1)
    - **Property 1: Result State Stability**
    - Generate random `CockpitQueryState` with non-null `result` and random non-RESET actions; assert `result` is never cleared
    - Use `fast-check` with Vitest, minimum 100 iterations
    - **Validates: Requirements 1.3**

  - [x] 1.3 Add backend run tracking to `routers/cockpit.py`
    - Create `cockpit_runs` table via Alembic migration with columns: `id`, `query`, `status`, `created_at`, `updated_at`, `result_summary`, `error_message`, `provenance`, `user_id`, `project_id`
    - Add index on `(user_id, created_at DESC)`
    - Implement run record creation (status `pending`) at the start of `POST /api/v1/cockpit/analyze`
    - Implement status transitions: `pending` → `running` → `success` | `error` | `timeout`
    - _Requirements: 1.1, 1.4_

  - [x] 1.4 Implement `GET /api/v1/cockpit/recent-runs` endpoint
    - Return all tracked runs for the current user/project, ordered by `created_at DESC`
    - Include pagination support (limit/offset)
    - Each run record includes: `run_id`, `query`, `status`, `created_at`, `updated_at`, `result_summary`, `error_message`, `provenance`
    - _Requirements: 1.4, 1.5_

  - [x] 1.5 Add WebSocket progress events and timeout handling in `WorkspacePage.tsx`
    - Emit `CockpitProgressEvent` at each analysis stage (classification, retrieval, enrichment, synthesis, scoring) with percentage and stage label
    - Display current stage label and percentage in the Cockpit progress indicator
    - Implement 120-second timeout: if no progress event received within 120s, dispatch `TIMEOUT` action showing warning with retry/cancel buttons
    - Wire `RESTORE` action to reload the most recent completed run when user returns to the Cockpit
    - _Requirements: 1.5, 1.6, 1.7_

  - [ ]* 1.6 Write unit tests for cockpit lifecycle
    - Test `cockpitReducer` transitions: START_ANALYSIS → PROGRESS → COMPLETE preserves result
    - Test timeout dispatch after 120s without progress
    - Test RESTORE action loads previous run
    - Test ERROR action preserves run_id for retry
    - _Requirements: 1.1, 1.2, 1.3, 1.6, 1.7_

- [x] 2. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Inline Slash Command Parser
  - [x] 3.1 Implement `parseInlineSlashCommand()` in `canonicalProduct.ts`
    - Add `InlineSlashParseResult` interface with fields: `command`, `argument`, `additionalInstructions`, `pendingCommands`, `originalQuery`, `normalizedQuery`
    - Implement regex-based scanner using `(?:^|\s)(\/[a-z]+)(?:\s|$)` to find all `/command` tokens at any position
    - For each match, check against `SLASH_COMMANDS` for validity
    - First valid match → primary `command`; subsequent valid matches → `pendingCommands` array preserving order
    - Text before first command + text after argument → `additionalInstructions`
    - If no valid command found → return `{ command: null, argument: normalizedQuery, ... }`
    - Preserve existing `parseSlashCommand()` for backward compatibility; have it delegate to the new function
    - _Requirements: 2.1, 2.3, 2.5, 2.6_

  - [ ]* 3.2 Write property test for inline slash command extraction (Property 2)
    - **Property 2: Inline Slash Command Extraction**
    - Generate input strings with valid slash command tokens embedded at random positions (leading, middle, trailing)
    - Assert the parser extracts the correct `SlashCommandDefinition` and argument
    - Use `fast-check` with Vitest, minimum 100 iterations
    - **Validates: Requirements 2.1**

  - [ ]* 3.3 Write property test for no-command passthrough (Property 4)
    - **Property 4: No-Command Passthrough**
    - Generate input strings guaranteed to NOT contain any `SLASH_COMMANDS` token
    - Assert parser returns `command: null` and full normalized input as `argument`
    - Use `fast-check` with Vitest, minimum 100 iterations
    - **Validates: Requirements 2.3**

  - [ ]* 3.4 Write property test for multi-command parsing (Property 5)
    - **Property 5: Multi-Command Parsing**
    - Generate input strings containing 2–4 valid slash command tokens at random positions
    - Assert first valid command is `command`, remaining are in `pendingCommands` in order of appearance
    - Use `fast-check` with Vitest, minimum 100 iterations
    - **Validates: Requirements 2.5**

  - [x] 3.5 Wire inline parser into Cockpit search flow in `WorkspacePage.tsx`
    - Replace the leading-slash-only check with `parseInlineSlashCommand()`
    - When `command` is non-null, build `SharedHandoffPayload` with `targetRoute`, `query`, `additionalInstructions`, and `pendingCommands`
    - Navigate to the target page with the handoff payload
    - When `command` is null, treat input as general evidence query (existing behavior)
    - _Requirements: 2.2, 2.3_

  - [ ]* 3.6 Write property test for handoff payload construction (Property 3)
    - **Property 3: Handoff Payload Construction**
    - Generate valid `InlineSlashParseResult` objects with non-null commands
    - Assert constructed `SharedHandoffPayload` contains command's `route` as `targetRoute`, extracted `argument` as `query`, and surrounding text as `additionalInstructions`
    - Use `fast-check` with Vitest, minimum 100 iterations
    - **Validates: Requirements 2.2**

  - [x] 3.7 Implement autocomplete dropdown for inline `/` trigger
    - Modify the Cockpit search bar to detect `/` at any cursor position, not only at position 0
    - Display the command autocomplete dropdown filtered by characters following the `/`
    - _Requirements: 2.4_

  - [ ]* 3.8 Write unit tests for inline parser edge cases
    - Test all 13 acceptance gate query probes from §11.13 (example-based)
    - Test "Run /disease intelligence on this and then prioritize targets on the basis of MCC"
    - Test "display /Structure of this and highlight all the pLLDT regions"
    - Test leading-slash backward compatibility: `/structure BRCA1`
    - Test unrecognized `/token` is ignored (treated as literal text)
    - Test command without argument returns empty string argument
    - _Requirements: 2.1, 2.6_

- [x] 4. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Deprecated Route Cleanup
  - [x] 5.1 Add redirect rules for deprecated routes in `App.tsx`
    - Build `REDIRECT_ROUTES` array from `LEGACY_ROUTE_DECISIONS` entries with `action: "hide"` or `action: "merge"`
    - Add React Router `<Navigate>` elements for each deprecated path redirecting to `/workspace` (or specified `canonicalPath`)
    - Cover all deprecated paths: `/operations`, `/reports`, `/notes`, `/exports`, `/memory`, `/ppi`, `/interaction-maps`, `/gene-explorer`, and any others in `LEGACY_ROUTE_DECISIONS`
    - _Requirements: 3.3, 3.5_

  - [x] 5.2 Clean up LeftRail navigation in `LeftRail.tsx`
    - Ensure LeftRail renders exactly 13 items from `CANONICAL_MODULE_ROUTES` grouped into 4 sections: Discovery (Cockpit, Evidence Search, Entity Intelligence), Analysis (Knowledge Graph, Pathways, 3D Structure, Design Studio), Workflows (Clinical Design, SynthArena, Research Labs, Contradiction & Similarity, PICO Verification), System (Settings)
    - Remove any hardcoded entries for Operations, Reports, Notes, Export Center, PPI Network, Interactions, Gene/Protein Explorer, Runtime Center, Model Center, or Catalog
    - _Requirements: 3.1, 3.2_

  - [x] 5.3 Add toast notification on deprecated route redirect
    - When a redirect from a deprecated route occurs, display a toast: `"${label} has moved to ${canonicalLabel}"`
    - Toast should auto-dismiss after 5 seconds
    - _Requirements: 3.4_

  - [ ]* 5.4 Write property test for deprecated route redirect (Property 6)
    - **Property 6: Deprecated Route Redirect**
    - Iterate all `LEGACY_ROUTE_DECISIONS` entries with `action: "hide"`; assert each path maps to a redirect target of `/workspace` or the specified `canonicalPath`
    - Use `fast-check` with Vitest (or example-based iteration over the data-driven list)
    - **Validates: Requirements 3.3, 3.4**

  - [ ]* 5.5 Write unit tests for LeftRail navigation
    - Assert LeftRail renders exactly 13 navigation items
    - Assert no deprecated entries appear in the rendered DOM
    - Assert section groupings match the 4 canonical sections
    - _Requirements: 3.1, 3.2_

- [x] 6. FE↔BE Contract Normalization
  - [x] 6.1 Audit and normalize `lib/api.ts` endpoint wrappers
    - Organize API client into clearly labeled sections: cockpit, entity-intelligence, graph, pathways, structure, design, clinical, syntharena, labs, contradiction-similarity, pico, settings
    - Ensure exactly one exported function per canonical backend endpoint
    - Rename `/targets/prioritize` wrapper to use `/targets/rank`; mark old wrapper as `@deprecated` with forwarding
    - Add TypeScript interfaces for all request/response payloads matching `Response_Envelope` schema
    - Remove any duplicate functions calling the same route under different names
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.6_

  - [x] 6.2 Add backend route aliases for deprecated endpoints in FastAPI routers
    - Add thin redirect from `/targets/prioritize` to `/targets/rank` in the targets router
    - Ensure all deprecated route aliases return the same `Response_Envelope` as the canonical route
    - _Requirements: 4.5_

  - [ ]* 6.3 Write property test for API client endpoint uniqueness (Property 7)
    - **Property 7: API Client Endpoint Uniqueness**
    - Statically extract all endpoint paths from `api.ts`; assert `Set` size equals array length (no duplicates)
    - **Validates: Requirements 4.2**

  - [ ]* 6.4 Write unit tests for contract normalization
    - Test that all API wrapper functions set `Content-Type: application/json`
    - Test that deprecated wrappers forward to canonical functions
    - Test that response types match `Response_Envelope` schema
    - _Requirements: 4.3, 4.5_

- [x] 7. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Frontend Build Stability
  - [x] 8.1 Fix all TypeScript compilation errors in `apps/web/`
    - Run `tsc --noEmit` and fix all reported errors
    - Resolve missing module imports (`@/lib/canonicalProduct`, i18n packages, Tooltip component types)
    - Fix unused variable warnings treated as errors in strict mode
    - Ensure all import paths resolve correctly
    - _Requirements: 5.1, 5.2, 5.3_

  - [x] 8.2 Verify production build succeeds
    - Run `npm run build` in `apps/web/` and confirm exit code 0
    - Verify production bundle is produced in `dist/`
    - Confirm bundle size is under 15 MB (uncompressed)
    - _Requirements: 5.1, 5.4_

- [x] 9. Connector Health Observability
  - [x] 9.1 Implement comprehensive `GET /api/v1/cockpit/source-health` in `routers/health.py`
    - Query the connector registry for all registered connectors (not just those with recent activity)
    - For each connector, fetch Redis rolling stats from `BaseConnector`: `avg_response_ms`, `p95_response_ms`, `errors_1h`, `ratelimit_hits_1h`
    - Include `circuit_breaker_state` from `ConnectorCircuitBreaker` (closed/open/half_open)
    - Derive connector status: open circuit breaker → `"degraded"`, high errors → `"error"`, no stats → `"unknown"`, otherwise → `"healthy"`
    - Return `SourceHealthResponse` with per-connector entries and aggregated `HealthSummary`
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 9.2 Implement `GET /api/v1/catalog/stats` with real database counts
    - Query PostgreSQL, Qdrant, and Neo4j for actual record/collection counts
    - Return non-zero values for populated collections
    - _Requirements: 6.4_

  - [x] 9.3 Implement frontend health components
    - Create `HealthStrip.tsx` component for the Cockpit showing summary badge: "X/Y sources healthy" with color coding (green >80%, yellow 50-80%, red <50%)
    - Add Sources tab to `SettingsPage.tsx` with sortable table: Name, Status, Latency (p95 ms), Error Count (1h), Rate Limit Hits (1h), Last Checked
    - Add expandable row detail showing health history and circuit breaker state
    - Wire both components to `cockpitSourceHealthAPI` in `lib/api.ts`
    - _Requirements: 6.5, 6.6_

  - [ ]* 9.4 Write property test for health stats computation (Property 8)
    - **Property 8: Health Stats Computation**
    - Generate arrays of 1–200 positive floats as response time samples
    - Assert `avg_response_ms` equals arithmetic mean and `p95_response_ms` equals value at 95th percentile index of sorted list
    - Use `fast-check` with Vitest, minimum 100 iterations
    - **Validates: Requirements 6.2**

  - [ ]* 9.5 Write property test for circuit breaker status mapping (Property 9)
    - **Property 9: Circuit Breaker Status Mapping**
    - Generate all circuit breaker states × error count combinations
    - Assert: `"open"` → `"degraded"`, `"closed"` with errors below threshold → `"healthy"`, `"closed"` with errors above threshold → `"error"`
    - Use `fast-check` with Vitest, minimum 100 iterations
    - **Validates: Requirements 6.3**

  - [ ]* 9.6 Write property test for health badge color coding (Property 10)
    - **Property 10: Health Badge Color Coding**
    - Generate `HealthSummary` with random total/healthy/degraded/error counts
    - Assert: `healthy/total > 0.8` → `"green"`, `0.5 ≤ healthy/total ≤ 0.8` → `"yellow"`, `healthy/total < 0.5` → `"red"`
    - Use `fast-check` with Vitest, minimum 100 iterations
    - **Validates: Requirements 6.6**

  - [ ]* 9.7 Write unit tests for connector health
    - Test source-health endpoint returns all registered connectors including those with no activity
    - Test catalog/stats returns non-zero counts for populated collections
    - Test health strip renders correct badge color for various summary ratios
    - _Requirements: 6.1, 6.4, 6.6_

- [x] 10. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Settings Platform Depth
  - [x] 11.1 Implement settings tab structure in `SettingsPage.tsx`
    - Add tab navigation for at least 8 sections: General, Sources, Runtime, Models, Security, Storage, Accessibility, Diagnostics
    - Each tab fetches live data from its corresponding backend endpoint on mount
    - _Requirements: 8.1_

  - [x] 11.2 Implement Sources tab with connector management
    - Display every registered connector with health status, enable/disable toggle, and API key input field (masked)
    - Wire to `GET /api/v1/cockpit/source-health` for health data and `POST /api/v1/settings` for toggle/key updates
    - _Requirements: 8.2_

  - [x] 11.3 Implement Runtime and Models tabs
    - Runtime tab: display current mode (hosted/local/auto), active inference engine, selected model, GPU availability from `GET /api/v1/runtime/status`
    - Models tab: display installed models with version, size, status from `GET /api/v1/models`; add install/remove actions from model catalog
    - _Requirements: 8.3, 8.6_

  - [x] 11.4 Implement Diagnostics tab with live backend metrics
    - Display real-time connection status for PostgreSQL, Redis, Qdrant, and Neo4j with response time metrics from `GET /api/v1/runtime/diagnostics`
    - Show cache hit rates and queue depths
    - All values fetched from live endpoints — no hardcoded or placeholder values
    - _Requirements: 8.4, 8.7_

  - [x] 11.5 Implement settings save with toast feedback
    - Wire `POST /api/v1/settings` for partial updates with field-level validation
    - Display toast notification confirming save within 500ms of successful response
    - Handle validation errors (422) with field-level error display
    - _Requirements: 8.5_

  - [ ]* 11.6 Write unit tests for Settings page
    - Test that at least 8 distinct tabs render
    - Test Sources tab displays connector list with health indicators
    - Test Runtime tab displays live runtime status
    - Test Diagnostics tab displays non-placeholder values
    - Test save action triggers toast notification
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [x] 12. Acceptance Gate Verification Suite
  - [x] 12.1 Create Playwright E2E test project for acceptance gates
    - Configure `acceptance-gates` project in Playwright config
    - Create test file structure with one test case per gate (13 total)
    - Configure screenshot capture on failure
    - Configure summary report output with gate name, status, and execution time
    - Target: all 13 tests complete within 10 minutes against live backend
    - _Requirements: 7.1, 7.5, 7.6, 7.7_

  - [x] 12.2 Implement Gate 1 test: Cockpit general query + slash command routing
    - Submit "Aspirin" as a general query; verify result dashboard with summary, entity tables, and provenance within 60 seconds
    - Submit `/structure BRCA1` and verify routing to 3D Structure page
    - _Requirements: 7.2_

  - [x] 12.3 Implement Gate 9 test: Removed tabs absent from navigation
    - Verify Operations, Reports, Notes, PPI, Interactions, and Gene/Protein are absent from LeftRail DOM
    - Verify exactly 13 navigation items present
    - _Requirements: 7.3_

  - [x] 12.4 Implement Gate 13 test: Exact prompt-style query probes
    - Submit each of the 7 exact query probes from §11.13: Aspirin, BRCA1, Loperamide, `/structure BRCA1`, `/disease breast cancer`, inline slash commands
    - Verify each produces a meaningful result or correct routing
    - _Requirements: 7.4_

  - [x] 12.5 Implement remaining gate tests (Gates 2–8, 10–12)
    - Gate 2: Entity Intelligence replaces fragmented flows
    - Gate 3: KG and pathway surfaces connected with provenance
    - Gate 4: Structure and Design support handoff and real tool execution
    - Gate 5: Clinical page reflects 10-step workflow
    - Gate 6: SynthArena create → compare → debate → export
    - Gate 7: Research labs launch real jobs and display results
    - Gate 8: Contradiction & Similarity and PICO accept fresh input
    - Gate 10: Settings exposes runtime/model/connector/privacy control
    - Gate 11: FE↔BE contract map is normalized
    - Gate 12: Visual QA, API QA, and E2E scenarios pass without fake-success
    - _Requirements: 7.1_

  - [x] 12.6 Create pytest integration test suite for backend acceptance gates
    - Test `POST /api/v1/cockpit/analyze` creates run record and returns full result
    - Test `GET /api/v1/cockpit/recent-runs` returns runs ordered by creation time
    - Test `GET /api/v1/cockpit/source-health` returns all registered connectors
    - Test `GET /api/v1/catalog/stats` returns non-zero counts
    - Test `GET /api/v1/settings` returns full settings tree
    - Test `GET /api/v1/runtime/status` returns accurate runtime state
    - Test deprecated route aliases forward correctly
    - _Requirements: 7.1_

- [x] 13. Final Checkpoint — Ensure all tests pass
  - Run `npm run build` in `apps/web/` and confirm exit code 0
  - Run `tsc --noEmit` and confirm zero errors
  - Run Vitest unit and property test suites
  - Run pytest integration tests
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation after each major phase
- Property tests validate universal correctness properties from the design document (Properties 1–10)
- Unit tests validate specific examples, edge cases, and error conditions
- The Playwright acceptance gate suite (task 12) serves as the final ship-readiness verification

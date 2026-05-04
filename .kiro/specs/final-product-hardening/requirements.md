# Requirements Document — Final Product Hardening

## Introduction

Three prior specs have brought the Drug Designer platform from a 30-40% functional scaffold to a substantially wired product:

1. **drug-designer-product-alignment** — Initial wiring of all 14 subsystems (45 tasks, all complete)
2. **platform-polish-and-improvements** — UI polish, AutoDock Vina auto-install, NLP contradiction engine, responsive layout (15 tasks, all complete)
3. **drug-designer-codebase-alignment** — NLP integration, research labs computation, KG enhancement, entity detail pages, pathway interactivity, structure viewer, clinical workflow, debate engine, dossier generation, WebSocket progress, integration testing, provenance compliance (20 tasks, all complete)

After verifying the codebase against the master requirements document (`requirements_1.md`), 8 critical gaps remain that prevent the platform from passing the §11 acceptance gates. This spec addresses each gap with precise, testable requirements to bring the platform to a ship-ready state.

The tech stack is React 19 / TypeScript / Vite 8 / TailwindCSS 4 (frontend), FastAPI / Python (backend), PostgreSQL + Qdrant + Redis + Neo4j (data layer).

## Glossary

- **Cockpit**: The main search hub page (`WorkspacePage.tsx`) acting as the agentic extension of every page, supporting general queries and slash commands
- **Query_Lifecycle**: The full cycle from user input through backend analysis to persistent result display in the Cockpit UI, including run tracking, progress display, and result rendering
- **Run_Tracker**: The system that persists cockpit analysis runs (via `cockpitRecentRunsAPI`) so they survive page reloads and appear in recent-runs lists
- **Inline_Slash_Command**: A slash command embedded within natural language (e.g., "Run /disease intelligence on this") as opposed to a leading slash command (e.g., "/disease breast cancer")
- **Slash_Command_Parser**: The `parseSlashCommand()` function in `canonicalProduct.ts` that extracts command and argument from user input
- **LeftRail**: The `LeftRail.tsx` sidebar navigation component driven by `CANONICAL_MODULE_ROUTES`
- **Deprecated_Route**: A route marked with `action: "hide"` in `LEGACY_ROUTE_DECISIONS` that must not appear in primary navigation and must redirect to the Cockpit
- **API_Client**: The centralized `apps/web/src/lib/api.ts` module containing all frontend-to-backend HTTP calls
- **Canonical_Route**: The backend route name that matches the product specification (e.g., `/targets/rank` not `/targets/prioritize`)
- **Connector_Health**: The per-connector status reported via `/api/v1/cockpit/source-health` and `/api/v1/sources/health`, enriched with Redis rolling stats from `BaseConnector`
- **Circuit_Breaker**: The `ConnectorCircuitBreaker` in `core/circuit_breaker.py` that tracks connector failures and skips degraded sources
- **Response_Envelope**: The universal API wrapper with status, data, provenance, and timing fields
- **Acceptance_Gate**: One of the 13 specific verification criteria from `requirements_1.md` §11 that must pass for the product to be considered ready
- **Build_Pipeline**: The `npm run build` command in `apps/web/` that must produce zero TypeScript compilation errors
- **Settings_Engine**: The combined frontend `SettingsPage.tsx` and backend `/api/v1/settings` system for platform configuration

## Requirements

### Requirement 1: Cockpit Query Lifecycle Stabilization

**User Story:** As a researcher, I want cockpit queries to reliably display results after analysis completes and persist those results across page interactions, so that long-running evidence queries produce a stable, visible result dashboard instead of silently resetting.

**Frontend Expected Outcome:**
- After submitting a general query (e.g., "Aspirin"), the Cockpit displays staged progress text with real ETA based on backend progress events
- When the backend returns a completed analysis payload, the Cockpit renders the full AnalysisReport (summary, stats, entity tables, KG, pathways) and does not reset to the default search shell
- The completed run appears in the recent-runs sidebar/section with run_id, query text, timestamp, and status
- If the user navigates away and returns, the most recent completed run is restorable from the recent-runs list
- If the analysis exceeds 120 seconds without a progress event, the UI displays a timeout warning with a "Retry" button instead of silently resetting

**Backend Expected Outcome:**
- `POST /api/v1/cockpit/analyze` creates a tracked run record in the database before starting analysis
- The run record is updated with status transitions: `pending` → `running` → `success` | `error` | `timeout`
- `GET /api/v1/cockpit/recent-runs` returns all tracked runs for the current user/project, ordered by creation time descending
- WebSocket progress events are emitted at each analysis stage (classification, retrieval, synthesis) with percentage and stage label
- If analysis fails or times out, the run record is updated with error details and the error is surfaced to the frontend

**Data Included:**
- Run record: `run_id`, `query`, `status`, `created_at`, `updated_at`, `result_summary`, `error_message`, `provenance`
- Progress event: `run_id`, `stage`, `percentage`, `message`, `timestamp`
- Recent-runs response: array of run records with pagination support

#### Acceptance Criteria

1. WHEN a researcher submits a general query in the Cockpit, THE Query_Lifecycle SHALL create a tracked run record in the database with status "pending" before initiating analysis
2. WHEN the backend analysis completes successfully, THE Cockpit SHALL render the full AnalysisReport and update the run record status to "success"
3. WHEN the backend analysis completes, THE Cockpit SHALL NOT reset to the default search shell; the result dashboard SHALL remain visible until the user explicitly starts a new search
4. WHEN a cockpit analysis run completes, THE Run_Tracker SHALL persist the run so it appears in `GET /api/v1/cockpit/recent-runs` within 2 seconds of completion
5. WHEN a researcher navigates away from the Cockpit and returns, THE Cockpit SHALL offer to restore the most recent completed run from the recent-runs list
6. IF a cockpit analysis exceeds 120 seconds without a progress event, THEN THE Cockpit SHALL display a timeout warning with retry and cancel options instead of silently resetting
7. WHEN the backend emits WebSocket progress events during analysis, THE Cockpit SHALL display the current stage label and percentage in the progress indicator

### Requirement 2: Prompt-Style Inline Slash Command Parsing

**User Story:** As a researcher, I want to use slash commands embedded in natural language (e.g., "Run /disease intelligence on this and then prioritize targets on the basis of MCC"), so that I can issue complex multi-step instructions without being limited to leading-slash syntax.

**Frontend Expected Outcome:**
- The Cockpit search bar accepts both leading-slash commands (`/structure BRCA1`) and inline slash commands (`Run /disease intelligence on this`)
- When an inline slash command is detected, the Cockpit extracts the command, builds a Handoff_Payload with the surrounding natural language as context, and routes to the target page
- If multiple inline slash commands are detected, the Cockpit executes them sequentially (first command routes immediately; subsequent commands are queued as pending actions on the target page)
- The command autocomplete dropdown appears when the user types `/` at any position in the input, not only at the start
- If no valid slash command is detected in the input, the query is treated as a general evidence query (current behavior preserved)

**Backend Expected Outcome:**
- No backend changes required for parsing; the Slash_Command_Parser in `canonicalProduct.ts` handles extraction
- If the inline command includes additional context (e.g., "prioritize targets on the basis of MCC"), that context is included in the Handoff_Payload as `additionalInstructions`

**Data Included:**
- Parsed inline command: `{ command: SlashCommandDefinition, argument: string, additionalInstructions: string, originalQuery: string }`
- Handoff_Payload extension: `additionalInstructions` field carrying the natural language context surrounding the slash command

#### Acceptance Criteria

1. WHEN a researcher enters text containing an inline slash command (e.g., "Run /disease intelligence on BRCA1"), THE Slash_Command_Parser SHALL extract the command `/disease` and argument `BRCA1` regardless of the command's position in the input
2. WHEN an inline slash command is detected, THE Cockpit SHALL build a Handoff_Payload with the extracted command, argument, and surrounding natural language as `additionalInstructions`, then navigate to the target page
3. WHEN the input contains no recognized slash command, THE Cockpit SHALL treat the entire input as a general evidence query
4. WHEN the user types `/` at any position in the search bar, THE Cockpit SHALL display the command autocomplete dropdown filtered by the characters following the `/`
5. WHEN multiple inline slash commands appear in a single input, THE Cockpit SHALL execute the first command immediately and include subsequent commands in the Handoff_Payload as `pendingCommands`
6. THE Slash_Command_Parser SHALL correctly parse all 13 acceptance gate query probes from requirements_1.md §11.13, including "Run /disease intelligence on this and then prioritize targets on the basis of MCC" and "display /Structure of this and highlight all the pLLDT regions"

### Requirement 3: Deprecated Route Cleanup from Primary Navigation

**User Story:** As a platform user, I want the navigation to contain only the 13 canonical pages, so that I am not confused by deprecated or redundant routes.

**Frontend Expected Outcome:**
- The LeftRail navigation displays exactly 13 items grouped into 4 sections: Discovery (Cockpit, Evidence Search, Entity Intelligence), Analysis (Knowledge Graph, Pathways, 3D Structure, Design Studio), Workflows (Clinical Design, SynthArena, Research Labs, Contradiction & Similarity, PICO Verification), System (Settings)
- No LeftRail entry exists for Operations, Reports & Export, Notes, standalone PPI Network, standalone Interactions, standalone Gene/Protein, Runtime Center, Model Center, or Catalog
- Navigating directly to a deprecated URL (e.g., `/operations`, `/reports`, `/notes`, `/exports`, `/memory`, `/ppi`, `/interaction-maps`, `/gene-explorer`) redirects to the Cockpit (`/workspace`) with a brief toast notification explaining the redirect

**Backend Expected Outcome:**
- Backend routes for deprecated pages remain functional for internal/contextual use but are not exposed in any navigation or discovery endpoint
- `GET /api/v1/cockpit/nav-counts` returns counts only for canonical modules

#### Acceptance Criteria

1. THE LeftRail SHALL display exactly 13 navigation items matching the `CANONICAL_MODULE_ROUTES` definition: Cockpit, Evidence Search, Entity Intelligence, Knowledge Graph, Pathways, 3D Structure, Design Studio, Clinical Design, SynthArena, Research Labs, Contradiction & Similarity, PICO Verification, Settings
2. THE LeftRail SHALL NOT display entries for Operations, Reports, Notes, Export Center, PPI Network, Interactions, Gene/Protein Explorer, Runtime Center, Model Center, or Catalog
3. WHEN a user navigates directly to a deprecated route URL, THE application SHALL redirect to `/workspace` within 300ms
4. WHEN a redirect from a deprecated route occurs, THE application SHALL display a toast notification stating which page was removed and where the user was redirected
5. THE React Router configuration SHALL define redirect rules for all paths listed in `LEGACY_ROUTE_DECISIONS` with `action: "hide"` or `action: "merge"`

### Requirement 4: Frontend-Backend Contract Normalization

**User Story:** As a developer, I want all frontend API calls to use canonical backend route names consistently, so that there is no contract drift between what the frontend requests and what the backend serves.

**Frontend Expected Outcome:**
- The API_Client (`lib/api.ts`) uses a single, canonical endpoint name for each operation
- No duplicate or conflicting endpoint wrappers exist for the same backend functionality
- All API calls include proper TypeScript types for request and response payloads
- The API_Client is organized by module family (cockpit, entity-intelligence, graph, pathways, structure, design, clinical, syntharena, labs, contradiction, pico, settings) with clear section headers

**Backend Expected Outcome:**
- All backend routers use the canonical route names from the product specification
- Deprecated route aliases (e.g., `/targets/prioritize` alongside `/targets/rank`) are preserved as thin redirects to canonical routes for backward compatibility
- Every canonical route returns a Response_Envelope with consistent field naming

**Data Included:**
- Contract map: module → frontend function → backend endpoint → response type
- Drift audit: list of mismatched route names with resolution (rename, alias, or deprecate)

#### Acceptance Criteria

1. THE API_Client SHALL use `/targets/rank` as the canonical endpoint for target ranking; the legacy `/targets/prioritize` wrapper SHALL be marked deprecated with a redirect to the canonical endpoint
2. THE API_Client SHALL have exactly one wrapper function per canonical backend endpoint, with no duplicate functions calling the same route under different names
3. WHEN the API_Client calls any endpoint, THE request SHALL include `Content-Type: application/json` and the response SHALL be typed with a TypeScript interface matching the Response_Envelope schema
4. THE API_Client SHALL be organized into clearly labeled sections matching the canonical module families: cockpit, entity-intelligence, graph, pathways, structure, design, clinical, syntharena, labs, contradiction-similarity, pico, settings
5. WHEN a deprecated backend route alias receives a request, THE backend SHALL forward the request to the canonical route and return the same Response_Envelope
6. THE API_Client SHALL NOT contain any endpoint wrappers that reference routes not defined in the backend router registry

### Requirement 5: Frontend Build Stability

**User Story:** As a developer, I want `npm run build` to complete with zero TypeScript compilation errors, so that the frontend is in a deployable state.

**Frontend Expected Outcome:**
- `npm run build` in `apps/web/` exits with code 0 and produces a valid production bundle in `dist/`
- Zero TypeScript errors reported by `tsc --noEmit`
- All import paths resolve correctly (no missing modules)
- No unused variable warnings that are treated as errors in strict mode

**Backend Expected Outcome:**
- Not applicable (frontend-only requirement)

**Data Included:**
- Build output: bundle size, chunk count, build time
- Error inventory: list of current TypeScript errors with file, line, and error code

#### Acceptance Criteria

1. WHEN `npm run build` is executed in `apps/web/`, THE Build_Pipeline SHALL exit with code 0 and produce a valid production bundle
2. WHEN `tsc --noEmit` is executed in `apps/web/`, THE TypeScript compiler SHALL report zero errors
3. THE Build_Pipeline SHALL resolve all import paths without "module not found" errors, including `@/lib/canonicalProduct`, i18n packages, and Tooltip component types
4. THE Build_Pipeline SHALL produce a production bundle smaller than 15 MB (uncompressed) to ensure reasonable load times
5. IF a new TypeScript error is introduced by any change in this spec, THEN THE Build_Pipeline SHALL catch the error before the change is considered complete

### Requirement 6: Connector Health Observability

**User Story:** As a platform operator, I want the connector health endpoint to report accurate, real-time status for all registered connectors, so that I can diagnose which data sources are operational and which are degraded.

**Frontend Expected Outcome:**
- The Settings → Sources tab displays a table of all registered connectors with columns: Name, Status (healthy/degraded/error/unknown), Latency (p95 ms), Error Count (1h), Rate Limit Hits (1h), Last Checked
- The Cockpit health strip shows a summary badge: "X/Y sources healthy" with color coding (green if >80% healthy, yellow if 50-80%, red if <50%)
- Clicking a connector row in Settings expands to show detailed health history and circuit breaker state

**Backend Expected Outcome:**
- `GET /api/v1/cockpit/source-health` returns health data for all connectors registered in the connector registry, not just those with recent activity
- Each connector entry includes: `name`, `status` (healthy/degraded/error/unknown), `avg_response_ms`, `p95_response_ms`, `errors_1h`, `ratelimit_hits_1h`, `last_checked`, `circuit_breaker_state` (closed/open/half-open)
- `GET /api/v1/catalog/stats` returns accurate collection counts from PostgreSQL, Qdrant, and Neo4j
- The health check probes each connector with a lightweight test query (e.g., HEAD request or minimal search) on a configurable interval (default 5 minutes)

**Data Included:**
```json
{
  "sources": [
    {
      "name": "UniProt",
      "status": "healthy",
      "avg_response_ms": 245,
      "p95_response_ms": 890,
      "errors_1h": 0,
      "ratelimit_hits_1h": 0,
      "last_checked": "2026-05-01T12:00:00Z",
      "circuit_breaker_state": "closed"
    }
  ],
  "summary": {
    "total": 13,
    "healthy": 11,
    "degraded": 1,
    "error": 1,
    "unknown": 0
  }
}
```

#### Acceptance Criteria

1. WHEN `GET /api/v1/cockpit/source-health` is called, THE system SHALL return health data for every connector registered in the connector registry, including connectors with no recent activity (status "unknown")
2. WHEN a connector has Redis rolling stats from BaseConnector, THE source-health response SHALL include `avg_response_ms`, `p95_response_ms`, `errors_1h`, and `ratelimit_hits_1h` computed from those stats
3. WHEN a connector's Circuit_Breaker is in "open" state, THE source-health response SHALL report that connector's status as "degraded" with `circuit_breaker_state: "open"`
4. WHEN `GET /api/v1/catalog/stats` is called, THE system SHALL query PostgreSQL, Qdrant, and Neo4j for actual record counts and return non-zero values for populated collections
5. THE Settings Sources tab SHALL display all registered connectors with their health status, latency metrics, and error counts in a sortable table
6. THE Cockpit health strip SHALL display a summary badge showing the ratio of healthy sources to total registered sources

### Requirement 7: Acceptance Gate Verification Suite

**User Story:** As a product owner, I want an automated verification suite that tests all 13 acceptance gates from requirements_1.md §11, so that I can confirm the platform meets every ship-readiness criterion.

**Frontend Expected Outcome:**
- An end-to-end test suite (Playwright) that exercises each acceptance gate as a distinct test case
- Test results are reported with pass/fail per gate, with screenshots on failure
- The test suite can be run via a single command: `npx playwright test --project=acceptance-gates`

**Backend Expected Outcome:**
- A backend integration test suite (pytest) that verifies API contracts for each acceptance gate
- Each test sends real queries and validates response structure, status codes, and data completeness
- Tests run against a live backend instance with real connectors (not mocked)

**Data Included:**
- 13 acceptance gate test cases mapped to requirements_1.md §11:
  1. Cockpit general query + slash command routing
  2. Entity Intelligence replaces fragmented flows
  3. KG and pathway surfaces are connected and provenance-clickable
  4. Structure and Design support direct handoff and real tool execution
  5. Clinical page reflects 10-step workflow with real stage artifacts
  6. SynthArena supports create → compare → debate → export
  7. Research labs launch real jobs and display real results
  8. Contradiction & Similarity and PICO both accept fresh input
  9. Removed tabs are gone from primary UX
  10. Settings exposes runtime/model/connector/privacy control
  11. FE↔BE contract map is normalized
  12. Visual QA, API QA, and end-to-end scenarios pass without fake-success
  13. Exact prompt-style query probes pass (Aspirin, BRCA1, Loperamide, /structure BRCA1, /disease breast cancer, inline slash commands)

#### Acceptance Criteria

1. THE Acceptance Gate verification suite SHALL include a distinct test case for each of the 13 gates defined in requirements_1.md §11
2. WHEN Gate 1 is tested, THE suite SHALL submit "Aspirin" as a general query and verify the Cockpit returns a result dashboard with summary, entity tables, and provenance within 60 seconds
3. WHEN Gate 9 is tested, THE suite SHALL verify that Operations, Reports, Notes, PPI, Interactions, and Gene/Protein are absent from the LeftRail navigation DOM
4. WHEN Gate 13 is tested, THE suite SHALL submit each of the 7 exact query probes from §11.13 and verify each produces a meaningful result or correct routing
5. WHEN any acceptance gate test fails, THE suite SHALL capture a screenshot, the full API response, and a descriptive failure message
6. THE Acceptance Gate verification suite SHALL complete all 13 gate tests within 10 minutes when run against a live backend instance
7. WHEN all 13 acceptance gate tests pass, THE suite SHALL produce a summary report with gate name, status, and execution time for each gate

### Requirement 8: Settings Platform Depth Verification

**User Story:** As a platform administrator, I want the Settings page to provide comprehensive control over runtime mode, model selection, connector toggles, API key management, privacy/data retention, cache tuning, and diagnostics, so that I can fully configure the platform from a single surface.

**Frontend Expected Outcome:**
- The Settings page has tabs/sections for: General, Sources, Runtime, Models, Security, Storage, Notifications, Export, Accessibility, Diagnostics
- Sources tab: table of all connectors with enable/disable toggles, API key input fields (masked), health status indicators
- Runtime tab: mode selector (hosted/local/auto), active engine display, GPU status, model download controls
- Models tab: installed model list with version, size, status; model catalog with install/remove actions
- Security tab: authentication settings, RBAC role display, session configuration, API key vault
- Diagnostics tab: PostgreSQL/Redis/Qdrant/Neo4j connection status, response time metrics, cache hit rates, queue depths
- Privacy tab: data retention policy controls, export/delete user data, anonymization settings
- Each settings change provides immediate visual feedback via toast notification

**Backend Expected Outcome:**
- `GET /api/v1/settings` returns the full settings tree with all sections populated
- `POST /api/v1/settings` accepts partial updates and validates each field
- `GET /api/v1/runtime/status` returns accurate runtime state (active_mode, active_engine, selected_model, gpu_status)
- `GET /api/v1/runtime/diagnostics` returns database connection status, cache metrics, and queue health
- `GET /api/v1/models` returns installed models and catalog with accurate availability status

#### Acceptance Criteria

1. THE Settings page SHALL display at least 8 distinct configuration sections: General, Sources, Runtime, Models, Security, Storage, Accessibility, Diagnostics
2. WHEN the Sources section is opened, THE Settings_Engine SHALL display every registered connector with its current health status, an enable/disable toggle, and an API key input field
3. WHEN the Runtime section is opened, THE Settings_Engine SHALL display the current runtime mode, active inference engine, selected model, and GPU availability as reported by `GET /api/v1/runtime/status`
4. WHEN the Diagnostics section is opened, THE Settings_Engine SHALL display real-time connection status for PostgreSQL, Redis, Qdrant, and Neo4j with response time metrics
5. WHEN a settings change is saved, THE Settings_Engine SHALL display a toast notification confirming the save within 500ms
6. WHEN the Models section is opened, THE Settings_Engine SHALL display installed models with version and status, matching the data from `GET /api/v1/models`
7. THE Settings page SHALL NOT display hardcoded or placeholder values for any diagnostic metric; all values SHALL be fetched from live backend endpoints

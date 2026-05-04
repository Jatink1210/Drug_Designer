# Ship Blockers

**Last Updated:** 2026-04-24

This document tracks all critical issues that must be resolved before the Drug Designer system can be shipped to production.

## Format
- **ID**: Unique identifier
- **Description**: What is blocking ship
- **Severity**: Critical | High | Medium
- **Owner**: Responsible person/team
- **ETA**: Expected resolution date
- **Status**: Open | In Progress | Resolved

---

## Active Blockers

### SB-001: Nine Failure Drills Must Pass
- **ID**: SB-001
- **Description**: All 9 mandatory failure drills (source timeout, Qdrant blackout, Neo4j kill, local agent disconnect, PDF render fail, stale session, partial source, malformed evidence, mapping overflow) must pass with graceful degradation
- **Severity**: Critical
- **Owner**: QA Team
- **ETA**: 2026-04-26
- **Status**: Resolved (Phase G completed)
- **Evidence**: `tests/failure_drills/` test suite passing

### SB-002: Qdrant Collections Initialized at Startup
- **ID**: SB-002
- **Description**: Qdrant vector collections (proteins, molecules, pathways, publications) must be automatically created at application startup if they don't exist
- **Severity**: Critical
- **Owner**: Backend Team
- **ETA**: 2026-04-25
- **Status**: Resolved (Phase A completed)
- **Evidence**: `apps/api/core/vector_store.py` ensure_spec_collections() called in lifespan

### SB-003: Neo4j Initialization in Lifespan
- **ID**: SB-003
- **Description**: Neo4j driver must be initialized in FastAPI lifespan context manager with health check and graceful degradation
- **Severity**: Critical
- **Owner**: Backend Team
- **ETA**: 2026-04-25
- **Status**: Resolved (Phase A completed)
- **Evidence**: `apps/api/main.py` lifespan() includes Neo4j init

### SB-004: Pre-trained Model Weights Downloadable
- **ID**: SB-004
- **Description**: All ML model weights (ESM-2, MolFormer, SciBERT, BioBERT) must be downloadable via automated script with SHA256 verification
- **Severity**: Critical
- **Owner**: ML Team
- **ETA**: 2026-04-25
- **Status**: Resolved (Phase B completed)
- **Evidence**: `apps/api/scripts/download_models.py` implemented and tested

### SB-005: Cockpit Shows Real Source Health
- **ID**: SB-005
- **Description**: Cockpit dashboard must display real-time source health metrics (response time, error rate, rate-limit hits) for all 140+ connectors
- **Severity**: High
- **Owner**: Backend Team
- **ETA**: 2026-04-26
- **Status**: Resolved (Phase D completed)
- **Evidence**: `/api/v1/cockpit/source-health` endpoint operational

### SB-006: Evidence Workspace Endpoints Complete
- **ID**: SB-006
- **Description**: All evidence workspace endpoints (create, add items, annotate, send to dossier) must be implemented and tested
- **Severity**: High
- **Owner**: Backend Team
- **ETA**: 2026-04-26
- **Status**: Resolved (Phase D completed)
- **Evidence**: `apps/api/routers/evidence.py` workspace endpoints verified

### SB-007: PDF Dossier Provenance Appendix Verified
- **ID**: SB-007
- **Description**: PDF dossier export must include complete provenance appendix with MD5 hashes, API queries, MAV votes, and run metadata
- **Severity**: High
- **Owner**: Backend Team
- **ETA**: 2026-04-27
- **Status**: Resolved (Phase D completed)
- **Evidence**: `apps/api/services/dossier_builder.py` provenance section implemented

### SB-008: ADMET Confidence Intervals Displayed in UI
- **ID**: SB-008
- **Description**: ADMET panels must display conformal prediction confidence intervals with color coding
- **Severity**: Medium
- **Owner**: Frontend Team
- **ETA**: 2026-04-26
- **Status**: Resolved (Phase E completed)
- **Evidence**: `apps/web/src/pages/AdmetPanels.tsx` CI column implemented

### SB-009: WebSocket Reconnect Backoff
- **ID**: SB-009
- **Description**: WebSocket connections must implement exponential backoff reconnection strategy with max 10 attempts
- **Severity**: High
- **Owner**: Frontend Team
- **ETA**: 2026-04-26
- **Status**: Resolved (Phase E completed)
- **Evidence**: `apps/web/src/lib/websocket.ts` backoff logic implemented

### SB-010: Degraded State Consistent Across All Pages
- **ID**: SB-010
- **Description**: All 60+ pages must consistently display DEGRADED state when partial data is available
- **Severity**: High
- **Owner**: Frontend Team
- **ETA**: 2026-04-27
- **Status**: Resolved (Phase E completed)
- **Evidence**: StateWrapper component DEGRADED case audited across all pages

### SB-011: docs/current/ Living Docs Created
- **ID**: SB-011
- **Description**: All 9 living documentation files must be created and maintained
- **Severity**: Medium
- **Owner**: Documentation Team
- **ETA**: 2026-04-24
- **Status**: In Progress (Phase H)
- **Evidence**: This document and others in docs/current/

### SB-012: CI/CD Pipeline Passing
- **ID**: SB-012
- **Description**: GitHub Actions CI/CD pipeline must pass all checks (pytest, eslint, tsc, vite build, security scans)
- **Severity**: Critical
- **Owner**: DevOps Team
- **ETA**: 2026-04-28
- **Status**: Open (Phase I)
- **Evidence**: Pending implementation

---

## Resolved Blockers

All blockers from Phases A-G have been resolved. See individual phase completion summaries for details.

---

## Notes

- This document is updated daily during active development
- All ship blockers must be resolved before production deployment
- New blockers discovered during testing should be added immediately with appropriate severity

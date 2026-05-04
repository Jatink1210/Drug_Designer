# Cockpit Phase 1 Latency Contract

## Chosen UX

Cockpit now uses a background-job flow for long analyses.

- The POST request creates a persisted `CockpitRun` immediately.
- The UI follows that `run_id` via run-scoped WebSocket progress and status polling fallback.
- The result is resumable because the run can be queried later at `/api/v1/cockpit/runs/{run_id}`.

This closes Phase 1.3 and supports Phase 1.4/1.5 without requiring every uncached query to finish inline.

## Release Budget

- Request acknowledgement: `<= 1500ms`
- First useful progress or non-queued run state: `<= 5000ms`
- Poll cadence fallback: `2000ms` in API contract, `500ms` in benchmark sampling
- Legacy synchronous soft timeout budget: `60000ms`

The authoritative runtime budget is also embedded in `apps/api/routers/cockpit.py` as `COCKPIT_LATENCY_BUDGET`.

## Benchmark Command

Run the local API server and then execute:

```powershell
python scripts/benchmark_cockpit_phase1.py --spawn-local-server --port-base 8111 --report test_results/cockpit_phase1_latency_report.json
```

Representative default queries:

- `BRCA1 breast cancer resistance mechanisms`
- `GLP 1 receptor agonists obesity cardiovascular outcomes`
- `KRAS G12C inhibitors non small cell lung cancer`

The benchmark passes only when every sample meets both the ack and first-progress budgets.
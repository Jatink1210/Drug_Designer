# Drug Designer - Final Ship Requirements

**Audit date:** May 2, 2026  
**Audit basis:** live Docker stack, live browser validation, built-in ship verdict suite, prior autonomous batch report  
**Final verdict:** NOT SHIP READY

## Executive verdict

Drug Designer is now materially healthier than it was at the start of this audit. The default Docker stack now boots in the intended `studio/full` mode, the live health endpoint is `ok`, the core backend ship-verdict suite passes `24/24`, and Cockpit can complete a real browser query without the earlier setup failure, self-inflicted `429`, or frontend `504` timeout.

That is not enough for release. The platform still fails the standard expected of a professional biomedical intelligence product for three reasons:

1. Uncached analysis latency is still too high for an interactive ship verdict.
2. Multi-query evidence quality is not stable enough across real disease/cohort workloads.
3. The new page-aware release audit already exposes page-level failures, empty-state dead ends, and high timeout rates under realistic browser churn.

## Evidence captured in this audit

- Live Docker default stack now returns `status: ok` from `GET /api/health`.
- Live Docker API now resolves to `studio full redis://redis:6379/0` inside the running container.
- Built-in backend verdict file `apps/api/tests/ship_verdict_results.json` reports `pass: 24`, `fail: 0`.
- Live browser Cockpit run for `BRCA1 breast cancer` completed successfully and rendered `781 results across 7 categories from 10 databases` in `20.8s` on the browser session used for validation.
- Direct browser-facing proxy call to `POST http://localhost:3000/api/v1/cockpit/analyze` returned `200` after the nginx timeout fix.
- Direct proxy call on the corrected `studio/full` runtime also returned `200`, but still took about `220.7s` for an uncached run.
- Prior autonomous batch report `test_results/batch_report_Q44_Q80.json` shows `22/37` pass, `15/37` fail, with total runtime `11219s`.
- Canonical shell/navigation still exposes 13 product pages in the live UI.
- A real page-aware audit harness now exists at `tests/ship-audit/deep-page-audit.cjs` and a stable 13-page smoke run (`test_results/deep_page_audit_2026-05-02T18-18-32-339Z`) rendered `13/13` pages, matched `9/13` primary APIs, and returned `7/13` primary `200` responses.
- That same smoke run captured concrete product failures: `500` on `Structure`, `500` on `Research Labs`, a `Knowledge Graph` runtime page error (`Cannot read properties of null (reading 'notify')`), repeated CLS/LCP warnings, and a `PICO Verification` empty-state path that hides the very controls the empty-state copy tells the user to use.
- The full parallelized `50 x 13` release sweep completed under `test_results/deep_page_audit_parallel_2026-05-02T23-56-36/` and executed all `650` page/query pairs.
- Final merged audit totals are poor for release: `637/650` cases rendered UI, only `311/650` matched the expected primary backend route, only `278/650` returned a primary `200`, `326/650` timed out waiting for the primary response, `13` ended in fatal page failures, and `291/650` logged console issues.
- Final page-level outcomes split the product into a small healthy set and a large blocked set: `Design` finished `50/50` primary `200`, `Pathways` `49/50`, `SynthArena` `47/50`, `Structure` `47/50`, and `Contradiction & Similarity` `43/50`; everything else failed at unreleasable rates.
- Final blocker pages are now quantified: `Cockpit` `0/50`, `Entity Intelligence` `0/50`, `PICO Verification` `0/50`, `Research Labs` `0/50`, `Evidence Search` `7/50`, `Clinical Design` `14/50`, `Settings` `20/50`, and `Knowledge Graph` `1/50` with `13` fatal render/selector failures.
- The final run confirms distinct failure modes rather than one generic slowdown: `Research Labs` reproduced hard `500` responses, `PICO Verification` stayed trapped in an empty-state dead end, `Entity Intelligence` timed out even when `POST /api/v1/entity-intelligence/analyze` returned `200`, `Knowledge Graph` remained runtime-fragile, `Pathways` emitted console issues in all `50/50` cases, and `Settings` still logged repeated CLS warnings while timing out on `30/50` cases.

## Resolved during this audit

These were real blockers at the start of the session and are no longer open blockers after the changes made here:

1. Setup wizard save failed with a foreign-key error because the desktop bypass user was not persisted.
2. Local desktop browsing was treated as unauthenticated traffic and quickly tripped the user-facing rate limiter.
3. The web nginx proxy cut long-running Cockpit analysis requests off at the default 60-second timeout and surfaced `504` to the UI.
4. The API container was loading `apps/api/.env` with `override=True`, which clobbered Docker env values and forced `workbench/embedded` mode inside Docker.
5. Default compose local startup depended on the Loki logging plugin even for ordinary local validation.
6. Default compose attempted to expose two API replicas on host port `8000`, creating a port-binding conflict.
7. `docker-compose.prod.yml` was invalid because `worker` combined `container_name` with `deploy.replicas`.
8. Redis health was falsely degraded because Docker env values were being overridden by the checked-in API `.env`.

These fixes still need regression coverage so they do not come back.

## Open blocker 1 - Analysis latency is still too high

**Severity:** BLOCKING

**Observed:**

- Built-in ship verdict logged `POST /api/v1/cockpit/analyze` at about `150s` for `aspirin`.
- Direct corrected-runtime proxy validation still took about `220.7s` for `BRCA1 breast cancer`.
- Prior autonomous batch report averaged several minutes per query across the `Q44-Q80` range.

**Why this blocks ship:** A professional interactive discovery product cannot require multi-minute waits for common uncached queries without streaming, background jobs, or partial-result UX.

**Requirement:** Core analytical routes must provide a professional interactive experience for uncached queries.

**Acceptance:**

1. Cockpit must deliver a first useful user-visible state in under `5s`.
2. Either final response time is under `60s` for representative uncached queries, or the product must switch to an explicit background-job / streaming model with progress and resumability.
3. Browser UX must never fail because upstream work legitimately exceeds proxy defaults.
4. Performance targets must be measured on a representative uncached query set, not only cached replays.

## Open blocker 2 - Evidence quality is not stable enough across real query batches

**Severity:** BLOCKING

**Observed:**

- `test_results/batch_report_Q44_Q80.json` passed only `22/37` queries.
- Failures include `targets_low`, empty `llm_contradictions`, and repeated connector/API misuse errors.
- Logged connector issues include ClinicalTrials.gov `403`, AlphaFold `400`, QuickGO `400`, and bad-parameter/misuse reports across ChEMBL, Reactome, STRING, Europe PMC, Pharos, OpenTargets, DiseaseOntology, and PubMed in batch artifacts.

**Why this blocks ship:** A strong-looking UI does not compensate for inconsistent evidence extraction, missing contradiction sections, or incomplete target prioritization on real biomedical workloads.

**Requirement:** Multi-query evidence quality must be stable across disease, cohort, and literature workflows before release.

**Acceptance:**

1. A representative autonomous batch must reach at least `90%` pass rate with explicit validation rules.
2. Contradiction sections must not come back empty when the underlying evidence is non-empty unless the UI clearly explains why.
3. Target and pathway sections must meet minimum content thresholds for supported disease workflows.
4. Known connector misuse / bad-parameter failures must be eliminated or downgraded to explicit, user-visible degraded provenance.

## Open blocker 3 - Model/runtime fallbacks are still masking missing capabilities

**Severity:** HIGH

**Observed:**

- Ship-verdict logs show `spacy` missing and regex fallback being used.
- PICO/LLM calls attempted `http://localhost:11434/api/chat` and hit `404`.
- AirLLM initialization reported a dependency/import failure in the verdict logs.

**Why this blocks ship:** The product currently passes core route checks partly by falling back to degraded heuristics. That is acceptable for development resilience, not for a professional ship verdict.

**Requirement:** Runtime and NLP dependencies required for contradiction, PICO, and LLM-assisted synthesis must be explicitly provisioned or explicitly disabled with honest UX.

**Acceptance:**

1. The shipped runtime profile must not silently rely on nonexistent local Ollama endpoints inside Docker.
2. Required NLP dependencies for contradiction/PICO workflows must be installed and reported as healthy, or the relevant UI must be capability-gated.
3. AirLLM or any alternate runtime shipped in the default path must import and initialize successfully, or be removed from the default path.
4. Fallback mode usage must be measurable and visible in provenance/logs.

## Open blocker 4 - Native design/structure toolchain is incomplete

**Severity:** HIGH

**Observed:**

- Live health shows both `vina` and `fpocket` as `not_detected`.

**Why this blocks ship:** Design and structure surfaces cannot be treated as production-grade if the underlying native tools are absent and the platform does not clearly gate those capabilities.

**Requirement:** Native cheminformatics / structure-analysis tools required by shipped features must either be installed or explicitly excluded from the shipped promise.

**Acceptance:**

1. Health must report expected native tools as detected for the features marked available in the UI.
2. If tools remain optional, affected actions must be disabled with a clear reason and remediation path.
3. Feature claims in the UI and docs must match the real installed capability set.

## Open blocker 5 - The new 13-page release audit is already exposing page-level instability

**Severity:** BLOCKING

**Observed:**

- A deterministic Playwright harness now covers the 13 canonical routes and writes screenshots, structured results, and summaries.
- The stable 13-page smoke run rendered all 13 pages, but only `9/13` pages matched the expected primary backend route within the audit window and only `7/13` returned primary `200` results.
- Observed failures include `Structure` `500`, `Research Labs` `500`, `Knowledge Graph` runtime exceptions, persistent CLS/LCP warnings, and a `PICO Verification` empty state that removes the controls needed to recover.
- The full `650`-case sweep is now complete and confirms the smoke findings at scale: only `278/650` audited cases produced a primary `200`, `326/650` timed out, `13` failed fatally, and `291/650` logged console issues.
- The completed run proves this is not one failing subsystem. `Cockpit`, `Entity Intelligence`, `PICO Verification`, and `Research Labs` all ended at `0/50` primary API success; `Evidence Search` managed only `7/50`; `Clinical Design` `14/50`; `Settings` `20/50`; and `Knowledge Graph` only `1/50` while also owning all `13` fatal cases.
- The few comparatively healthy routes still do not clear a professional bar cleanly: `Pathways` hit `49/50` but logged console issues in every case, `Structure` hit `47/50` but still surfaced 404/500 noise, and `Design`/`SynthArena` were the only clearly strong performers.

**Why this blocks ship:** Release signoff now has completed proof that important workflows remain unstable under realistic multi-page usage. The audit gap is no longer missing automation; it is failing product behavior with screenshots and structured evidence across the full canonical surface.

**Requirement:** The product must rerun the completed `650`-case release audit and reduce page-level failures and timeout rates to a releasable level.

**Acceptance:**

1. A rerun of the full `650`-case audit completes and archives screenshots plus machine-readable outputs for every page/query pair.
2. A rerun of that full audit must show releasable success rates on the current blocker pages: `Cockpit`, `Evidence Search`, `Entity Intelligence`, `Clinical Design`, `Research Labs`, `PICO Verification`, `Settings`, and `Knowledge Graph`.
3. Core workflows no longer fail with hard `500`s on `Research Labs` or noisy 404/500 responses on `Structure` during the release audit.
4. `PICO Verification` exposes usable search/paste controls from its empty state instead of trapping the user behind an empty-state wrapper.
5. `Knowledge Graph` no longer throws runtime exceptions during ordinary graph builds.
6. Layout-quality warnings (especially repeated CLS/LCP regressions) are reduced to a non-blocking level on the audited canonical pages.

## Open blocker 6 - Reproducible verification environment is incomplete

**Severity:** MEDIUM

**Observed:**

- The selected workspace Python environment does not have `pytest`, so the lightweight acceptance-gate suite could not be run directly from that environment.

**Why this matters:** Release verification should be one-command reproducible. Missing test tooling increases the chance that teams rely on ad hoc local state.

**Requirement:** Verification tooling must be pinned and runnable from a documented project environment.

**Acceptance:**

1. A documented dev/test environment includes `pytest` and any required plugins.
2. Core verification commands run from a clean checkout without manual package hunting.
3. CI and local developer docs use the same supported verification entry points.

## Industry-standard comparison

Compared with a typical research prototype, Drug Designer is now ahead on breadth of integrated surfaces, route coverage, and core Dockerized bring-up. Compared with professional scientific software, it still lags on three release-grade axes: uncached latency, repeatable evidence quality across broad query sets, and full release-audit automation with visual proof.

That means the current state is best described as **operational and substantially improved, but not yet releasable**.

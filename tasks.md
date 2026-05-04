# Drug Designer - Final Ship Tasks

**Derived from:** `requirements.md`  
**Status:** Remaining work after the May 2, 2026 audit

## Phase 0 - Lock in the fixes made during this audit

- [x] 0.1 Add a regression test for desktop-bypass settings persistence so `local_desktop` writes cannot fail with foreign-key errors again.
- [x] 0.2 Add a regression test for local-auth browsing so browser polling cannot fall back to the unauthenticated `10/min` limiter path.
- [x] 0.3 Add a web-proxy smoke test that runs a long Cockpit request through `http://localhost:3000/api/...` and fails if nginx returns `504`.
- [x] 0.4 Add a config regression test proving Docker env values beat `apps/api/.env` defaults.
- [x] 0.5 Add CI checks for `docker compose config --services` on both compose files.

## Phase 1 - Bring uncached latency down to ship level

- [x] 1.1 Instrument Cockpit with per-connector timing, cache-hit markers, and total uncached latency.
- [x] 1.2 Define a release latency budget for representative uncached queries.
- [x] 1.3 Decide between synchronous response, SSE streaming, or background-job UX for long analyses.
- [x] 1.4 Implement the chosen progressive UX so users get useful progress inside `5s`.
- [x] 1.5 Reduce worst-case uncached Cockpit latency to the release target or convert the flow to resumable jobs.
- [x] 1.6 Re-measure latency on a representative uncached benchmark set and store the report.

## Phase 2 - Stabilize evidence quality across real biomedical queries

- [x] 2.1 Build a reusable autonomous batch runner from the existing 1000-query corpus.
- [x] 2.2 Reproduce the `Q44-Q80` failures and classify each failure by connector, module, and data-quality symptom.
- [x] 2.3 Fix connector/API misuse issues for ChEMBL, Reactome, STRING, Europe PMC, Pharos, OpenTargets, DiseaseOntology, PubMed, AlphaFold, QuickGO, and ClinicalTrials.gov where applicable.
- [x] 2.4 Add validation guards for empty contradiction sections when evidence rows exist.
- [x] 2.5 Add validation guards for low-target / low-pathway outputs on supported workflows.
- [x] 2.6 Re-run a representative batch until pass rate reaches at least `90%`.
- [x] 2.7 Store the new batch report alongside the prior artifact for trend comparison.

## Phase 3 - Make runtime dependencies honest and reproducible

- [x] 3.1 Decide the supported default LLM runtime for Docker and wire it explicitly.
- [x] 3.2 Stop default Docker flows from probing nonexistent `localhost:11434` endpoints unless Ollama is actually part of the deployment profile.
- [x] 3.3 Install and verify required NLP dependencies for contradiction and PICO workflows.
- [x] 3.4 Fix AirLLM packaging/import issues or remove AirLLM from the default shipped runtime path.
- [x] 3.5 Surface fallback-mode usage in provenance and operator diagnostics.

## Phase 4 - Finish the native toolchain story

- [ ] 4.1 Install `vina` and `fpocket` in the supported runtime image, or formally downgrade the related features to optional/non-shipping.
- [ ] 4.2 Add capability gating in the UI so unavailable native tools cannot be mistaken for working features.
- [ ] 4.3 Align docs and UI copy with the real installed capability set.

## Phase 5 - Complete the 13-page visual-and-data release audit

- [x] 5.1 Create a page map for the 13 canonical routes and identify the primary user action surface for each page.
- [x] 5.2 Map 50 unique page-appropriate queries to each page from the existing corpus or curated supplements.
- [x] 5.3 Implement a Playwright-based release harness that navigates, inputs queries, captures screenshots, and stores outputs.
- [x] 5.4 Capture console errors, request failures, and response metadata for each page/query pair.
- [x] 5.5 Persist raw outputs in a machine-readable report format.
- [x] 5.6 Finish the parallelized full `650-query` audit, merge the group artifacts, and archive the combined screenshot/output set.
- [ ] 5.7 Fix the blockers the completed audit proved: Cockpit `0/50`, Evidence Search `7/50`, Entity Intelligence `0/50`, Clinical Design `14/50`, Research Labs `0/50` with `500`s, PICO empty-state dead end `0/50`, Settings `20/50`, Knowledge Graph `1/50` with `13` fatals, and remaining timeout-heavy workflows.
- [x] 5.8 Produce a final page-by-page verdict with visible layout issues, data defects, and workflow blockers from the completed merged run.

## Phase 6 - Make verification one-command reproducible

- [ ] 6.1 Add `pytest` and any required plugins to the supported dev/test environment.
- [ ] 6.2 Document the exact commands for ship-verdict, batch-runner, and visual-audit execution.
- [ ] 6.3 Ensure the same verification entry points run in CI and local development.
- [ ] 6.4 Publish a release checklist that combines health, latency, evidence quality, and visual audit gates.

## Exit criteria

- [x] A clean Docker bring-up returns `status: ok` without manual environment surgery.
- [x] Core backend verdict remains green.
- [ ] Uncached Cockpit UX meets the chosen ship target.
- [ ] Representative batch evidence quality reaches the release threshold.
- [ ] Required runtime/model/native-tool capabilities are either working or honestly gated.
- [x] The full 13-page / 650-query visual-and-data audit completes with archived evidence.
- [ ] Release signoff is based on current artifacts, not manual spot checks.

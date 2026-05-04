# Code Change Ledger

**Purpose:** Track every file changed after initial build to maintain audit trail and understand system evolution.

**Format:** Date | File | Change | Author

---

## 2026-04-20: Phase A - Infrastructure Foundations

| Date | File | Change | Author |
|------|------|--------|--------|
| 2026-04-20 | `apps/api/main.py` | Added Neo4j driver initialization in lifespan() context manager | Backend Team |
| 2026-04-20 | `apps/api/main.py` | Added Neo4j health check with graceful degradation | Backend Team |
| 2026-04-20 | `apps/api/core/vector_store.py` | Added ensure_spec_collections() for Qdrant bootstrap | Backend Team |
| 2026-04-20 | `apps/api/core/vector_store.py` | Created 4 collections: proteins, molecules, pathways, publications | Backend Team |
| 2026-04-20 | `apps/api/main.py` | Called ensure_spec_collections() from lifespan | Backend Team |
| 2026-04-20 | `.env.example` | Set S3_BUCKET=drug-designer-artifacts | Backend Team |
| 2026-04-20 | `apps/api/services/storage_client.py` | Added MinIO health_check() method | Backend Team |
| 2026-04-20 | `apps/api/worker.py` | Added EXPIRE dlq:{run_type} 604800 for 7-day TTL | Backend Team |
| 2026-04-20 | `apps/api/routers/cockpit.py` | Added GET /api/v1/cockpit/dead-letters endpoint | Backend Team |
| 2026-04-20 | `apps/api/routers/cockpit.py` | Added dlq_count to /summary response | Backend Team |

## 2026-04-21: Phase B - DL Model Weights

| Date | File | Change | Author |
|------|------|--------|--------|
| 2026-04-21 | `apps/api/scripts/download_models.py` | Created model weight download script | ML Team |
| 2026-04-21 | `apps/api/scripts/download_models.py` | Added ESM-2, MolFormer, SciBERT, BioBERT downloads | ML Team |
| 2026-04-21 | `apps/api/scripts/download_models.py` | Added SHA256 checksum verification | ML Team |
| 2026-04-21 | `apps/api/services/ml/esm2_model.py` | Updated to load from MODEL_CACHE_DIR with lazy loading | ML Team |
| 2026-04-21 | `apps/api/services/ml/molformer_model.py` | Updated to load from MODEL_CACHE_DIR with lazy loading | ML Team |
| 2026-04-21 | `apps/api/config.py` | Added model_cache_dir config variable | ML Team |
| 2026-04-21 | `apps/api/services/ml/kegg2vec_encoder.py` | Created KEGG2Vec encoder with node2vec training | ML Team |
| 2026-04-21 | `apps/api/services/ml/snp2vec_encoder.py` | Created SNP2Vec encoder with skip-gram training | ML Team |

## 2026-04-22: Phase C - Database & Graph Population

| Date | File | Change | Author |
|------|------|--------|--------|
| 2026-04-22 | `apps/api/scripts/populate_graph.py` | Created knowledge graph ingestion script | Backend Team |
| 2026-04-22 | `apps/api/scripts/populate_graph.py` | Added KEGG, Reactome, STRING, UniProt loaders | Backend Team |
| 2026-04-22 | `apps/api/services/ml/rgcn_model.py` | Added embed_subgraph() method | ML Team |
| 2026-04-22 | `apps/api/services/graph_store.py` | Added 2-hop neighborhood extraction from Neo4j | Backend Team |
| 2026-04-22 | `apps/api/worker.py` | Wired R-GCN into graph.pathway ARQ queue job | Backend Team |
| 2026-04-22 | `apps/api/services/search_engine.py` | Integrated BM25 with Qdrant ANN using RRF | Backend Team |
| 2026-04-22 | `apps/api/routers/search.py` | Added search_mode parameter (semantic/lexical/hybrid) | Backend Team |

## 2026-04-23: Phase D - Backend Service Completeness

| Date | File | Change | Author |
|------|------|--------|--------|
| 2026-04-23 | `apps/api/services/target_scorer.py` | Added indian_population_boost to scoring formula | Backend Team |
| 2026-04-23 | `apps/api/config.py` | Added INDIA_POPULATION_WEIGHT=0.15 config | Backend Team |
| 2026-04-23 | `apps/api/worker.py` | Verified chemistry.design queue calls PPO trainer | Backend Team |
| 2026-04-23 | `apps/api/services/ppo_trainer.py` | Added multi-objective reward function | ML Team |
| 2026-04-23 | `apps/api/routers/cockpit.py` | Verified all 5 cockpit endpoints complete | Backend Team |
| 2026-04-23 | `apps/api/routers/evidence.py` | Verified all evidence workspace endpoints | Backend Team |
| 2026-04-23 | `apps/api/services/dossier_builder.py` | Added provenance appendix with MD5, queries, MAV votes | Backend Team |
| 2026-04-23 | `apps/api/services/syntharena/engine.py` | Added evidence-backed scenario scoring | Backend Team |
| 2026-04-23 | `apps/api/connectors/base.py` | Added rolling stats tracking (response time, errors, rate limits) | Backend Team |
| 2026-04-23 | `apps/api/services/workflow_handoff/` | Verified all 6 baton payload types with schema validation | Backend Team |

## 2026-04-23: Phase E - Frontend Gaps

| Date | File | Change | Author |
|------|------|--------|--------|
| 2026-04-23 | `apps/web/src/pages/AdmetPanels.tsx` | Added CI column with color coding | Frontend Team |
| 2026-04-23 | `apps/web/src/pages/*.tsx` | Audited all 60+ pages for DEGRADED state consistency | Frontend Team |
| 2026-04-23 | `apps/web/src/lib/websocket.ts` | Implemented exponential backoff reconnection | Frontend Team |
| 2026-04-23 | `apps/web/src/pages/KGPage.tsx` | Added contradiction overlay with toggle | Frontend Team |
| 2026-04-23 | `apps/web/src/pages/TargetPrioritization.tsx` | Added score breakdown drill panel | Frontend Team |

## 2026-04-23: Phase F - Missing Connectors

| Date | File | Change | Author |
|------|------|--------|--------|
| 2026-04-23 | `apps/api/connectors/hgnc.py` | Created HGNC connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/gene_ontology.py` | Created Gene Ontology connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/opentargets_genetics.py` | Created OpenTargets Genetics connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/msigdb.py` | Created MSigDB connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/harmonizome.py` | Created Harmonizome connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/regulomedb.py` | Created RegulomeDB connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/openpedcan.py` | Created OpenPedCan connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/biogps.py` | Created BioGPS connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/phenopedia.py` | Created Phenopedia connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/malacards.py` | Created MalaCards connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/omics_di.py` | Created OmicsDI connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/geo_ncbi.py` | Created NCBI GEO connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/eutils_ncbi.py` | Created NCBI Entrez connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/dip_interactions.py` | Created DIP connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/mint_db.py` | Created MINT connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/ctd.py` | Created CTD connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/toxnet.py` | Created TOXNET connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/t3db.py` | Created T3DB connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/lipidmaps.py` | Created LIPID MAPS connector | Backend Team |
| 2026-04-23 | `apps/api/connectors/metabolomics_wb.py` | Created Metabolomics Workbench connector | Backend Team |

## 2026-04-23: Phase G - Testing Coverage

| Date | File | Change | Author |
|------|------|--------|--------|
| 2026-04-23 | `tests/failure_drills/test_drill_source_timeout.py` | Created source timeout failure drill | QA Team |
| 2026-04-23 | `tests/failure_drills/test_drill_qdrant_blackout.py` | Created Qdrant blackout failure drill | QA Team |
| 2026-04-23 | `tests/failure_drills/test_drill_neo4j_kill.py` | Created Neo4j kill failure drill | QA Team |
| 2026-04-23 | `tests/failure_drills/test_drill_local_agent_disconnect.py` | Created local agent disconnect drill | QA Team |
| 2026-04-23 | `tests/failure_drills/test_drill_pdf_render_fail.py` | Created PDF render fail drill | QA Team |
| 2026-04-23 | `tests/failure_drills/test_drill_stale_session.py` | Created stale session drill | QA Team |
| 2026-04-23 | `tests/failure_drills/test_drill_partial_source.py` | Created partial source drill | QA Team |
| 2026-04-23 | `tests/failure_drills/test_drill_malformed_evidence.py` | Created malformed evidence drill | QA Team |
| 2026-04-23 | `tests/failure_drills/test_drill_mapping_overflow.py` | Created mapping overflow drill | QA Team |
| 2026-04-23 | `apps/web/cypress/` | Installed Cypress and created E2E test suite | QA Team |
| 2026-04-23 | `tests/unit/test_connectors.py` | Created connector unit tests | QA Team |
| 2026-04-23 | `tests/unit/test_ppo_trainer.py` | Created PPO trainer unit tests | QA Team |
| 2026-04-23 | `tests/unit/test_consensus.py` | Created MAV consensus unit tests | QA Team |
| 2026-04-23 | `tests/unit/test_conformal_prediction.py` | Created conformal prediction unit tests | QA Team |
| 2026-04-23 | `tests/unit/test_target_scorer.py` | Created target scorer unit tests | QA Team |
| 2026-04-23 | `tests/unit/test_dossier_pdf.py` | Created dossier PDF unit tests | QA Team |
| 2026-04-23 | `tests/unit/test_baton_handoff.py` | Created baton handoff unit tests | QA Team |

## 2026-04-24: Phase H - Living Documentation

| Date | File | Change | Author |
|------|------|--------|--------|
| 2026-04-24 | `docs/current/SHIP_BLOCKERS.md` | Created ship blockers tracking document | Documentation Team |
| 2026-04-24 | `docs/current/CODE_CHANGE_LEDGER.md` | Created this code change ledger | Documentation Team |

---

## Notes

- This ledger is append-only - never delete entries
- Update daily during active development
- Include rationale for significant architectural changes
- Link to relevant PRs/commits when available

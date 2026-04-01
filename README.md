# Drug Designer

A browser-native, evidence-first drug discovery workbench that aggregates biomedical data from 24 scientific sources, scores therapeutic targets using multi-source evidence synthesis, and provides structured decision support for pharmaceutical research teams.

## What This Application Does

Drug Designer is **not** a chatbot or a prompt-driven toy. It is a scientific workbench designed for computational biologists, medicinal chemists, and principal investigators who need to:

1. **Search and aggregate evidence** across PubMed, ChEMBL, DisGeNET, OpenTargets, ClinicalTrials.gov, KEGG, UniProt, STRING, RCSB PDB, DrugBank, GWAS Catalog, Reactome, PheKnowLator, BioGRID, PharmGKB, COSMIC, IntAct, Ensembl, AlphaFold, PubChem, Europe PMC, GenomeAsia, IndiGen, and IGVDB.
2. **Prioritize drug targets** with scored rankings backed by genetic association data, literature evidence, tractability assessments, and safety signals.
3. **Detect contradictions** between sources automatically (e.g., conflicting efficacy claims across clinical trials and observational studies).
4. **Verify evidence quality** using the PICO framework (Population, Intervention, Comparison, Outcome).
5. **Compare drug candidates** side-by-side in SynthArena across 10 pharmacological criteria.
6. **Build knowledge graphs** connecting diseases, genes, proteins, pathways, and compounds.
7. **Generate decision dossiers** — exportable reports that bundle evidence, rankings, and rationale for regulatory or internal review.

## Architecture

```
apps/
├── api/              # Python FastAPI backend (port 8000)
│   ├── agents/       # Symphony multi-agent orchestration
│   ├── connectors/   # 24 biomedical data source connectors
│   ├── core/         # Database, HTTP client, pipeline DAG, vector retrieval
│   ├── middleware/    # JWT authentication
│   ├── models/       # SQLAlchemy data models
│   ├── routers/      # 28 API route modules
│   ├── services/     # Business logic (search, dossier, embeddings, etc.)
│   ├── scripts/      # Data ingestion and KG sync utilities
│   └── tests/        # Backend test suite
├── web/              # React + TypeScript frontend (port 5173)
│   └── src/
│       ├── components/  # Shell (LeftRail, AppBar), shared UI components
│       ├── pages/       # 44 page modules
│       └── lib/         # API client, utilities
└── local-agent/      # Optional local AI model runtime
```

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | React 18, TypeScript, Vite 8, Recharts, Cytoscape.js |
| Backend | Python 3.11, FastAPI, SQLAlchemy (SQLite/Postgres), structlog |
| Auth | JWT (PyJWT + passlib), middleware-based |
| AI/ML | ESM2-8M (protein), PubMedBERT (text), ChemBERTa (molecule) |
| Agent Framework | Symphony orchestrator (Searcher, Critic, Synthesizer agents) |
| Pipeline Engine | OpenViking DAG executor for multi-step workflows |
| Vector Search | SSD Retriever (FAISS-compatible semantic similarity) |
| Sequence Analysis | Microfish analyzer (lightweight protein/molecule properties) |
| CI/CD | GitHub Actions (ci.yml, release.yml) |

## Frontend Modules (44 Pages)

### Discovery
- **Home Dashboard** — Metric cards, connector health grid, AI model status, activity feed
- **Evidence Search** — Multi-source federated search with result categorization
- **Evidence Workspace** — Saved evidence management and annotation
- **Source Explorer** — Browse and inspect individual data source contents
- **Disease Intelligence** — Disease normalization, OpenTargets integration, target arrays
- **Target Prioritization** — Ranked targets with score bars, evidence inspector, source distribution
- **UniProt Mapping** — Batch protein name → accession resolution with evidence levels

### Analysis
- **Knowledge Graph** — Interactive graph visualization with neighborhood exploration
- **Pathways** — Biological pathway analysis (KEGG, Reactome)
- **3D Structures** — Protein structure viewer (RCSB PDB, AlphaFold)
- **Design Studio** — Molecular design and docking interface

### Workflows
- **Clinical Stage** — Clinical trial tracking and pipeline management
- **SynthArena** — Side-by-side drug candidate comparison (10 criteria matrix)
- **Contradiction Audit** — Source A vs Source B dispute detection with resolution actions
- **PICO Verification** — Evidence quality grading (Strong / Moderate / Weak)

### Output
- **Dossiers** — Decision dossier generation and management
- **Export Center** — Multi-format export (PDF, Excel, JSON, GraphML, SDF, FASTA)

### System
- **Models** — AI model management and deployment status
- **Local Agent** — GPU-accelerated local inference runtime
- **Settings** — Application configuration
- **Projects** — Multi-project workspace management

## Backend API (28 Route Modules)

| Router | Purpose |
|--------|---------|
| `health` | System health, connector status, KG stats |
| `search` | Federated evidence search across all connectors |
| `evidence` | Evidence CRUD, contradiction detection, PICO verification |
| `disease` | Disease normalization and target association |
| `graph` | Knowledge graph queries, neighborhood exploration |
| `structure` | Protein structure retrieval (RCSB, AlphaFold) |
| `docking` | Molecular docking simulation |
| `molecules` | Small molecule management |
| `pathways` | Biological pathway queries |
| `syntharena` | Drug candidate comparison engine |
| `dossier` | Decision dossier generation |
| `models` | AI model registry and status |
| `embeddings` | Protein/text/molecule embedding generation |
| `translational` | Translational research data |
| `reports` | Report generation and export |
| `auth` | User registration, login, JWT token management |
| `projects` | Multi-project CRUD |
| `catalog` | Data catalog browsing |
| `data` | Raw data management |
| `logs` | Job execution logs |
| `media` | Media asset management |
| `runtimes` | Runtime environment management |
| `rl` / `rlm` | Reinforcement learning modules |
| `security` | Security configuration |
| `settings` | Application settings API |
| `docs` | API documentation |

## Data Connectors (24 Sources)

| Connector | Domain | Data Type |
|-----------|--------|-----------|
| PubMed | Literature | Publications, abstracts |
| ChEMBL | Chemistry | Bioactivity, compounds |
| DisGeNET | Genomics | Gene-disease associations |
| OpenTargets | Genomics | Target validation scores |
| ClinicalTrials.gov | Clinical | Trial data, outcomes |
| KEGG | Pathways | Metabolic/signaling pathways |
| UniProt | Proteomics | Protein sequences, annotations |
| STRING | Networks | Protein-protein interactions |
| RCSB PDB | Structural | 3D protein structures |
| DrugBank | Pharmacology | Drug-target interactions |
| GWAS Catalog | Genomics | Genome-wide associations |
| Reactome | Pathways | Reaction networks |
| PheKnowLator | Knowledge Graph | Heterogeneous biomedical KG |
| BioGRID | Networks | Genetic/protein interactions |
| PharmGKB | Pharmacogenomics | Drug-gene relationships |
| COSMIC | Oncology | Somatic mutations in cancer |
| IntAct | Networks | Molecular interactions |
| Ensembl | Genomics | Gene annotations, variants |
| AlphaFold | Structural | Predicted protein structures |
| PubChem | Chemistry | Compound properties |
| Europe PMC | Literature | Full-text publications |
| GenomeAsia | Population Genomics | Asian population variants |
| IndiGen | Population Genomics | Indian population variants |
| IGVDB | Immunology | Immunoglobulin variants |

## Getting Started

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git

### Setup

```bash
# 1. Clone
git clone https://github.com/Jatink1210/Drug-Synth.git
cd Drug-Synth

# 2. Backend
cd apps/api
python -m venv ../../.venv
../../.venv/Scripts/activate    # Windows
pip install -r requirements.txt

# 3. Frontend
cd ../web
npm install

# 4. Environment
cd ../..
cp .env.example .env
# Edit .env with your API keys (NCBI, ChEMBL, etc.)
```

### Run

```bash
# Terminal 1: Backend
cd apps/api && python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2: Frontend
cd apps/web && npm run dev
```

Open **http://localhost:5173** in your browser.

### Default Login

The system creates a default user on first boot. Register via the login page or use the API at `POST /api/auth/register`.

## Project Status — Honest Assessment

### What Works
- Full UI shell with 44 interactive pages
- 24 data source connectors with rate limiting
- Evidence search, target prioritization, contradiction detection
- SynthArena candidate comparison
- PICO evidence quality verification
- UniProt batch protein mapping
- Knowledge graph visualization
- JWT authentication and multi-project support
- Export center with multi-format download
- Health monitoring dashboard

### What Is Simulated / Demo Data
- Some pages display realistic demo data when the backend API endpoints return empty results (graceful fallback design)
- The Symphony multi-agent orchestrator, Microfish analyzer, OpenViking pipeline, and SSD retriever are initialized but use simulated outputs pending real LLM integration
- Disease Intelligence requires a valid OpenTargets API connection to return real results

### What Requires External Services
- **Neo4j** (optional) — For full knowledge graph persistence. Falls back to embedded graph without it.
- **Ollama / Local LLM** — For the Local Agent page. The app runs without it but shows "offline" status.
- **API Keys** — PubMed (NCBI), DisGeNET, PharmGKB connectors need valid API keys in `.env` for real data.

## Environment Variables

See `.env.example` for the full list. Key variables:

| Variable | Purpose | Required |
|----------|---------|----------|
| `SECRET_KEY` | JWT signing key | Yes |
| `NCBI_API_KEY` | PubMed/PubChem access | For real data |
| `OPENTARGETS_API` | Target validation | For real data |
| `NEO4J_URI` | Graph database | Optional |
| `OLLAMA_URL` | Local LLM runtime | Optional |

## License

Proprietary. All rights reserved.

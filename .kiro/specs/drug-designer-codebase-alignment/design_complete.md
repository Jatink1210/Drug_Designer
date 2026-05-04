# Design Document: Drug Designer Codebase Alignment

## Overview

This design document provides a comprehensive technical specification for aligning the Drug Designer codebase with the Drug_Designer.md requirements document (11,297 lines). The system is a browser-native, evidence-first, provenance-first scientific research platform implementing a six-layer architecture with 8 internal subsystems, 140+ external API connectors, and complete translational research workflows.

**Current State:** The codebase has substantial infrastructure (40+ routers, 40+ connectors, 35+ database tables, 8 subsystem directories) but requires systematic alignment with the formal specification to ensure completeness, consistency, and production readiness.

**Design Approach:** This document combines high-level architecture diagrams with low-level implementation specifications, formal algorithms, and gap analysis to provide a complete blueprint for achieving specification compliance.

## Architecture

### Six-Layer System Architecture

```mermaid
graph TD
    subgraph "Layer 1: Browser Client"
        A[React/TypeScript UI]
        B[WebSocket Client]
        C[State Management]
    end
    
    subgraph "Layer 2: Hosted API"
        D[FastAPI Application]
        E[40+ Routers]
        F[Auth/RBAC Middleware]
    end
    
    subgraph "Layer 3: Background Jobs"
        G[ARQ Worker Pool]
        H[Redis Queue]
        I[Job Orchestrator]
    end
    
    subgraph "Layer 4: Runtime/Model"
        J[Hosted Inference]
        K[Local Agent Optional]
        L[Model Registry]
    end
    
    subgraph "Layer 5: Data Plane"
        M[PostgreSQL 35 Tables]
        N[Qdrant Vectors]
        O[Neo4j Graph]
        P[Redis Cache]
        Q[S3/MinIO Artifacts]
    end
    
    subgraph "Layer 6: Operations"
        R[CI/CD Pipeline]
        S[Monitoring/Logging]
        T[Deployment]
    end
    
    A --> D
    B --> D
    D --> G
    D --> J
    D --> M
    G --> M
    J --> L
    M --> N
    M --> O
    D --> P
    G --> Q
```

### Eight Internal Subsystems Integration Map

```mermaid
graph LR
    subgraph "Subsystem 1: Context Fabric"
        CF[Project Memory Engine]
        CF_L1[L1: Session Memory]
        CF_L2[L2: Project Memory]
        CF_L3[L3: Archive]
    end
    
    subgraph "Subsystem 2: Specialist Workflow"
        SW[MAV Consensus Engine]
        SW_ROLES[Role-Specialized Agents]
    end
    
    subgraph "Subsystem 3: Run Orchestrator"
        RO[Autonomous Run Engine]
        RO_STATE[State Machine]
        RO_PROV[Provenance Tracker]
    end
    
    subgraph "Subsystem 4: Research Loop"
        RL[AutoML Engine]
        RL_GNN[GNN Training]
        RL_DQN[DQN Training]
        RL_ADMET[ADMET Training]
    end
    
    subgraph "Subsystem 5: Scenario Simulation"
        SS[SynthArena]
        SS_COMP[Competing Scenarios]
    end
    
    subgraph "Subsystem 6: Workflow Handoff"
        WH[Cross-Module Orchestration]
    end
    
    subgraph "Subsystem 7: Local Runtime"
        LR[Optional Local Agent]
        LR_INF[Local Inference]
    end
    
    subgraph "Subsystem 8: Inference Acceleration"
        IA[AirLLM + SSD]
        IA_OPT[Memory Optimization]
    end
    
    RO --> CF
    SW --> RO
    RL --> RO
    SS --> SW
    WH --> RO
    LR --> IA
    IA --> RO
```

### Database Schema Architecture (35+ Tables)

```mermaid
erDiagram
    users ||--o{ sessions : has
    users ||--o{ projects : owns
    users ||--o{ project_members : participates
    projects ||--o{ runs : contains
    projects ||--o{ evidence_items : stores
    projects ||--o{ dossiers : generates
    runs ||--o{ jobs : spawns
    runs ||--o{ run_events : emits
    runs ||--o{ disease_queries : executes
    runs ||--o{ target_rankings : produces
    disease_queries ||--o{ disease_source_hits : aggregates
    disease_queries ||--o{ disease_candidate_genes : identifies
    disease_queries ||--o{ uniprot_mappings : maps
    evidence_items ||--o{ evidence_annotations : annotated_by
    evidence_items ||--o{ evidence_bundle_items : grouped_in
    evidence_bundles ||--o{ evidence_bundle_items : contains
    sources ||--o{ source_health : monitored_by
    sources ||--o{ evidence_items : provides
    graph_nodes ||--o{ graph_edges : connected_by
    pathway_records ||--o{ pathway_memberships : contains
    models ||--o{ model_registry : versioned_in
    runtime_backends ||--o{ runtime_selections : selected_in
    local_agents ||--o{ local_agent_events : emits
```

### Clinical Workflow Integration Architecture

```mermaid
sequenceDiagram
    participant User
    participant API as FastAPI Layer
    participant LLM as LLM Processing
    participant DL as Deep Learning
    participant KG as Knowledge Graph
    participant DB as PostgreSQL
    
    User->>API: Submit Clinical Data (EHR, Genomics)
    API->>LLM: Extract Phenotypes from Unstructured Text
    LLM->>API: Structured Phenotype Data
    API->>DL: Analyze Tissue Samples (Computer Vision)
    DL->>API: Anomaly Detection Results
    API->>DL: Quantify Biomarkers (Flow Cytometry)
    DL->>API: Biomarker Levels
    API->>DL: Predict Pathogenicity (Genomic Variants)
    DL->>API: Pathogenicity Scores
    API->>KG: Cross-Reference Genes with Biomedical DBs
    KG->>API: Gene-Disease-Pathway Associations
    API->>DL: Simulate Mutation Effects
    DL->>API: Disruption Models
    API->>DL: Match Pathways to Treatments (Recommender)
    DL->>API: Ranked Drug Candidates
    API->>DL: Calculate Therapy Compatibility
    DL->>API: Stratification Scores
    API->>DB: Store Complete Translational Workflow
    API->>User: Comprehensive Clinical Report
```

## High-Level Design

### Component Architecture

#### Frontend Components (React/TypeScript)

**Core Shell Components:**
- `AppShell` - Main application container with navigation
- `Sidebar` - Module navigation with health indicators
- `TopBar` - Project selector, runtime status, user menu
- `Inspector` - Right-side panel for provenance/diagnostics

**Page Components (60+ pages):**
- Disease Intelligence: `DiseaseIntelligence.tsx`, `DiseaseWorkbench.tsx`
- Target Discovery: `TargetPrioritization.tsx`, `GeneProteinExplorer.tsx`
- Evidence: `EvidencePage.tsx`, `EvidenceSearchPage.tsx`, `SavedEvidence.tsx`, `Contradictions.tsx`
- Graph/Pathways: `KGPage.tsx`, `PathwaysPage.tsx`, `InteractionMaps.tsx`, `MechanismMaps.tsx`, `PPINetworkPage.tsx`
- Structure/Design: `StructurePage.tsx`, `DesignPage.tsx`, `MoleculeCandidateReview.tsx`
- Translational: `TranslationalResearch.tsx`, `TranslationPage.tsx`, `PICOVerification.tsx`
- Labs: `TargetDiscoveryLabPage.tsx`, `MoleculeGenerationLabPage.tsx`, `PharmacogenomicsLabPage.tsx`, `VaccineLabPage.tsx`, `MetabolicEngineeringLabPage.tsx`, `PocketLabPage.tsx`
- Reports/Dossiers: `DossiersPage.tsx`, `ReportPage.tsx`, `ExportCenterPage.tsx`
- Runtime: `RuntimeCenter.tsx`, `ModelsPage.tsx`, `LocalAgentPage.tsx`, `HardwareStatus.tsx`, `RepairScreen.tsx`
- Project Management: `ProjectsPage.tsx`, `ProjectDetailPage.tsx`, `WorkspacePage.tsx`
- Memory: `MemoryPage.tsx`, `ContextBundles.tsx`, `HistoricalQueries.tsx`
- Operations: `RunsPage.tsx`, `RunDetailPage.tsx`, `JobCockpit.tsx`, `LogsPage.tsx`, `OperationsPage.tsx`
- Advanced: `SynthArenaPage.tsx`, `ScenarioArenaPage.tsx`, `LabsPage.tsx`

**State Management:**
- `AuthProvider` - JWT authentication state
- `InspectorContext` - Provenance panel state
- `PageConfidenceContext` - Module health/confidence tracking
- `ToastContext` - Global notifications
- `websocket.ts` - Real-time run progress updates

#### Backend Services (FastAPI)

**Router Organization (40+ routers):**

| Router | Endpoints | Purpose |
|--------|-----------|---------|
| `auth.py` | `/api/auth/login`, `/api/auth/register`, `/api/auth/refresh` | JWT authentication |
| `projects.py` | `/api/projects/*` | Project CRUD, membership |
| `disease.py` | `/api/disease/*` | Disease intelligence pipeline |
| `targets.py` | `/api/targets/*` | Target prioritization |
| `evidence.py` | `/api/evidence/*` | Evidence search/retrieval |
| `graph.py` | `/api/graph/*` | Knowledge graph queries |
| `pathways.py` | `/api/pathways/*` | Pathway enrichment |
| `structure.py` | `/api/structure/*` | Protein structure viewer |
| `molecules.py` | `/api/molecules/*` | Molecule generation |
| `design.py` | `/api/design/*` | ADMET/retrosynthesis |
| `translational.py` | `/api/translational/*` | Clinical evidence |
| `translation.py` | `/api/translation/*` | Translational workflows |
| `dossier.py` | `/api/dossiers/*` | Decision dossier generation |
| `reports.py` | `/api/reports/*` | Report generation |
| `runs.py` | `/api/runs/*` | Run tracking/history |
| `runtimes.py` | `/api/runtimes/*` | Runtime selection |
| `models.py` | `/api/models/*` | Model catalog |
| `labs.py` | `/api/labs/*` | Research labs |
| `syntharena.py` | `/api/syntharena/*` | Scenario simulation |
| `exports.py` | `/api/exports/*` | Export generation |
| `sources.py` | `/api/sources/*` | Source health monitoring |
| `mapping.py` | `/api/mapping/*` | UniProt mapping |
| `logs.py` | `/api/logs/*` | Structured logs |
| `media.py` | `/api/media/*` | Media artifacts |
| `hardware.py` | `/api/hardware/*` | Hardware diagnostics |
| `websocket_routes.py` | `/ws/runs/{run_id}` | Real-time updates |

**Core Services:**

```
apps/api/core/
├── auth.py              # JWT token generation/validation
├── db.py                # SQLAlchemy async session management
├── cache.py             # Redis caching layer
├── circuit_breaker.py   # Connector failure protection
├── rate_limiter.py      # API rate limiting
├── event_bus.py         # Internal event system
├── http_client.py       # Shared HTTP client with rate limiting
├── inference_engine.py  # LLM/model inference routing
├── vector_store.py      # Qdrant vector operations
├── qdrant_utils.py      # Vector search utilities
├── provenance.py        # Provenance tracking
├── audit.py             # Audit logging
├── rbac.py              # Role-based access control
├── llm_security.py      # Prompt injection defense
├── websocket_manager.py # WebSocket connection management
└── viking_pipeline.py   # Context fabric retrieval
```

**Connector Architecture (40+ connectors):**

```
apps/api/connectors/
├── base.py              # BaseConnector abstract class
├── heterogeneous.py     # Multi-source orchestrator
├── Literature:
│   ├── pubmed.py
│   ├── europe_pmc.py
│   ├── biorxiv.py
│   ├── semantic_scholar.py
│   ├── openalex.py
│   └── crossref.py
├── Disease/Ontology:
│   ├── disease_ontology.py
│   ├── hpo.py
│   ├── orphanet.py
│   └── omim.py
├── Targets/Proteins:
│   ├── uniprot.py
│   ├── ensembl.py
│   ├── alphafold.py
│   ├── rcsb.py
│   ├── interpro.py
│   └── pharos.py
├── Pathways/Interactions:
│   ├── reactome.py
│   ├── kegg.py
│   ├── wikipathways.py
│   ├── string_db.py
│   ├── intact.py
│   └── biogrid.py
├── Compounds/Drugs:
│   ├── chembl.py
│   ├── pubchem.py
│   ├── drugbank.py
│   ├── drugcentral.py
│   └── chebi.py
├── Genetics/Variants:
│   ├── gnomad.py
│   ├── dbsnp.py
│   ├── clinvar.py
│   ├── gwas_catalog.py
│   ├── disgenet.py
│   └── opentargets.py
├── Translational/Clinical:
│   ├── clinicaltrials.py
│   └── patents.py
└── Population Context:
    ├── genomeasia_loader.py
    ├── indigen_loader.py
    └── igvdb_loader.py
```

### Data Flow Architecture

#### Disease Intelligence Pipeline

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Orchestrator
    participant Connectors
    participant LLM
    participant DB
    participant Cache
    
    User->>API: POST /api/disease/intelligence {"query": "IPEX syndrome"}
    API->>Orchestrator: Create Run (disease.intelligence)
    Orchestrator->>Cache: Check cached results
    Cache-->>Orchestrator: Cache miss
    Orchestrator->>LLM: Normalize disease query
    LLM-->>Orchestrator: {normalized: "IPEX", identifiers: {...}}
    Orchestrator->>Connectors: Query 12 sources in parallel
    Connectors-->>Orchestrator: Aggregated gene candidates
    Orchestrator->>LLM: Detect contradictions
    LLM-->>Orchestrator: Contradiction report
    Orchestrator->>DB: Store disease_query, candidates, evidence
    Orchestrator->>Cache: Cache results (30min TTL)
    Orchestrator->>API: Run complete with artifacts
    API->>User: Disease intelligence results
```

#### Target Prioritization Flow

```mermaid
sequenceDiagram
    participant User
    participant API
    participant Scorer
    participant GNN
    participant DB
    participant Qdrant
    
    User->>API: POST /api/targets/prioritize
    API->>Scorer: Initialize composite scoring
    Scorer->>DB: Fetch candidate genes
    Scorer->>GNN: Calculate pathway centrality
    GNN-->>Scorer: Centrality scores
    Scorer->>DB: Fetch GWAS associations
    Scorer->>DB: Fetch druggability data
    Scorer->>Qdrant: Semantic literature search
    Qdrant-->>Scorer: Literature scores
    Scorer->>Scorer: Compute composite score
    Scorer->>DB: Store target_rankings
    Scorer->>API: Ranked targets with provenance
    API->>User: Target prioritization results
```

### Deployment Architecture

```mermaid
graph TB
    subgraph "Docker Compose Stack"
        subgraph "Application Layer"
            API1[API Server 1]
            API2[API Server 2]
            Worker1[ARQ Worker 1]
            Worker2[ARQ Worker 2]
            Worker3[ARQ Worker 3]
            Web[Nginx + React SPA]
        end
        
        subgraph "Data Layer"
            PG[(PostgreSQL 16)]
            Redis[(Redis 7)]
            Qdrant[(Qdrant v1.9)]
            Neo4j[(Neo4j 5)]
            MinIO[(MinIO S3)]
        end
        
        subgraph "Observability"
            Prometheus[Prometheus]
            Grafana[Grafana]
            Loki[Loki]
        end
        
        subgraph "Gateway"
            NginxLB[Nginx Load Balancer]
        end
    end
    
    Users --> NginxLB
    NginxLB --> API1
    NginxLB --> API2
    NginxLB --> Web
    API1 --> PG
    API2 --> PG
    API1 --> Redis
    API2 --> Redis
    API1 --> Qdrant
    API2 --> Qdrant
    API1 --> Neo4j
    API2 --> Neo4j
    Worker1 --> Redis
    Worker2 --> Redis
    Worker3 --> Redis
    Worker1 --> PG
    Worker2 --> PG
    Worker3 --> PG
    API1 --> MinIO
    API2 --> MinIO
    Worker1 --> MinIO
    Prometheus --> API1
    Prometheus --> API2
    Grafana --> Prometheus
    Grafana --> Loki

## Low-Level Design

### Database Schema Specifications


## Low-Level Design

### Database Schema Specifications


## Low-Level Design

### Database Schema Specifications

#### Core Tables (Wave 1)

**users table:**
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100),
    role VARCHAR(20) DEFAULT 'collaborator',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login TIMESTAMPTZ
);
CREATE INDEX idx_users_email ON users(email);
```

**sessions table:**
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id),
    token_hash TEXT NOT NULL UNIQUE,
    ip_hash TEXT,
    user_agent_hash TEXT,
    client_type TEXT DEFAULT 'browser',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ,
    expires_at TIMESTAMPTZ NOT NULL,
    is_active BOOLEAN DEFAULT TRUE
);
CREATE INDEX idx_sessions_user_id ON sessions(user_id);
```

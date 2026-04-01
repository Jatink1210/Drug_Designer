"""DrugSynth Workbench — FastAPI Application Entry Point."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from middleware.auth import JWTAuthMiddleware

from config import settings
from routers import (
    health,
    search,
    structure,
    docking,
    molecules,
    evidence,
    reports,
    data,
    embeddings,
    graph,
    translational,
    models,
    rl,
    rlm,
    media,
    logs,
    runtimes,
    dossier,
    pathways,
    catalog,
    projects,
    syntharena,
    disease,
    settings as settings_router,
    docs as docs_router,
    auth as auth_router,
)
from routers import security as security_router

structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.dev.ConsoleRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs(settings.local_store_path, exist_ok=True)
    db_dir = os.path.dirname(settings.sqlite_db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
        
    # Initialize GitHub repo integrations (Symphony, Microfish, OpenViking, SSD)
    from agents.symphony_orchestrator import orchestrator
    from services.microfish_analyzer import analyzer as microfish
    from core.viking_pipeline import VikingPipeline
    from core.ssd_retriever import ssd_db
    structlog.get_logger().info("github_repos_integrated", symphony=True, microfish=True, openviking=True, ssd=True)
        
    # Bootstrap multi-tenant user models schema
    from core.db import init_db
    try:
        await init_db()
    except Exception as e:
        structlog.get_logger().error("db_init_failed", error=str(e))

    # Initialize rate limits for known hosts
    from core.http_client import get_rate_limiter
    rl = get_rate_limiter()
    rl.set_limit("rest.uniprot.org", 10.0)
    rl.set_limit("eutils.ncbi.nlm.nih.gov", 3.0)  # NCBI rate limit
    rl.set_limit("www.ebi.ac.uk", 10.0)
    rl.set_limit("clinicaltrials.gov", 5.0)
    rl.set_limit("search.rcsb.org", 10.0)
    rl.set_limit("data.rcsb.org", 10.0)
    rl.set_limit("reactome.org", 5.0)
    rl.set_limit("alphafold.ebi.ac.uk", 5.0)
    rl.set_limit("pubchem.ncbi.nlm.nih.gov", 5.0)
    rl.set_limit("string-db.org", 3.0)
    rl.set_limit("api.patentsview.org", 5.0)
    rl.set_limit("rest.kegg.jp", 5.0)
    rl.set_limit("go.drugbank.com", 3.0)
    rl.set_limit("www.disgenet.org", 3.0)
    rl.set_limit("rest.ensembl.org", 10.0)

    mode_label = f"{settings.dss_mode}/{settings.dss_storage_backend}"
    structlog.get_logger().info(
        "api_started", port=settings.api_port, version="1.0.0", mode=mode_label
    )

    # Initialize graph constraints — only needed for Neo4j (full mode)
    if settings.dss_storage_backend != "embedded" and settings.dss_mode != "workbench":
        from routers.graph import startup_graph_constraints
        try:
            await startup_graph_constraints()
        except Exception:
            pass  # Non-fatal — graph constraints are best-effort

    yield


app = FastAPI(
    title="DrugSynth Workbench API",
    version="1.0.0",
    description="Local-first scientific discovery workbench API — multi-source biomedical search, structure, docking, molecule design, evidence, and reporting platform.",
    lifespan=lifespan,
)

# In workbench (desktop) mode the API only binds to 127.0.0.1 so
# allowing all origins is safe.  We use allow_origin_regex because
# allow_origins=["*"] + allow_credentials=True is silently rejected
# by the CORS spec (and Starlette enforces this).
if settings.dss_mode == "workbench":
    app.add_middleware(
        CORSMiddleware,
        allow_origin_regex=r".*",
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
else:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health.router)
app.include_router(search.router)
app.include_router(structure.router)
app.include_router(docking.router)
app.include_router(molecules.router)
app.include_router(evidence.router)
app.include_router(reports.router)
app.include_router(data.router)
app.include_router(embeddings.router)
app.include_router(graph.router)
app.include_router(translational.router)
app.include_router(models.router)
app.include_router(rl.router)
app.include_router(media.router)
app.include_router(logs.router)
app.include_router(runtimes.router)
app.include_router(settings_router.router)
app.include_router(rlm.router)
app.include_router(dossier.router)
app.include_router(pathways.router)
app.include_router(catalog.router)
app.include_router(projects.router)
app.include_router(syntharena.router)
app.include_router(disease.router)
app.include_router(auth_router.router)
app.include_router(security_router.router)
app.include_router(docs_router.router, tags=["Documentation"])

# Install log secret redaction (Section 16.4)
try:
    from middleware.log_redaction import install_redaction
    install_redaction()
except Exception:
    pass

# Serve Frontend SPA
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

frontend_dist = os.path.join(os.path.dirname(__file__), "..", "web", "dist")
if os.path.isdir(frontend_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    async def serve_frontend(full_path: str):
        # Serve index.html for React Router paths
        path = os.path.join(frontend_dist, full_path)
        if os.path.isfile(path) and not os.path.isdir(path):
            return FileResponse(path)
        return FileResponse(os.path.join(frontend_dist, "index.html"))

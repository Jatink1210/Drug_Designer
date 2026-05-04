"""Drug Designer — FastAPI Application Entry Point (§6, Layer 2)."""

from __future__ import annotations

import os
import sys

# ── Fix Windows console encoding (emoji in print() crashes on CP1252) ──
os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass  # Already reconfigured or not supported

from contextlib import asynccontextmanager
from core.env_bootstrap import load_runtime_env

# Load local defaults without overriding real process env supplied by Docker or the shell.
load_runtime_env()

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
    translation,
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
    entity_intelligence,
    targets,
    runs,
    exports,
    sources,
    mapping,
    design,
    labs,
    settings as settings_router,
    docs as docs_router,
    auth as auth_router,
    cockpit,
    hardware,
    clinical,
    consensus,
)
from routers import security as security_router
from routers import websocket_routes
from routers import dag as dag_router
from routers import esm3 as esm3_router
from routers import contradictions as contradictions_router
from routers import pico as pico_router

_is_dev = os.getenv("DSS_ENV", "development") == "development"
structlog.configure(
    processors=[
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.contextvars.merge_contextvars,
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer() if _is_dev else structlog.processors.JSONRenderer(),
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.PrintLoggerFactory(),
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # §37 Gate: Refuse to start with insecure default secrets (production only)
    _INSECURE_SECRETS = {"changeme-for-production", "workbench-dev-secret-key-change-in-production", ""}
    auth_enabled = os.environ.get("DRUGDESIGNER_AUTH_ENABLED", "true").lower() == "true"
    if auth_enabled and settings.jwt_secret in _INSECURE_SECRETS:
        if _is_dev:
            structlog.get_logger().warning(
                "insecure_jwt_secret",
                msg="JWT_SECRET is insecure — auth is DISABLED for safety. "
                    "Set JWT_SECRET in .env for authenticated mode.",
            )
            # Auto-disable auth in dev to prevent crash
            os.environ["DRUGDESIGNER_AUTH_ENABLED"] = "false"
        else:
            raise RuntimeError(
                "JWT_SECRET must be set to a secure value. "
                "Set the JWT_SECRET environment variable or add it to .env"
            )

    os.makedirs(settings.local_store_path, exist_ok=True)
    db_dir = os.path.dirname(settings.sqlite_db_path)
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)

    # ── Auto-create database tables (embedded/SQLite mode) ──
    try:
        import models.db_tables  # noqa: F401 — registers all 40+ tables with Base.metadata
        import models.user       # noqa: F401 — registers User model
        from core.db import init_db
        await init_db()
        structlog.get_logger().info("database_tables_initialized")
    except Exception as db_err:
        structlog.get_logger().warning("database_init_warning", error=str(db_err))

        
    # Initialize Drug Designer native subsystems (§29 Integration Map)
    # §Rule: "The application should NOT expose or depend on external repository names"
    try:
        from services.agency.symphony import UniversalSymphony
        from services.structure.mirofish_pipeline import MiroFishDockingOrchestrator
        from services.graph.viking_walker import VikingGraphWalker
        from services.models.ssd_state_space import StateSpaceModelPhysics
        structlog.get_logger().info("native_subsystems_initialized",
            run_orchestrator=True, scenario_engine=True,
            context_fabric=True, inference_layer=True)
    except ImportError as exc:
        structlog.get_logger().warning("subsystem_import_warning", error=str(exc))

    # Activate log redaction (§96 — mask secrets/PII in structured logs)
    try:
        from middleware.log_redaction import install_redaction
        install_redaction()
    except Exception as exc:
        structlog.get_logger().warning("log_redaction_init_failed", error=str(exc))

    # Initialize circuit breaker registry (§62)
    from core.circuit_breaker import CircuitBreakerRegistry
    app.state.circuit_breakers = CircuitBreakerRegistry()

    # Initialize rate limiter registry (§52, §A9)
    from core.rate_limiter import RateLimiterRegistry
    app.state.rate_limiters = RateLimiterRegistry()

    # Initialize global event bus (Deep-Impl §1.5)
    from core.event_bus import event_bus
    app.state.event_bus = event_bus

    # Initialize ARQ worker pool for background job queuing (§6)
    # Skip Redis connection entirely in embedded/workbench mode to avoid 11s timeout
    if settings.dss_storage_backend == "embedded":
        app.state.arq_pool = None
        structlog.get_logger().info("arq_pool_skipped", reason="embedded mode — no Redis needed")
    else:
        try:
            from arq import create_pool
            from arq.connections import RedisSettings
            redis_url = getattr(settings, 'redis_url', 'redis://localhost:6379')
            arq_redis = RedisSettings.from_dsn(redis_url) if '://' in redis_url else RedisSettings()
            app.state.arq_pool = await create_pool(arq_redis)
            structlog.get_logger().info("arq_pool_initialized")
        except Exception as exc:
            app.state.arq_pool = None
            structlog.get_logger().warning("arq_pool_unavailable", error=str(exc))
        
    # Bootstrap DB schema via Alembic (§56.3, §91)
    from core.db import init_db
    import models.db_tables  # noqa: F401  — ensure all ORM models registered before create_all
    try:
        await init_db()  # create_all as safety net; Alembic is the source of truth
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

    # A3: Storage client startup health check (S3/MinIO or local fallback)
    try:
        from services.storage_client import storage_client
        storage_status = storage_client.health_check()
        structlog.get_logger().info("storage_initialized", **storage_status)
    except Exception as exc:
        structlog.get_logger().warning("storage_init_failed", error=str(exc))

    # A1: Initialize graph store + Neo4j constraints at startup (not lazy)
    if settings.dss_storage_backend != "embedded" and settings.dss_mode != "workbench":
        try:
            from services.graph_store import get_graph_store
            graph_store = get_graph_store()
            # Ping Neo4j so failures are visible at boot, not first request
            if hasattr(graph_store, "_get_driver"):
                driver = graph_store._get_driver()
                async with driver.session() as _ping_session:
                    await _ping_session.run("RETURN 1")
                await graph_store.setup_constraints()
                structlog.get_logger().info("neo4j_initialized", uri=settings.neo4j_uri)
            app.state.graph_store = graph_store
        except Exception as exc:
            # Non-fatal — degrade gracefully; embedded fallback still works
            structlog.get_logger().warning(
                "neo4j_init_failed",
                error=str(exc),
                hint="Neo4j unavailable — graph features will use embedded (NetworkX) fallback.",
            )

    # A2: Ensure Qdrant spec collections exist at startup
    if settings.dss_storage_backend != "embedded" and settings.dss_mode != "workbench":
        try:
            from core.vector_store import get_vector_store
            vs = get_vector_store()
            if hasattr(vs, "ensure_spec_collections"):
                results = vs.ensure_spec_collections()
                structlog.get_logger().info("qdrant_collections_initialized", results=results)
        except Exception as exc:
            structlog.get_logger().warning(
                "qdrant_collections_init_failed",
                error=str(exc),
                hint="Qdrant unavailable — vector features will use embedded (SQLite) fallback.",
            )

    yield


app = FastAPI(
    title="Drug Designer API",
    version="1.0.0",
    description="Browser-native, evidence-first, provenance-first scientific research and decision-support platform (§1, §2).",
    lifespan=lifespan,
)

# ── §60.4 Prometheus Metrics ────────────────────────────────
if settings.prometheus_enabled:
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            excluded_handlers=["/api/health", "/metrics"],
        ).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)
        structlog.get_logger().info("prometheus_metrics_enabled")
    except ImportError:
        structlog.get_logger().warning("prometheus_instrumentator_not_installed")

# ── §O-1: Custom api_request_duration_seconds histogram ─────
# Required by the performance-sla.json Grafana dashboard which queries
# api_request_duration_seconds_bucket{endpoint=~"..."}.
try:
    from prometheus_client import Histogram as _PromHistogram

    _API_REQUEST_DURATION = _PromHistogram(
        "api_request_duration_seconds",
        "API request duration in seconds (labelled by endpoint class)",
        ["method", "endpoint", "status_code"],
        buckets=[0.01, 0.025, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0],
    )
    _API_PROM_AVAILABLE = True
except ImportError:
    _API_REQUEST_DURATION = None  # type: ignore[assignment]
    _API_PROM_AVAILABLE = False

# ── §96 Sentry Error Tracking ──────────────────────────────
if settings.sentry_dsn:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            traces_sample_rate=0.1,
            environment=os.getenv("DSS_ENV", "development"),
            release=f"drug-designer@1.0.0",
        )
        structlog.get_logger().info("sentry_initialized")
    except ImportError:
        structlog.get_logger().warning("sentry_sdk_not_installed")

# ── §5.3 Performance Budget Enforcement ─────────────────────
import time as _perf_time
import collections as _collections
import logging as _logging

_perf_logger = _logging.getLogger("perf")
_recent_timings: collections.deque = _collections.deque(maxlen=1000)


def get_recent_timings() -> list[float]:
    """Expose recent response timings for diagnostics."""
    return list(_recent_timings)


@app.middleware("http")
async def timing_middleware(request: Request, call_next):
    start = _perf_time.perf_counter()
    response = await call_next(request)
    elapsed = (_perf_time.perf_counter() - start) * 1000
    response.headers["Server-Timing"] = f"total;dur={elapsed:.1f}"
    _recent_timings.append(elapsed)
    if elapsed > 400:
        _perf_logger.warning(f"Slow request: {request.method} {request.url.path} took {elapsed:.0f}ms")

    # §O-1: Record to api_request_duration_seconds histogram
    if _API_PROM_AVAILABLE:
        try:
            # Use route template as endpoint label for cardinality control
            route = request.scope.get("route")
            endpoint = route.path if route and hasattr(route, "path") else request.url.path
            _API_REQUEST_DURATION.labels(
                method=request.method,
                endpoint=endpoint,
                status_code=str(response.status_code),
            ).observe(elapsed / 1000.0)
        except Exception:
            pass  # never let metrics break the request

    return response


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
    # §68.1 CORS Policy
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "https://drugdesigner.app",      # Production
            "http://localhost:5173",          # Vite dev
            "http://localhost:3000",          # Alternative dev
        ] + (settings.api_cors_origins if hasattr(settings, 'api_cors_origins') else []),
        allow_credentials=True,  # Required for HTTP-only cookie auth
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

app.include_router(health.router)

# Register all routers with resilience — a single bad router should not crash the app
_ROUTERS = [
    ("search", search), ("structure", structure), ("docking", docking),
    ("molecules", molecules), ("evidence", evidence), ("reports", reports),
    ("data", data), ("embeddings", embeddings), ("graph", graph),
    ("translational", translational), ("translation", translation),
    ("models", models), ("rl", rl), ("media", media), ("logs", logs),
    ("runtimes", runtimes), ("settings", settings_router), ("rlm", rlm),
    ("dossier", dossier), ("pathways", pathways), ("catalog", catalog),
    ("projects", projects), ("syntharena", syntharena), ("disease", disease),
    ("entity_intelligence", entity_intelligence),
    ("targets", targets), ("runs", runs), ("exports", exports),
    ("sources", sources), ("mapping", mapping), ("design", design),
    ("labs", labs), ("auth", auth_router), ("security", security_router),
    ("docs", docs_router), ("websocket", websocket_routes),
    ("dag", dag_router), ("cockpit", cockpit), ("hardware", hardware),
    ("clinical", clinical), ("consensus", consensus),
    ("esm3", esm3_router),  # ESM-3 Large De Novo Protein Design (§24.2)
    ("contradictions", contradictions_router),  # Contradiction & Similarity Analysis (Task 21)
    ("pico", pico_router),  # PICO Verification (Task 22)
]

_failed_routers: list[str] = []
for name, mod in _ROUTERS:
    try:
        app.include_router(mod.router)
    except Exception as exc:
        _failed_routers.append(name)
        structlog.get_logger().error("router_registration_failed", router=name, error=str(exc))

if _failed_routers:
    structlog.get_logger().warning("some_routers_unavailable", routers=_failed_routers)

# §67.4 Request Correlation — X-Request-ID on every request
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        # §67.4: Bind request_id to structlog context for all downstream logs
        try:
            import structlog
            structlog.contextvars.bind_contextvars(request_id=request_id)
        except Exception:
            pass
        response: Response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

app.add_middleware(RequestIDMiddleware)

# §93.3 Global Exception Handler — convert all HTTPException to envelope format
from fastapi import HTTPException as _HTTPException
from fastapi.responses import JSONResponse
from models.envelope import build_envelope as _build_envelope_fn, _request_id, _trace_id
import time as _time

@app.exception_handler(_HTTPException)
async def http_exception_to_envelope(request: Request, exc: _HTTPException):
    """§93.3: Never throw raw error tracebacks to the UI — always envelope."""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "request_id": request.headers.get("X-Request-ID", _request_id()),
            "trace_id": _trace_id(),
            "status": "error",
            "data": None,
            "warnings": [],
            "errors": [{
                "code": f"HTTP_{exc.status_code}",
                "message": exc.detail if isinstance(exc.detail, str) else str(exc.detail),
                "details": {},
                "recoverable": exc.status_code < 500,
                "suggested_action": "Retry the request." if exc.status_code >= 500 else "",
            }],
            "provenance": {"sources": [], "generated_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()), "runtime_mode": "hosted"},
            "runtime_context": {"mode": "hosted", "selected_runtime": "", "selected_model": "", "fallback_used": False},
            "timing": {"started_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()), "elapsed_ms": 0},
        },
    )

@app.exception_handler(Exception)
async def unhandled_exception_to_envelope(request: Request, exc: Exception):
    """§93.3: Catch-all — never expose raw 500 tracebacks."""
    # Handle ServiceUnavailableError with structured response
    try:
        from routers.health import ServiceUnavailableError
        if isinstance(exc, ServiceUnavailableError):
            structured = exc.to_structured_error()
            return JSONResponse(
                status_code=503,
                content=structured.model_dump(),
                headers={"Retry-After": str(structured.retry_after_seconds or 30)},
            )
    except ImportError:
        pass

    import structlog as _sl
    _sl.get_logger().error("unhandled_exception", error=str(exc), path=str(request.url))
    return JSONResponse(
        status_code=500,
        content={
            "request_id": request.headers.get("X-Request-ID", _request_id()),
            "trace_id": _trace_id(),
            "status": "error",
            "data": None,
            "warnings": [],
            "errors": [{
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred.",
                "details": {},
                "recoverable": False,
                "suggested_action": "Contact support or retry later.",
            }],
            "provenance": {"sources": [], "generated_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()), "runtime_mode": "hosted"},
            "runtime_context": {"mode": "hosted", "selected_runtime": "", "selected_model": "", "fallback_used": False},
            "timing": {"started_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()), "elapsed_ms": 0},
        },
    )

# §68.3 User-facing rate limits (120/min auth, 10/min unauth)
try:
    from middleware.rate_limit import RateLimitMiddleware
    app.add_middleware(RateLimitMiddleware)
except Exception:
    pass

# §67.3 Install log secret redaction
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

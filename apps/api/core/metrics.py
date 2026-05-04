"""Prometheus Metrics Collection for All Subsystems (NFR-MAIN-002).

Custom metrics for:
- API latency
- Connector performance
- Database query performance
- Model inference performance
"""

from __future__ import annotations

from typing import Dict, Any, Optional
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    Summary,
    CollectorRegistry,
    generate_latest,
    CONTENT_TYPE_LATEST,
)
import structlog
import time

log = structlog.get_logger(__name__)

# Create custom registry
registry = CollectorRegistry()

# ═══════════════════════════════════════════════════════════════
# API Metrics
# ═══════════════════════════════════════════════════════════════

# API request counter
api_requests_total = Counter(
    'api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status'],
    registry=registry
)

# API request duration
api_request_duration_seconds = Histogram(
    'api_request_duration_seconds',
    'API request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0),
    registry=registry
)

# API request size
api_request_size_bytes = Summary(
    'api_request_size_bytes',
    'API request size in bytes',
    ['method', 'endpoint'],
    registry=registry
)

# API response size
api_response_size_bytes = Summary(
    'api_response_size_bytes',
    'API response size in bytes',
    ['method', 'endpoint'],
    registry=registry
)

# Active requests
api_requests_in_progress = Gauge(
    'api_requests_in_progress',
    'Number of API requests in progress',
    ['method', 'endpoint'],
    registry=registry
)

# ═══════════════════════════════════════════════════════════════
# Connector Metrics
# ═══════════════════════════════════════════════════════════════

# Connector request counter
connector_requests_total = Counter(
    'connector_requests_total',
    'Total connector requests',
    ['connector', 'status'],
    registry=registry
)

# Connector request duration
connector_request_duration_seconds = Histogram(
    'connector_request_duration_seconds',
    'Connector request duration in seconds',
    ['connector'],
    buckets=(0.1, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 30.0),
    registry=registry
)

# Connector errors
connector_errors_total = Counter(
    'connector_errors_total',
    'Total connector errors',
    ['connector', 'error_type'],
    registry=registry
)

# Circuit breaker state
connector_circuit_breaker_state = Gauge(
    'connector_circuit_breaker_state',
    'Circuit breaker state (0=closed, 1=open, 2=half_open)',
    ['connector'],
    registry=registry
)

# Connector cache hits
connector_cache_hits_total = Counter(
    'connector_cache_hits_total',
    'Total connector cache hits',
    ['connector'],
    registry=registry
)

# Connector cache misses
connector_cache_misses_total = Counter(
    'connector_cache_misses_total',
    'Total connector cache misses',
    ['connector'],
    registry=registry
)

# ═══════════════════════════════════════════════════════════════
# Database Metrics
# ═══════════════════════════════════════════════════════════════

# Database query counter
db_queries_total = Counter(
    'db_queries_total',
    'Total database queries',
    ['operation', 'table'],
    registry=registry
)

# Database query duration
db_query_duration_seconds = Histogram(
    'db_query_duration_seconds',
    'Database query duration in seconds',
    ['operation', 'table'],
    buckets=(0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0),
    registry=registry
)

# Database connection pool
db_connection_pool_size = Gauge(
    'db_connection_pool_size',
    'Database connection pool size',
    registry=registry
)

# Database connection pool usage
db_connection_pool_usage = Gauge(
    'db_connection_pool_usage',
    'Database connection pool usage',
    registry=registry
)

# Database errors
db_errors_total = Counter(
    'db_errors_total',
    'Total database errors',
    ['operation', 'error_type'],
    registry=registry
)

# ═══════════════════════════════════════════════════════════════
# Model Inference Metrics
# ═══════════════════════════════════════════════════════════════

# Model inference counter
model_inference_total = Counter(
    'model_inference_total',
    'Total model inferences',
    ['model_name', 'model_type'],
    registry=registry
)

# Model inference duration
model_inference_duration_seconds = Histogram(
    'model_inference_duration_seconds',
    'Model inference duration in seconds',
    ['model_name', 'model_type'],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0),
    registry=registry
)

# Model memory usage
model_memory_usage_bytes = Gauge(
    'model_memory_usage_bytes',
    'Model memory usage in bytes',
    ['model_name'],
    registry=registry
)

# Model batch size
model_batch_size = Histogram(
    'model_batch_size',
    'Model batch size',
    ['model_name'],
    buckets=(1, 5, 10, 20, 50, 100, 200, 500),
    registry=registry
)

# Model errors
model_errors_total = Counter(
    'model_errors_total',
    'Total model errors',
    ['model_name', 'error_type'],
    registry=registry
)

# ═══════════════════════════════════════════════════════════════
# Clinical Workflow Metrics
# ═══════════════════════════════════════════════════════════════

# Clinical workflow stage counter
clinical_workflow_stages_total = Counter(
    'clinical_workflow_stages_total',
    'Total clinical workflow stages completed',
    ['stage', 'status'],
    registry=registry
)

# Clinical workflow stage duration
clinical_workflow_stage_duration_seconds = Histogram(
    'clinical_workflow_stage_duration_seconds',
    'Clinical workflow stage duration in seconds',
    ['stage'],
    buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0),
    registry=registry
)

# ═══════════════════════════════════════════════════════════════
# WebSocket Metrics
# ═══════════════════════════════════════════════════════════════

# WebSocket connections
websocket_connections_active = Gauge(
    'websocket_connections_active',
    'Number of active WebSocket connections',
    registry=registry
)

# WebSocket messages sent
websocket_messages_sent_total = Counter(
    'websocket_messages_sent_total',
    'Total WebSocket messages sent',
    ['message_type'],
    registry=registry
)

# WebSocket messages received
websocket_messages_received_total = Counter(
    'websocket_messages_received_total',
    'Total WebSocket messages received',
    ['message_type'],
    registry=registry
)

# ═══════════════════════════════════════════════════════════════
# Cache Metrics
# ═══════════════════════════════════════════════════════════════

# Cache hits
cache_hits_total = Counter(
    'cache_hits_total',
    'Total cache hits',
    ['cache_name'],
    registry=registry
)

# Cache misses
cache_misses_total = Counter(
    'cache_misses_total',
    'Total cache misses',
    ['cache_name'],
    registry=registry
)

# Cache size
cache_size_bytes = Gauge(
    'cache_size_bytes',
    'Cache size in bytes',
    ['cache_name'],
    registry=registry
)

# Cache evictions
cache_evictions_total = Counter(
    'cache_evictions_total',
    'Total cache evictions',
    ['cache_name'],
    registry=registry
)

# ═══════════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════════

class MetricsCollector:
    """Helper class for collecting metrics."""
    
    @staticmethod
    def track_api_request(method: str, endpoint: str, status: int, duration: float):
        """Track API request metrics."""
        api_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        api_request_duration_seconds.labels(method=method, endpoint=endpoint).observe(duration)
    
    @staticmethod
    def track_connector_request(connector: str, status: str, duration: float):
        """Track connector request metrics."""
        connector_requests_total.labels(connector=connector, status=status).inc()
        connector_request_duration_seconds.labels(connector=connector).observe(duration)
    
    @staticmethod
    def track_connector_error(connector: str, error_type: str):
        """Track connector error."""
        connector_errors_total.labels(connector=connector, error_type=error_type).inc()
    
    @staticmethod
    def track_db_query(operation: str, table: str, duration: float):
        """Track database query metrics."""
        db_queries_total.labels(operation=operation, table=table).inc()
        db_query_duration_seconds.labels(operation=operation, table=table).observe(duration)
    
    @staticmethod
    def track_model_inference(model_name: str, model_type: str, duration: float, batch_size: int = 1):
        """Track model inference metrics."""
        model_inference_total.labels(model_name=model_name, model_type=model_type).inc()
        model_inference_duration_seconds.labels(model_name=model_name, model_type=model_type).observe(duration)
        model_batch_size.labels(model_name=model_name).observe(batch_size)
    
    @staticmethod
    def track_clinical_workflow_stage(stage: str, status: str, duration: float):
        """Track clinical workflow stage metrics."""
        clinical_workflow_stages_total.labels(stage=stage, status=status).inc()
        clinical_workflow_stage_duration_seconds.labels(stage=stage).observe(duration)
    
    @staticmethod
    def set_circuit_breaker_state(connector: str, state: str):
        """Set circuit breaker state."""
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state, 0)
        connector_circuit_breaker_state.labels(connector=connector).set(state_value)
    
    @staticmethod
    def track_cache_hit(cache_name: str):
        """Track cache hit."""
        cache_hits_total.labels(cache_name=cache_name).inc()
    
    @staticmethod
    def track_cache_miss(cache_name: str):
        """Track cache miss."""
        cache_misses_total.labels(cache_name=cache_name).inc()


def get_metrics() -> bytes:
    """Get Prometheus metrics in text format."""
    return generate_latest(registry)


def get_metrics_content_type() -> str:
    """Get Prometheus metrics content type."""
    return CONTENT_TYPE_LATEST


# Initialize metrics collector
metrics_collector = MetricsCollector()


# Context manager for tracking request duration
class track_duration:
    """Context manager for tracking operation duration."""
    
    def __init__(self, metric_func, *args, **kwargs):
        self.metric_func = metric_func
        self.args = args
        self.kwargs = kwargs
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        self.metric_func(*self.args, duration=duration, **self.kwargs)
        return False


log.info("prometheus_metrics_initialized")

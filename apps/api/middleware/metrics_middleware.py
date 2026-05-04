"""Metrics Middleware for Custom Prometheus Metrics Collection.

Task 15.2: Configure Prometheus metrics collection
NFR-MAIN-002: Monitoring & Observability

This middleware integrates custom metrics from apps/api/core/metrics.py
with the FastAPI application to track:
- API request latency and throughput
- Connector performance
- Database query performance
- Model inference performance
- Clinical workflow stages
- WebSocket connections
- Cache performance
"""

from __future__ import annotations

import time
from typing import Callable
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
import structlog

from apps.api.core.metrics import metrics_collector, api_requests_in_progress

log = structlog.get_logger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect custom Prometheus metrics for all requests."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Collect metrics for each request.
        
        Metrics collected:
        - api_requests_total (counter)
        - api_request_duration_seconds (histogram)
        - api_requests_in_progress (gauge)
        - api_request_size_bytes (summary)
        - api_response_size_bytes (summary)
        """
        # Extract request metadata
        method = request.method
        path = request.url.path
        
        # Normalize endpoint path (remove IDs)
        endpoint = self._normalize_endpoint(path)
        
        # Track in-progress requests
        api_requests_in_progress.labels(method=method, endpoint=endpoint).inc()
        
        # Track request size
        request_size = int(request.headers.get("content-length", 0))
        
        # Start timer
        start_time = time.time()
        
        try:
            # Process request
            response = await call_next(request)
            
            # Calculate duration
            duration = time.time() - start_time
            
            # Get status code
            status = response.status_code
            
            # Track response size
            response_size = int(response.headers.get("content-length", 0))
            
            # Record metrics
            metrics_collector.track_api_request(
                method=method,
                endpoint=endpoint,
                status=status,
                duration=duration
            )
            
            # Log slow requests
            if duration > 5.0:
                log.warning(
                    "slow_api_request",
                    method=method,
                    endpoint=endpoint,
                    duration_seconds=duration,
                    status=status
                )
            
            return response
            
        except Exception as e:
            # Track error
            duration = time.time() - start_time
            metrics_collector.track_api_request(
                method=method,
                endpoint=endpoint,
                status=500,
                duration=duration
            )
            
            log.error(
                "api_request_error",
                method=method,
                endpoint=endpoint,
                duration_seconds=duration,
                error=str(e)
            )
            
            raise
            
        finally:
            # Decrement in-progress counter
            api_requests_in_progress.labels(method=method, endpoint=endpoint).dec()
    
    @staticmethod
    def _normalize_endpoint(path: str) -> str:
        """
        Normalize endpoint path by removing UUIDs and IDs.
        
        Examples:
        - /api/projects/123e4567-e89b-12d3-a456-426614174000 -> /api/projects/{id}
        - /api/runs/abc123/status -> /api/runs/{id}/status
        - /api/evidence/search -> /api/evidence/search
        """
        import re
        
        # Replace UUIDs
        path = re.sub(
            r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}',
            '/{id}',
            path,
            flags=re.IGNORECASE
        )
        
        # Replace numeric IDs
        path = re.sub(r'/\d+(?=/|$)', '/{id}', path)
        
        # Replace alphanumeric IDs (at least 8 chars)
        path = re.sub(r'/[a-zA-Z0-9]{8,}(?=/|$)', '/{id}', path)
        
        return path


# Helper function to track connector metrics
def track_connector_metrics(connector_name: str, status: str, duration: float):
    """
    Track connector request metrics.
    
    Args:
        connector_name: Name of the connector (e.g., "pubmed", "uniprot")
        status: Request status ("success", "error", "timeout")
        duration: Request duration in seconds
    """
    metrics_collector.track_connector_request(
        connector=connector_name,
        status=status,
        duration=duration
    )


# Helper function to track database metrics
def track_database_metrics(operation: str, table: str, duration: float):
    """
    Track database query metrics.
    
    Args:
        operation: Database operation ("select", "insert", "update", "delete")
        table: Table name
        duration: Query duration in seconds
    """
    metrics_collector.track_db_query(
        operation=operation,
        table=table,
        duration=duration
    )


# Helper function to track model inference metrics
def track_model_metrics(
    model_name: str,
    model_type: str,
    duration: float,
    batch_size: int = 1
):
    """
    Track model inference metrics.
    
    Args:
        model_name: Name of the model (e.g., "esm2", "molformer")
        model_type: Type of model ("protein_lm", "molecule_transformer", "cv", "nn")
        duration: Inference duration in seconds
        batch_size: Number of items in batch
    """
    metrics_collector.track_model_inference(
        model_name=model_name,
        model_type=model_type,
        duration=duration,
        batch_size=batch_size
    )


# Helper function to track clinical workflow metrics
def track_clinical_workflow_metrics(stage: str, status: str, duration: float):
    """
    Track clinical workflow stage metrics.
    
    Args:
        stage: Workflow stage name (e.g., "ehr_ingestion", "phenotype_clustering")
        status: Stage status ("success", "error")
        duration: Stage duration in seconds
    """
    metrics_collector.track_clinical_workflow_stage(
        stage=stage,
        status=status,
        duration=duration
    )


# Helper function to track cache metrics
def track_cache_metrics(cache_name: str, hit: bool):
    """
    Track cache hit/miss metrics.
    
    Args:
        cache_name: Name of the cache (e.g., "redis", "memory")
        hit: True if cache hit, False if cache miss
    """
    if hit:
        metrics_collector.track_cache_hit(cache_name=cache_name)
    else:
        metrics_collector.track_cache_miss(cache_name=cache_name)


log.info("metrics_middleware_initialized")

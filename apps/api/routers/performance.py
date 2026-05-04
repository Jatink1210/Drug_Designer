"""Performance monitoring and dashboard endpoints (FR-PERF-004)."""

from __future__ import annotations

from typing import Dict, Any
from fastapi import APIRouter, HTTPException
import structlog

from core.http_client import get_performance_metrics, reset_performance_metrics
from core.circuit_breaker import get_circuit_breaker_registry

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/performance", tags=["performance"])


@router.get("/metrics")
async def get_metrics() -> Dict[str, Any]:
    """
    Get performance metrics for all connectors.
    
    Returns:
        Performance metrics including latency percentiles and error rates
    """
    try:
        metrics = get_performance_metrics()
        
        # Calculate overall statistics
        total_requests = sum(m["total_requests"] for m in metrics.values())
        total_errors = sum(m["total_errors"] for m in metrics.values())
        
        overall_error_rate = round(
            total_errors / max(total_requests, 1) * 100, 2
        )
        
        # Calculate SLA compliance (p95 < 3000ms target)
        sla_compliant_hosts = sum(
            1 for m in metrics.values()
            if m["p95_latency_ms"] < 3000
        )
        
        sla_compliance_rate = round(
            sla_compliant_hosts / max(len(metrics), 1) * 100, 2
        )
        
        return {
            "overall": {
                "total_requests": total_requests,
                "total_errors": total_errors,
                "error_rate_pct": overall_error_rate,
                "sla_compliance_rate_pct": sla_compliance_rate,
                "monitored_hosts": len(metrics),
            },
            "by_host": metrics,
        }
    
    except Exception as e:
        log.error("failed_to_get_metrics", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/circuit-breaker")
async def get_circuit_breaker_status() -> Dict[str, Any]:
    """
    Get circuit breaker status for all hosts.
    
    Returns:
        Circuit breaker status including open/closed state and failure counts
    """
    try:
        registry = get_circuit_breaker_registry()
        
        # Get all health diagnostics
        all_health = registry.get_all_health()
        
        # Get summary
        summary = registry.get_summary()
        
        return {
            "summary": summary,
            "breakers": all_health,
        }
    
    except Exception as e:
        log.error("failed_to_get_circuit_breaker_status", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metrics/reset")
async def reset_metrics() -> Dict[str, str]:
    """
    Reset performance metrics.
    
    Returns:
        Success message
    """
    try:
        reset_performance_metrics()
        
        log.info("performance_metrics_reset_via_api")
        
        return {"status": "success", "message": "Performance metrics reset"}
    
    except Exception as e:
        log.error("failed_to_reset_metrics", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/dashboard")
async def get_dashboard() -> Dict[str, Any]:
    """
    Get comprehensive performance dashboard data.
    
    Returns:
        Dashboard data including metrics, circuit breaker status, and SLA compliance
    """
    try:
        metrics = get_performance_metrics()
        registry = get_circuit_breaker_registry()
        
        # Identify slow hosts (p95 > 3000ms)
        slow_hosts = [
            {
                "host": host,
                "p95_latency_ms": m["p95_latency_ms"],
                "error_rate": m["error_rate"],
            }
            for host, m in metrics.items()
            if m["p95_latency_ms"] > 3000
        ]
        
        # Identify high error rate hosts (>5%)
        error_prone_hosts = [
            {
                "host": host,
                "error_rate": m["error_rate"],
                "total_errors": m["total_errors"],
            }
            for host, m in metrics.items()
            if m["error_rate"] > 5.0
        ]
        
        # Circuit breaker summary
        cb_summary = registry.get_summary()
        
        return {
            "summary": {
                "total_hosts": len(metrics),
                "slow_hosts": len(slow_hosts),
                "error_prone_hosts": len(error_prone_hosts),
                "open_circuits": cb_summary.get("open", 0),
                "half_open_circuits": cb_summary.get("half_open", 0),
            },
            "slow_hosts": slow_hosts,
            "error_prone_hosts": error_prone_hosts,
            "circuit_breaker_summary": cb_summary,
            "sla_targets": {
                "p95_latency_ms": 3000,
                "error_rate_pct": 5.0,
            },
        }
    
    except Exception as e:
        log.error("failed_to_get_dashboard", error=str(e))
        raise HTTPException(status_code=500, detail=str(e))

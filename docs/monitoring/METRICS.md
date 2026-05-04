# Drug Designer - Prometheus Metrics Reference

## Overview

This document describes all Prometheus metrics collected by the Drug Designer platform. These metrics are used by Grafana dashboards for monitoring system health, performance SLAs, and operational metrics.

**Task**: 15.2 Configure Prometheus metrics collection  
**Priority**: P2  
**Requirements**: NFR-MAIN-002 (Monitoring & Observability)

## Metrics Endpoint

**URL**: `http://api:8000/metrics`  
**Format**: Prometheus text format  
**Scrape Interval**: 15 seconds (configured in `monitoring/prometheus/prometheus.yml`)

## Metric Categories

### 1. API Metrics

#### `api_requests_total`
**Type**: Counter  
**Labels**: `method`, `endpoint`, `status`  
**Description**: Total number of API requests  
**Usage**: Track request volume and error rates

```promql
# Request rate by endpoint
rate(api_requests_total[5m])

# Error rate
rate(api_requests_total{status=~"5.."}[5m]) / rate(api_requests_total[5m])
```

#### `api_request_duration_seconds`
**Type**: Histogram  
**Labels**: `method`, `endpoint`  
**Buckets**: 0.01, 0.05, 0.1, 0.5, 1.0, 2.5, 5.0, 10.0  
**Description**: API request duration in seconds  
**Usage**: Track latency and SLA compliance

```promql
# p95 latency by endpoint
histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m]))

# SLA compliance (% of requests < 2s)
sum(rate(api_request_duration_seconds_bucket{le="2"}[5m])) / sum(rate(api_request_duration_seconds_count[5m]))
```

#### `api_request_size_bytes`
**Type**: Summary  
**Labels**: `method`, `endpoint`  
**Description**: API request size in bytes  
**Usage**: Track request payload sizes

#### `api_response_size_bytes`
**Type**: Summary  
**Labels**: `method`, `endpoint`  
**Description**: API response size in bytes  
**Usage**: Track response payload sizes

#### `api_requests_in_progress`
**Type**: Gauge  
**Labels**: `method`, `endpoint`  
**Description**: Number of API requests currently in progress  
**Usage**: Track concurrent request load

```promql
# Current in-progress requests
api_requests_in_progress

# Peak concurrent requests
max_over_time(api_requests_in_progress[1h])
```

---

### 2. Connector Metrics

#### `connector_requests_total`
**Type**: Counter  
**Labels**: `connector`, `status`  
**Description**: Total connector requests  
**Usage**: Track connector usage and success rates

```promql
# Connector request rate
rate(connector_requests_total[5m])

# Connector success rate
rate(connector_requests_total{status="success"}[5m]) / rate(connector_requests_total[5m])
```

#### `connector_request_duration_seconds`
**Type**: Histogram  
**Labels**: `connector`  
**Buckets**: 0.1, 0.5, 1.0, 2.0, 3.0, 5.0, 10.0, 30.0  
**Description**: Connector request duration in seconds  
**Usage**: Track connector latency and SLA compliance

```promql
# p95 connector latency
histogram_quantile(0.95, rate(connector_request_duration_seconds_bucket[5m]))

# Slow connectors (>10s)
histogram_quantile(0.95, rate(connector_request_duration_seconds_bucket[5m])) > 10
```

#### `connector_errors_total`
**Type**: Counter  
**Labels**: `connector`, `error_type`  
**Description**: Total connector errors  
**Usage**: Track connector failures by error type

```promql
# Connector error rate
rate(connector_errors_total[5m])

# Errors by type
sum(rate(connector_errors_total[5m])) by (error_type)
```

#### `connector_circuit_breaker_state`
**Type**: Gauge  
**Labels**: `connector`  
**Values**: 0 (closed), 1 (open), 2 (half_open)  
**Description**: Circuit breaker state for each connector  
**Usage**: Monitor circuit breaker activations

```promql
# Open circuit breakers
connector_circuit_breaker_state == 1

# Count of open circuit breakers
count(connector_circuit_breaker_state == 1)
```

#### `connector_cache_hits_total`
**Type**: Counter  
**Labels**: `connector`  
**Description**: Total connector cache hits  
**Usage**: Track cache effectiveness

```promql
# Cache hit rate
rate(connector_cache_hits_total[5m]) / (rate(connector_cache_hits_total[5m]) + rate(connector_cache_misses_total[5m]))
```

#### `connector_cache_misses_total`
**Type**: Counter  
**Labels**: `connector`  
**Description**: Total connector cache misses  
**Usage**: Track cache effectiveness

---

### 3. Database Metrics

#### `db_queries_total`
**Type**: Counter  
**Labels**: `operation`, `table`  
**Description**: Total database queries  
**Usage**: Track database query volume

```promql
# Query rate by operation
rate(db_queries_total[5m])

# Queries by table
sum(rate(db_queries_total[5m])) by (table)
```

#### `db_query_duration_seconds`
**Type**: Histogram  
**Labels**: `operation`, `table`  
**Buckets**: 0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 5.0  
**Description**: Database query duration in seconds  
**Usage**: Track query performance

```promql
# p95 query latency
histogram_quantile(0.95, rate(db_query_duration_seconds_bucket[5m]))

# Slow queries (>1s)
histogram_quantile(0.95, rate(db_query_duration_seconds_bucket[5m])) > 1
```

#### `db_connection_pool_size`
**Type**: Gauge  
**Description**: Database connection pool size  
**Usage**: Monitor connection pool configuration

#### `db_connection_pool_usage`
**Type**: Gauge  
**Description**: Database connection pool usage (active connections)  
**Usage**: Monitor connection pool utilization

```promql
# Connection pool utilization %
(db_connection_pool_usage / db_connection_pool_size) * 100

# Connection pool near exhaustion (>90%)
(db_connection_pool_usage / db_connection_pool_size) > 0.9
```

#### `db_errors_total`
**Type**: Counter  
**Labels**: `operation`, `error_type`  
**Description**: Total database errors  
**Usage**: Track database failures

```promql
# Database error rate
rate(db_errors_total[5m])

# Errors by type
sum(rate(db_errors_total[5m])) by (error_type)
```

---

### 4. Model Inference Metrics

#### `model_inference_total`
**Type**: Counter  
**Labels**: `model_name`, `model_type`  
**Description**: Total model inferences  
**Usage**: Track model usage

```promql
# Inference rate by model
rate(model_inference_total[5m])

# Total inferences by model type
sum(model_inference_total) by (model_type)
```

#### `model_inference_duration_seconds`
**Type**: Histogram  
**Labels**: `model_name`, `model_type`  
**Buckets**: 0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0  
**Description**: Model inference duration in seconds  
**Usage**: Track inference performance

```promql
# p95 inference latency
histogram_quantile(0.95, rate(model_inference_duration_seconds_bucket[5m]))

# Slow inferences (>60s)
histogram_quantile(0.95, rate(model_inference_duration_seconds_bucket[5m])) > 60
```

#### `model_memory_usage_bytes`
**Type**: Gauge  
**Labels**: `model_name`  
**Description**: Model memory usage in bytes  
**Usage**: Monitor model memory consumption

```promql
# Memory usage by model
model_memory_usage_bytes

# High memory usage (>16GB)
model_memory_usage_bytes > 16000000000
```

#### `model_batch_size`
**Type**: Histogram  
**Labels**: `model_name`  
**Buckets**: 1, 5, 10, 20, 50, 100, 200, 500  
**Description**: Model batch size  
**Usage**: Track batch size distribution

```promql
# Median batch size
histogram_quantile(0.5, rate(model_batch_size_bucket[5m]))
```

#### `model_errors_total`
**Type**: Counter  
**Labels**: `model_name`, `error_type`  
**Description**: Total model errors  
**Usage**: Track model failures

```promql
# Model error rate
rate(model_errors_total[5m])

# Errors by model
sum(rate(model_errors_total[5m])) by (model_name)
```

---

### 5. Clinical Workflow Metrics

#### `clinical_workflow_stages_total`
**Type**: Counter  
**Labels**: `stage`, `status`  
**Description**: Total clinical workflow stages completed  
**Usage**: Track workflow stage completion

```promql
# Stage completion rate
rate(clinical_workflow_stages_total{status="success"}[5m])

# Stage error rate
rate(clinical_workflow_stages_total{status="error"}[5m]) / rate(clinical_workflow_stages_total[5m])
```

#### `clinical_workflow_stage_duration_seconds`
**Type**: Histogram  
**Labels**: `stage`  
**Buckets**: 1.0, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0  
**Description**: Clinical workflow stage duration in seconds  
**Usage**: Track stage performance and SLA compliance

```promql
# p95 stage latency
histogram_quantile(0.95, rate(clinical_workflow_stage_duration_seconds_bucket[5m]))

# SLA compliance by stage
sum(rate(clinical_workflow_stage_duration_seconds_bucket{stage="ehr_ingestion",le="5"}[5m])) / sum(rate(clinical_workflow_stage_duration_seconds_count{stage="ehr_ingestion"}[5m]))
```

**Stages**:
- `ehr_ingestion` (SLA: <5s)
- `phenotype_clustering` (SLA: <30s)
- `tissue_analysis` (SLA: <120s)
- `biomarker_quantification` (SLA: <30s)
- `genomic_sequencing` (SLA: <600s)
- `pathogenicity_prediction` (SLA: <60s)
- `knowledge_graph` (SLA: <0.5s)
- `disruption_modeling` (SLA: <30s)
- `drug_matching` (SLA: <30s)
- `therapy_stratification` (SLA: <10s)

---

### 6. WebSocket Metrics

#### `websocket_connections_active`
**Type**: Gauge  
**Description**: Number of active WebSocket connections  
**Usage**: Monitor WebSocket connection count

```promql
# Current active connections
websocket_connections_active

# High connection count (>1000)
websocket_connections_active > 1000
```

#### `websocket_messages_sent_total`
**Type**: Counter  
**Labels**: `message_type`  
**Description**: Total WebSocket messages sent  
**Usage**: Track WebSocket message volume

```promql
# Message send rate
rate(websocket_messages_sent_total[5m])

# Messages by type
sum(rate(websocket_messages_sent_total[5m])) by (message_type)
```

#### `websocket_messages_received_total`
**Type**: Counter  
**Labels**: `message_type`  
**Description**: Total WebSocket messages received  
**Usage**: Track WebSocket message volume

---

### 7. Cache Metrics

#### `cache_hits_total`
**Type**: Counter  
**Labels**: `cache_name`  
**Description**: Total cache hits  
**Usage**: Track cache effectiveness

```promql
# Cache hit rate
rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))

# Low cache hit rate (<50%)
(rate(cache_hits_total[5m]) / (rate(cache_hits_total[5m]) + rate(cache_misses_total[5m]))) < 0.5
```

#### `cache_misses_total`
**Type**: Counter  
**Labels**: `cache_name`  
**Description**: Total cache misses  
**Usage**: Track cache effectiveness

#### `cache_size_bytes`
**Type**: Gauge  
**Labels**: `cache_name`  
**Description**: Cache size in bytes  
**Usage**: Monitor cache memory usage

#### `cache_evictions_total`
**Type**: Counter  
**Labels**: `cache_name`  
**Description**: Total cache evictions  
**Usage**: Track cache pressure

```promql
# Cache eviction rate
rate(cache_evictions_total[5m])
```

---

## Usage Examples

### SLA Monitoring

```promql
# API endpoints meeting <2s SLA
(sum(rate(api_request_duration_seconds_bucket{endpoint=~"/api/evidence.*",le="2"}[5m])) / sum(rate(api_request_duration_seconds_count{endpoint=~"/api/evidence.*"}[5m]))) * 100

# Clinical workflow stages meeting SLA
(sum(rate(clinical_workflow_stage_duration_seconds_bucket{stage="ehr_ingestion",le="5"}[5m])) / sum(rate(clinical_workflow_stage_duration_seconds_count{stage="ehr_ingestion"}[5m]))) * 100
```

### Error Monitoring

```promql
# API error rate
(sum(rate(api_requests_total{status=~"5.."}[5m])) / sum(rate(api_requests_total[5m]))) * 100

# Connector error rate
(sum(rate(connector_requests_total{status!="success"}[5m])) / sum(rate(connector_requests_total[5m]))) * 100
```

### Performance Monitoring

```promql
# Top 10 slowest endpoints
topk(10, histogram_quantile(0.95, rate(api_request_duration_seconds_bucket[5m])))

# Top 10 slowest connectors
topk(10, histogram_quantile(0.95, rate(connector_request_duration_seconds_bucket[5m])))

# Top 10 slowest database queries
topk(10, histogram_quantile(0.95, rate(db_query_duration_seconds_bucket[5m])))
```

### Resource Monitoring

```promql
# Memory usage
process_resident_memory_bytes{job="drug-designer-api"}

# CPU usage
rate(process_cpu_seconds_total{job="drug-designer-api"}[5m]) * 100

# Database connection pool utilization
(db_connection_pool_usage / db_connection_pool_size) * 100
```

---

## Integration

### Middleware Integration

The `MetricsMiddleware` in `apps/api/middleware/metrics_middleware.py` automatically collects API metrics for all requests.

To enable:

```python
from apps.api.middleware.metrics_middleware import MetricsMiddleware

app.add_middleware(MetricsMiddleware)
```

### Manual Metric Collection

For custom metrics collection:

```python
from apps/api.middleware.metrics_middleware import (
    track_connector_metrics,
    track_database_metrics,
    track_model_metrics,
    track_clinical_workflow_metrics,
    track_cache_metrics
)

# Track connector request
track_connector_metrics("pubmed", "success", 1.5)

# Track database query
track_database_metrics("select", "projects", 0.05)

# Track model inference
track_model_metrics("esm2", "protein_lm", 2.3, batch_size=10)

# Track clinical workflow stage
track_clinical_workflow_metrics("ehr_ingestion", "success", 3.2)

# Track cache hit
track_cache_metrics("redis", hit=True)
```

---

## Best Practices

1. **Use Labels Wisely**: Keep cardinality low (< 1000 unique label combinations)
2. **Normalize Endpoints**: Remove IDs from endpoint labels to reduce cardinality
3. **Set Appropriate Buckets**: Histogram buckets should cover expected value ranges
4. **Monitor Cardinality**: Use `prometheus_tsdb_symbol_table_size_bytes` to track
5. **Use Recording Rules**: Pre-compute expensive queries for dashboards
6. **Set Retention**: Configure appropriate retention period (default: 15 days)

---

## Troubleshooting

### High Cardinality

If metrics have too many unique label combinations:
- Normalize endpoint paths (remove IDs)
- Limit connector names to family groups
- Aggregate table names by category

### Missing Metrics

If metrics are not appearing:
- Check `/metrics` endpoint is accessible
- Verify Prometheus is scraping (check `/targets`)
- Ensure metric names match exactly
- Check for label mismatches

### Slow Queries

If Prometheus queries are slow:
- Use recording rules for complex queries
- Reduce time range
- Increase scrape interval
- Add more Prometheus instances (federation)

---

**Last Updated**: Task 15.2 Implementation  
**Version**: 1.0  
**Status**: Complete

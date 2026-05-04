# Drug Designer - Grafana Dashboards

## Overview

This directory contains comprehensive Grafana dashboards for monitoring the Drug Designer platform. These dashboards provide real-time visibility into system health, performance SLAs, connector health, clinical workflows, database performance, and model inference metrics.

**Task**: 15.1 Create comprehensive Grafana dashboards  
**Priority**: P2  
**Requirements**: NFR-MAIN-002 (Monitoring & Observability)

## Dashboard Inventory

### 1. System Health Dashboard (`system-health.json`)

**Purpose**: Overall system health and operational metrics

**Key Metrics**:
- Service health status (API, PostgreSQL, Redis, Qdrant, Neo4j, MinIO)
- System uptime
- Total API requests (24h)
- Error rate (5m)
- Active WebSocket connections
- API request rate by method
- API requests by status code
- Memory usage by service
- CPU usage
- Database connections
- Cache hit rate

**Refresh Rate**: 30 seconds

**Use Cases**:
- Quick health check of all services
- Identifying service outages
- Monitoring resource utilization
- Tracking overall system performance

---

### 2. Performance SLA Dashboard (`performance-sla.json`)

**Purpose**: Monitor compliance with performance SLA targets

**Key Metrics**:
- SLA compliance overview (>95% target)
  - Health/Auth endpoints (<200ms)
  - Evidence search (<2s)
  - Disease intelligence (<30s)
  - Target prioritization (<15s)
  - Graph queries (<1s)
  - Dossier generation (<90s)
- API latency p95 by endpoint
- Clinical workflow stage latency (p95)
- Clinical workflow SLA compliance
  - EHR ingestion (<5s)
  - Phenotype clustering (<30s)
  - Tissue analysis (<2min)
  - Biomarker quantification (<30s)
  - Pathogenicity prediction (<1min)
  - Drug matching (<30s)
  - Therapy stratification (<10s)
- Database query latency (p95)
- Model inference latency (p95)
- SLA violations table (last 24h)

**Alerts**:
- High API Latency (>30s for 5m)
- SLA Violation (<95% compliance for 10m)

**Refresh Rate**: 30 seconds

**Use Cases**:
- Ensuring SLA compliance
- Identifying performance bottlenecks
- Tracking latency trends
- Validating performance improvements

---

### 3. Connector Health Dashboard (`connector-health.json`)

**Purpose**: Monitor health and performance of 140+ external API connectors

**Key Metrics**:
- Connector uptime (last 24h) - target: >90%
- Total connector requests (24h)
- Connector error rate (5m)
- Circuit breakers open count
- Connector request rate by family
- Connector latency (p95) by family
- SLA compliance by connector family:
  - Literature connectors (<3s)
  - Disease/Ontology connectors (<2s)
  - Target/Protein connectors (<2s)
  - Pathway connectors (<2s)
  - Compound/Drug connectors (<2s)
  - Genetics/Variant connectors (<2s)
  - Translational/Clinical connectors (<3s)
  - Population/Regional connectors (<3s)
- Connector cache hit rate
- Connector errors by type
- Circuit breaker status table
- Top 10 slowest connectors

**Alerts**:
- Connector Circuit Breaker Open (for 5m)
- Slow Connector (>10s for 5m)
- Low Connector Uptime (<90% for 10m)
- High Connector Error Rate (>10% for 5m)

**Refresh Rate**: 1 minute

**Use Cases**:
- Monitoring external API health
- Identifying failing connectors
- Tracking circuit breaker activations
- Optimizing connector performance
- Validating cache effectiveness

---

### 4. Clinical Workflow Dashboard (`clinical-workflow.json`)

**Purpose**: Monitor the 10-stage clinical workflow pipeline

**Key Metrics**:
- Clinical workflow completion rate (target: >90%)
- Total workflows (24h)
- Average workflow duration (target: <30min)
- Workflow error rate
- Workflow stage throughput
- Per-stage metrics (latency p95 and success rate):
  1. EHR Ingestion (SLA: <5s)
  2. Phenotype Clustering (SLA: <30s)
  3. Tissue Analysis (SLA: <2min)
  4. Biomarker Quantification (SLA: <30s)
  5. Genomic Sequencing (SLA: <10min WES)
  6. Pathogenicity Prediction (SLA: <1min for 1000 variants)
  7. Knowledge Graph Cross-Reference (SLA: <500ms)
  8. Disruption Modeling (SLA: <30s per mutation)
  9. Drug Matching (SLA: <30s)
  10. Therapy Stratification (SLA: <10s)

**Alerts**:
- Clinical Workflow SLA Violation (<95% compliance for 10m)
- High Clinical Workflow Error Rate (>5% for 5m)

**Refresh Rate**: 30 seconds

**Use Cases**:
- Monitoring clinical pipeline health
- Identifying workflow bottlenecks
- Tracking stage-specific performance
- Ensuring clinical SLA compliance
- Debugging workflow failures

---

### 5. Database Performance Dashboard (`database-performance.json`)

**Purpose**: Monitor database and data store performance

**Key Metrics**:
- PostgreSQL connection pool (active vs pool size)
- Database query rate by operation
- Database query latency (p95) by operation
- Database query latency (p95) by table
- Database errors by type
- PostgreSQL database size
- Redis memory usage and evictions
- Redis operations rate
- Qdrant vector store performance
- Neo4j graph database performance
- Top 10 slowest queries

**Alerts**:
- Database Connection Pool Exhaustion (>90% for 5m)
- Slow Database Query (>1s for 5m)
- High Database Error Rate (>1 error/sec for 5m)

**Refresh Rate**: 30 seconds

**Use Cases**:
- Monitoring database health
- Identifying slow queries
- Tracking connection pool usage
- Optimizing query performance
- Capacity planning

---

### 6. Model Inference Dashboard (`model-inference.json`)

**Purpose**: Monitor deep learning model inference performance

**Key Metrics**:
- Model inference rate by model
- Model inference latency (p95) by model
- Per-model metrics:
  - ESM-2 Protein Language Model (target: <10s for 100 proteins)
  - MolFormer Molecule Transformer (target: <5s for 100 molecules)
  - Pathogenicity Prediction Model (target: <1min for 1000 variants)
  - Tissue Analysis Computer Vision Model (target: <2min per WSI)
  - Biomarker Quantification Neural Network (target: <30s per sample)
  - GAT Target Ranking Model (target: <30s for 1000 targets)
- Model memory usage
- Model batch size distribution
- Model errors by type
- Model performance summary table

**Alerts**:
- Slow Model Inference (>60s for 5m)
- High Model Error Rate (>0.1 errors/sec for 5m)
- High Model Memory Usage (>16GB for 5m)

**Refresh Rate**: 30 seconds

**Use Cases**:
- Monitoring ML model performance
- Identifying inference bottlenecks
- Tracking model memory usage
- Optimizing batch sizes
- Debugging model errors

---

## Alert Rules

Alert rules are defined in `monitoring/prometheus/alerts/drug-designer-alerts.yml` and cover:

### SLA Violations
- High API Latency (>30s)
- High Error Rate (>0.1%)
- SLA Violation (<95% compliance)

### Connector Health
- Connector Circuit Breaker Open
- Slow Connector (>10s)
- Low Connector Uptime (<90%)
- High Connector Error Rate (>10%)

### Clinical Workflow
- Clinical Workflow SLA Violation
- High Clinical Workflow Error Rate (>5%)

### Database
- Database Connection Pool Exhaustion (>90%)
- Slow Database Query (>1s)
- High Database Error Rate

### Models
- Slow Model Inference (>60s)
- High Model Error Rate
- High Model Memory Usage (>16GB)

### System
- Service Down
- High Memory Usage (>90%)
- High CPU Usage (>80%)
- Low Cache Hit Rate (<50%)

### WebSocket
- High WebSocket Connections (>1000)
- WebSocket Message Backlog

## Accessing Dashboards

### Local Development
1. Start the monitoring stack:
   ```bash
   docker-compose up -d grafana prometheus
   ```

2. Access Grafana:
   - URL: http://localhost:3000
   - Default credentials: admin/admin

3. Navigate to Dashboards → Drug Designer folder

### Production
1. Access Grafana through the configured domain
2. Use SSO or configured authentication
3. Navigate to Dashboards → Drug Designer folder

## Dashboard Provisioning

Dashboards are automatically provisioned via:
- **Provisioning Config**: `monitoring/grafana/provisioning/dashboards/dashboards.yaml`
- **Dashboard Files**: `monitoring/grafana/dashboards/*.json`

Changes to dashboard JSON files are automatically detected and applied on Grafana restart.

## Metrics Collection

Metrics are collected by Prometheus from:
- **API Server**: `http://api:8000/metrics`
- **PostgreSQL**: `postgres:5432`
- **Redis**: `redis:6379`
- **Qdrant**: `qdrant:6333/metrics`
- **Neo4j**: `neo4j:7474/metrics`
- **MinIO**: `minio:9000/minio/v2/metrics/cluster`

Prometheus configuration: `monitoring/prometheus/prometheus.yml`

## Customization

### Adding New Panels
1. Edit the dashboard JSON file
2. Add new panel configuration to the `panels` array
3. Restart Grafana or wait for auto-reload

### Modifying Alerts
1. Edit `monitoring/prometheus/alerts/drug-designer-alerts.yml`
2. Reload Prometheus configuration:
   ```bash
   docker-compose exec prometheus kill -HUP 1
   ```

### Adjusting Thresholds
Update threshold values in:
- Dashboard JSON files (for visual thresholds)
- Alert rules YAML (for alert thresholds)

## Best Practices

1. **Monitor SLA Compliance**: Check Performance SLA dashboard daily
2. **Review Connector Health**: Monitor connector uptime and circuit breakers
3. **Track Clinical Workflows**: Ensure all 10 stages meet SLA targets
4. **Optimize Slow Queries**: Use Database Performance dashboard to identify bottlenecks
5. **Monitor Model Performance**: Track inference latency and memory usage
6. **Respond to Alerts**: Configure alert notifications (email, Slack, PagerDuty)
7. **Capacity Planning**: Use trends to predict resource needs

## Troubleshooting

### Dashboard Not Loading
- Check Grafana logs: `docker-compose logs grafana`
- Verify provisioning config: `monitoring/grafana/provisioning/dashboards/dashboards.yaml`
- Ensure dashboard JSON is valid

### No Data in Panels
- Verify Prometheus is scraping metrics: http://localhost:9090/targets
- Check metric names match those in dashboard queries
- Ensure time range is appropriate

### Alerts Not Firing
- Verify alert rules are loaded: http://localhost:9090/alerts
- Check alert rule syntax in YAML file
- Ensure Alertmanager is configured (if using)

## Maintenance

### Regular Tasks
- Review dashboard performance monthly
- Update SLA thresholds as requirements change
- Add new metrics as features are added
- Archive old dashboards when deprecated

### Version Control
All dashboard JSON files are version controlled in Git. Changes should be:
1. Tested in development
2. Reviewed by team
3. Deployed to production via CI/CD

## Support

For issues or questions:
- Check Grafana documentation: https://grafana.com/docs/
- Review Prometheus documentation: https://prometheus.io/docs/
- Contact DevOps team

---

**Last Updated**: Task 15.1 Implementation  
**Version**: 1.0  
**Status**: Complete

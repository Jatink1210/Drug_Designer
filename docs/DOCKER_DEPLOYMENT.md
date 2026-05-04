# Drug Designer — Production Docker Deployment Guide

## Overview

This guide covers deploying the Drug Designer platform using Docker Compose in a production environment. The stack includes all necessary services for a complete, production-ready deployment.

**Task Reference:** Task 23.1 - Configure Docker Compose stack (NFR-MAIN-002)

## Architecture

The production stack consists of:

### Application Layer
- **API Server** (FastAPI) - 2 replicas with load balancing
- **Web Frontend** (React + Nginx) - Static asset serving
- **Background Workers** (ARQ) - 3 replicas for async job processing

### Data Layer
- **PostgreSQL 16** - Primary relational database
- **Redis 7** - Cache and message queue
- **Qdrant v1.13** - Vector embeddings store
- **Neo4j 5** - Knowledge graph database
- **MinIO** - S3-compatible object storage

### Infrastructure Layer
- **Nginx** - Reverse proxy and load balancer

### Observability Layer (NFR-MAIN-002)
- **Prometheus** - Metrics collection and alerting
- **Grafana** - Dashboards and visualization
- **Loki** - Log aggregation
- **Promtail** - Log collection agent

## Prerequisites

1. **Docker Engine** 24.0+ and **Docker Compose** 2.20+
2. **System Requirements:**
   - CPU: 16+ cores recommended
   - RAM: 32GB+ recommended
   - Disk: 500GB+ SSD storage
3. **Network:** Open ports 80, 443, 3000, 3001, 9090

## Quick Start

### 1. Environment Configuration

Create a `.env.prod` file with required secrets:

```bash
# Database
POSTGRES_USER=drugdesigner
POSTGRES_PASSWORD=<strong-password>
POSTGRES_DB=drugdesigner

# Neo4j
NEO4J_PASSWORD=<strong-password>

# MinIO
MINIO_ROOT_USER=admin
MINIO_ROOT_PASSWORD=<strong-password>

# Security
JWT_SECRET=<random-256-bit-key>
PG_ENCRYPT_KEY=<random-256-bit-key>

# Grafana
GRAFANA_ADMIN_PASSWORD=<strong-password>
GRAFANA_SECRET_KEY=<random-key>

# Optional: Error Tracking
SENTRY_DSN=https://...
```

### 2. Generate Secrets

Use the provided script to generate secure secrets:

```bash
# Generate random secrets
openssl rand -hex 32  # For JWT_SECRET
openssl rand -hex 32  # For PG_ENCRYPT_KEY
openssl rand -hex 32  # For GRAFANA_SECRET_KEY
```

### 3. Start the Stack

```bash
# Start all services
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Check service health
docker-compose -f docker-compose.prod.yml ps

# View logs
docker-compose -f docker-compose.prod.yml logs -f
```

### 4. Initialize Database

```bash
# Run database migrations
docker-compose -f docker-compose.prod.yml exec api alembic upgrade head

# Create initial admin user (optional)
docker-compose -f docker-compose.prod.yml exec api python scripts/create_admin.py
```

### 5. Verify Deployment

Access the following endpoints:

- **Application:** http://localhost:3000
- **API Docs:** http://localhost:8000/docs
- **Grafana:** http://localhost:3001 (admin / <GRAFANA_ADMIN_PASSWORD>)
- **Prometheus:** http://localhost:9090
- **MinIO Console:** http://localhost:9001

## Service Configuration

### Health Checks

All services include health checks with the following parameters:

| Service | Interval | Timeout | Retries | Start Period |
|---------|----------|---------|---------|--------------|
| API | 30s | 10s | 3 | 40s |
| Web | 30s | 10s | 3 | 20s |
| Worker | 30s | 10s | 3 | 30s |
| PostgreSQL | 10s | 5s | 5 | 30s |
| Redis | 10s | 5s | 5 | 10s |
| Qdrant | 30s | 10s | 3 | 30s |
| Neo4j | 30s | 10s | 5 | 60s |
| MinIO | 30s | 10s | 3 | 30s |
| Prometheus | 30s | 10s | 3 | 30s |
| Grafana | 30s | 10s | 3 | 40s |
| Loki | 30s | 10s | 3 | 30s |

### Resource Limits

Production resource limits per service:

| Service | CPU Limit | Memory Limit | CPU Reserved | Memory Reserved |
|---------|-----------|--------------|--------------|-----------------|
| API | 2.0 | 4GB | 1.0 | 2GB |
| Web | 1.0 | 512MB | 0.5 | 256MB |
| Worker (×3) | 2.0 | 4GB | 1.0 | 2GB |
| PostgreSQL | 4.0 | 8GB | 2.0 | 4GB |
| Redis | 1.0 | 2GB | 0.5 | 1GB |
| Qdrant | 4.0 | 8GB | 2.0 | 4GB |
| Neo4j | 4.0 | 8GB | 2.0 | 4GB |
| MinIO | 2.0 | 4GB | 1.0 | 2GB |
| Prometheus | 2.0 | 2GB | 1.0 | 1GB |
| Grafana | 1.0 | 1GB | 0.5 | 512MB |
| Loki | 2.0 | 2GB | 1.0 | 1GB |

**Total Resources:**
- CPU: ~30 cores (limits), ~15 cores (reserved)
- Memory: ~48GB (limits), ~24GB (reserved)

### Restart Policies

All services use `restart: unless-stopped` for high availability:
- Services automatically restart on failure
- Services remain stopped if manually stopped
- Services start automatically on system boot

## Monitoring & Observability

### Prometheus Metrics

Prometheus scrapes metrics from all services every 15 seconds:

- **Application Metrics:** Request rates, latencies, error rates
- **Database Metrics:** Connection pools, query performance, cache hit rates
- **System Metrics:** CPU, memory, disk usage
- **Connector Metrics:** External API health, circuit breaker states

Access Prometheus: http://localhost:9090

### Grafana Dashboards

Pre-configured dashboards for:

1. **System Overview** - Overall health and performance
2. **API Performance** - Request rates, latencies, error rates
3. **Database Performance** - PostgreSQL, Redis, Qdrant, Neo4j metrics
4. **Connector Health** - External API status and failure rates
5. **Resource Usage** - CPU, memory, disk across all services

Access Grafana: http://localhost:3001

Default credentials: `admin` / `<GRAFANA_ADMIN_PASSWORD>`

### Log Aggregation

Loki collects logs from all Docker containers:

- **Structured Logging:** JSON format with trace IDs
- **Log Retention:** 30 days (configurable)
- **Query Interface:** Available in Grafana

Query logs in Grafana using LogQL:
```logql
{service="api"} |= "error"
{service="worker"} | json | level="ERROR"
```

### Alerting

Prometheus alerts are configured for:

- **Critical Alerts:**
  - Service down (API, PostgreSQL, Redis, Qdrant, Neo4j, MinIO)
  - High error rates (>5% for 5 minutes)
  
- **Warning Alerts:**
  - High latency (p95 >2s for 5 minutes)
  - High resource usage (CPU >80%, Memory >90%)
  - Connector failures (>20% failure rate)
  - Circuit breakers open

Alert rules: `monitoring/prometheus/alerts/drug-designer-alerts.yml`

## Backup & Recovery

### Database Backups

PostgreSQL backups are stored in `./backups/postgres`:

```bash
# Manual backup
docker-compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U drugdesigner drugdesigner > backup_$(date +%Y%m%d).sql

# Restore from backup
docker-compose -f docker-compose.prod.yml exec -T postgres \
  psql -U drugdesigner drugdesigner < backup_20240101.sql
```

### Neo4j Backups

Neo4j backups are stored in `./backups/neo4j`:

```bash
# Manual backup
docker-compose -f docker-compose.prod.yml exec neo4j \
  neo4j-admin database dump neo4j --to-path=/backups

# Restore from backup
docker-compose -f docker-compose.prod.yml exec neo4j \
  neo4j-admin database load neo4j --from-path=/backups
```

### Volume Backups

All persistent data is stored in Docker volumes:

```bash
# List volumes
docker volume ls | grep drugdesigner

# Backup a volume
docker run --rm -v drugdesigner_postgres_data:/data -v $(pwd)/backups:/backup \
  alpine tar czf /backup/postgres_data.tar.gz -C /data .

# Restore a volume
docker run --rm -v drugdesigner_postgres_data:/data -v $(pwd)/backups:/backup \
  alpine tar xzf /backup/postgres_data.tar.gz -C /data
```

## Scaling

### Horizontal Scaling

Scale individual services:

```bash
# Scale API servers
docker-compose -f docker-compose.prod.yml up -d --scale api=4

# Scale workers
docker-compose -f docker-compose.prod.yml up -d --scale worker=5
```

### Load Balancing

Nginx automatically load balances across API replicas. Update `nginx.conf` for custom load balancing strategies.

## Security

### Network Isolation

All services communicate on an isolated bridge network (`drugdesigner-network`):
- Subnet: 172.20.0.0/16
- No external access except through Nginx

### Secrets Management

**Never commit secrets to version control!**

Use environment variables or Docker secrets:

```bash
# Using Docker secrets (Swarm mode)
echo "my-secret-password" | docker secret create postgres_password -
```

### TLS/SSL

For production, configure TLS certificates:

1. Place certificates in `./certs/`:
   - `cert.pem` - SSL certificate
   - `key.pem` - Private key
   - `ca.pem` - CA certificate (optional)

2. Update `nginx.conf` to enable HTTPS

3. Restart Nginx:
   ```bash
   docker-compose -f docker-compose.prod.yml restart nginx
   ```

## Troubleshooting

### Service Won't Start

Check logs:
```bash
docker-compose -f docker-compose.prod.yml logs <service-name>
```

Common issues:
- Missing environment variables
- Port conflicts
- Insufficient resources
- Volume permission issues

### Database Connection Errors

Verify PostgreSQL is healthy:
```bash
docker-compose -f docker-compose.prod.yml exec postgres pg_isready
```

Check connection string in API logs:
```bash
docker-compose -f docker-compose.prod.yml logs api | grep POSTGRES_URL
```

### High Memory Usage

Check resource usage:
```bash
docker stats
```

Adjust resource limits in `docker-compose.prod.yml` if needed.

### Connector Failures

Check circuit breaker status in Prometheus:
```promql
circuit_breaker_state{state="open"}
```

View connector logs:
```bash
docker-compose -f docker-compose.prod.yml logs api | grep connector
```

## Maintenance

### Update Services

```bash
# Pull latest images
docker-compose -f docker-compose.prod.yml pull

# Restart services with new images
docker-compose -f docker-compose.prod.yml up -d

# Remove old images
docker image prune -a
```

### Database Migrations

```bash
# Check current migration version
docker-compose -f docker-compose.prod.yml exec api alembic current

# Apply migrations
docker-compose -f docker-compose.prod.yml exec api alembic upgrade head

# Rollback migration
docker-compose -f docker-compose.prod.yml exec api alembic downgrade -1
```

### Clean Up

```bash
# Stop all services
docker-compose -f docker-compose.prod.yml down

# Remove volumes (WARNING: deletes all data)
docker-compose -f docker-compose.prod.yml down -v

# Remove orphaned containers
docker-compose -f docker-compose.prod.yml down --remove-orphans
```

## Performance Tuning

### PostgreSQL

Adjust PostgreSQL settings in `docker-compose.prod.yml`:
- `shared_buffers`: 25% of system RAM
- `effective_cache_size`: 50-75% of system RAM
- `work_mem`: Total RAM / max_connections / 16

### Redis

Configure Redis memory policy:
- `maxmemory`: Set based on available RAM
- `maxmemory-policy`: `allkeys-lru` for cache eviction

### Qdrant

Optimize vector search:
- Increase memory allocation for better performance
- Use HNSW index for large datasets
- Adjust `m` and `ef_construct` parameters

## Support

For issues and questions:
- GitHub Issues: [repository-url]
- Documentation: [docs-url]
- Email: support@drugdesigner.com

## License

Copyright © 2024 Drug Designer. All rights reserved.

# Environment Variables Configuration Guide

**Task:** 23.2 - Configure environment variables  
**Priority:** P0 (Critical)  
**Last Updated:** April 23, 2026

---

## Table of Contents

1. [Overview](#overview)
2. [Quick Start](#quick-start)
3. [Environment-Specific Configurations](#environment-specific-configurations)
4. [Security Best Practices](#security-best-practices)
5. [Variable Reference](#variable-reference)
6. [Secret Management](#secret-management)
7. [Validation & Testing](#validation--testing)
8. [Troubleshooting](#troubleshooting)

---

## Overview

The Drug Designer platform uses environment variables for all configuration to follow the [12-Factor App](https://12factor.net/) methodology. This ensures:

- **Security:** No hardcoded credentials in source code
- **Flexibility:** Easy configuration across environments
- **Portability:** Same codebase runs in dev, staging, and production
- **Compliance:** HIPAA-compliant secret management

### Configuration Files

| File | Purpose | Committed to Git? |
|------|---------|-------------------|
| `.env.example` | Template with all variables | ✅ Yes |
| `.env` | Local development configuration | ❌ No (gitignored) |
| `.env.staging` | Staging environment configuration | ❌ No (secure storage) |
| `.env.production` | Production environment configuration | ❌ No (secure storage) |

---

## Quick Start

### 1. Copy Template

```bash
cp .env.example .env
```

### 2. Generate Secrets

```bash
# JWT Secret (256-bit)
python -c "import secrets; print('JWT_SECRET=' + secrets.token_urlsafe(32))"

# Encryption Key (Fernet)
python -c "from cryptography.fernet import Fernet; print('ENCRYPTION_KEY=' + Fernet.generate_key().decode())"

# PostgreSQL Encryption Key (256-bit hex)
openssl rand -hex 32 | awk '{print "PG_ENCRYPT_KEY=" $0}'

# Grafana Secret Key
python -c "import secrets; print('GRAFANA_SECRET_KEY=' + secrets.token_urlsafe(32))"
```

### 3. Set Required Variables

**Minimum required for local development:**

```bash
# Database
POSTGRES_PASSWORD=your_strong_password_here

# Neo4j
NEO4J_PASSWORD=your_strong_password_here

# MinIO
MINIO_ROOT_PASSWORD=your_strong_password_here

# Security
JWT_SECRET=<generated_from_step_2>
ENCRYPTION_KEY=<generated_from_step_2>
PG_ENCRYPT_KEY=<generated_from_step_2>

# Grafana
GRAFANA_ADMIN_PASSWORD=your_strong_password_here
GRAFANA_SECRET_KEY=<generated_from_step_2>
```

### 4. Validate Configuration

```bash
# Check for CHANGE_ME placeholders
grep -r "CHANGE_ME" .env

# Validate required variables
python scripts/validate_env.py
```

---

## Environment-Specific Configurations

### Development Environment

**File:** `.env`

```bash
ENVIRONMENT=development
DEBUG=true
LOG_LEVEL=debug

# Use local services
POSTGRES_HOST=localhost
REDIS_HOST=localhost
NEO4J_URI=bolt://localhost:7687
QDRANT_HOST=localhost
MINIO_ENDPOINT=localhost:9000

# Disable security features for easier development
DSS_SECURE_COOKIES=false
RATE_LIMIT_ENABLED=false

# Mock external APIs (optional)
MOCK_EXTERNAL_APIS=true

# Enable hot reload
API_RELOAD=true
```

### Staging Environment

**File:** `.env.staging` (stored in secure vault)

```bash
ENVIRONMENT=staging
DEBUG=false
LOG_LEVEL=info

# Use staging database
POSTGRES_HOST=staging-db.internal
POSTGRES_PASSWORD=<vault:staging/postgres_password>

# Use staging services
REDIS_HOST=staging-redis.internal
NEO4J_URI=bolt://staging-neo4j.internal:7687
QDRANT_HOST=staging-qdrant.internal
MINIO_ENDPOINT=staging-minio.internal:9000

# Enable security features
DSS_SECURE_COOKIES=true
RATE_LIMIT_ENABLED=true
CIRCUIT_BREAKER_ENABLED=true

# Enable monitoring
SENTRY_DSN=<vault:staging/sentry_dsn>
SENTRY_ENVIRONMENT=staging
PROMETHEUS_ENABLED=true
LOKI_ENABLED=true

# Use real external APIs
MOCK_EXTERNAL_APIS=false
NCBI_API_KEY=<vault:staging/ncbi_api_key>
DISGENET_API_KEY=<vault:staging/disgenet_api_key>
```

### Production Environment

**File:** `.env.production` (stored in secure vault)

```bash
ENVIRONMENT=production
DEBUG=false
LOG_LEVEL=warning

# Use production database with connection pooling
POSTGRES_HOST=prod-db-primary.internal
POSTGRES_PASSWORD=<vault:production/postgres_password>
POSTGRES_POOL_SIZE=50
POSTGRES_MAX_OVERFLOW=20

# Use production services
REDIS_HOST=prod-redis-cluster.internal
NEO4J_URI=bolt://prod-neo4j-cluster.internal:7687
QDRANT_HOST=prod-qdrant-cluster.internal
MINIO_ENDPOINT=prod-minio-cluster.internal:9000

# Maximum security
DSS_SECURE_COOKIES=true
RATE_LIMIT_ENABLED=true
CIRCUIT_BREAKER_ENABLED=true
LLM_ENABLE_PROMPT_INJECTION_DETECTION=true

# Production monitoring
SENTRY_DSN=<vault:production/sentry_dsn>
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.01
PROMETHEUS_ENABLED=true
LOKI_ENABLED=true
GRAFANA_ROOT_URL=https://monitoring.drugdesigner.com

# Production API keys
NCBI_API_KEY=<vault:production/ncbi_api_key>
DISGENET_API_KEY=<vault:production/disgenet_api_key>
OPENTARGETS_API_KEY=<vault:production/opentargets_api_key>
CHEMBL_API_KEY=<vault:production/chembl_api_key>
DRUGBANK_API_KEY=<vault:production/drugbank_api_key>

# Production LLM
OPENAI_API_KEY=<vault:production/openai_api_key>
LLM_RUNTIME_MODE=hosted

# Backup configuration
BACKUP_ENABLED=true
BACKUP_S3_BUCKET=drugdesigner-backups-prod
BACKUP_SCHEDULE=0 2 * * *
BACKUP_RETENTION_DAYS=90

# Performance tuning
ARQ_WORKER_COUNT=10
ARQ_MAX_JOBS=50
WEBSOCKET_MAX_CONNECTIONS=5000
```

---

## Security Best Practices

### 1. Secret Generation

**Always use cryptographically secure random generators:**

```bash
# ✅ GOOD: Cryptographically secure
python -c "import secrets; print(secrets.token_urlsafe(32))"

# ❌ BAD: Not cryptographically secure
echo "my_secret_key"
```

### 2. Password Requirements

**All passwords MUST meet these requirements:**

- Minimum 16 characters
- Mixed case (uppercase and lowercase)
- Numbers
- Special characters
- No dictionary words
- No personal information

**Example strong password:**
```
Kx9#mP2$vL8@nQ5!wR7&tY4^uI3*oP6
```

### 3. Secret Rotation

**Rotate secrets on this schedule:**

| Secret Type | Rotation Frequency | Priority |
|-------------|-------------------|----------|
| JWT_SECRET | Every 90 days | High |
| ENCRYPTION_KEY | Every 180 days | Critical |
| PG_ENCRYPT_KEY | Every 180 days | Critical |
| Database passwords | Every 90 days | High |
| API keys | Every 180 days | Medium |
| Service passwords | Every 90 days | High |

**Rotation procedure:**

1. Generate new secret
2. Update in vault/secret manager
3. Deploy to staging
4. Validate functionality
5. Deploy to production with zero-downtime
6. Revoke old secret after 24 hours

### 4. Secret Storage

**NEVER store secrets in:**

- ❌ Source code
- ❌ Git repositories
- ❌ Docker images
- ❌ Configuration files committed to version control
- ❌ Slack/email/chat
- ❌ Unencrypted files

**ALWAYS store secrets in:**

- ✅ Environment variables
- ✅ Secret management systems (HashiCorp Vault, AWS Secrets Manager)
- ✅ Encrypted configuration files (with separate key management)
- ✅ Kubernetes Secrets (encrypted at rest)

### 5. Access Control

**Principle of Least Privilege:**

- Developers: Access to development secrets only
- DevOps: Access to staging and production secrets
- CI/CD: Read-only access to deployment secrets
- Applications: Access only to required secrets

**Audit all secret access:**

```bash
# Log all secret retrievals
vault audit enable file file_path=/var/log/vault_audit.log

# Review access logs regularly
vault audit list
```

---

## Variable Reference

### Critical Variables (MUST be set)

| Variable | Description | Example | Security Level |
|----------|-------------|---------|----------------|
| `JWT_SECRET` | JWT token signing key | `<32-byte-random>` | 🔴 Critical |
| `ENCRYPTION_KEY` | Fernet encryption key | `<fernet-key>` | 🔴 Critical |
| `PG_ENCRYPT_KEY` | PostgreSQL encryption key | `<32-byte-hex>` | 🔴 Critical |
| `POSTGRES_PASSWORD` | Database password | `<strong-password>` | 🔴 Critical |
| `NEO4J_PASSWORD` | Neo4j password | `<strong-password>` | 🔴 Critical |
| `MINIO_ROOT_PASSWORD` | MinIO password | `<strong-password>` | 🔴 Critical |

### High Priority Variables (Should be set)

| Variable | Description | Example | Security Level |
|----------|-------------|---------|----------------|
| `GRAFANA_ADMIN_PASSWORD` | Grafana admin password | `<strong-password>` | 🟠 High |
| `GRAFANA_SECRET_KEY` | Grafana secret key | `<32-byte-random>` | 🟠 High |
| `SENTRY_DSN` | Sentry error tracking DSN | `https://...@sentry.io/...` | 🟠 High |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` | 🟠 High |
| `NCBI_API_KEY` | NCBI API key | `...` | 🟡 Medium |

### Optional Variables (Can use defaults)

| Variable | Description | Default | Required? |
|----------|-------------|---------|-----------|
| `LOG_LEVEL` | Logging level | `info` | No |
| `API_PORT` | API server port | `8000` | No |
| `CACHE_DEFAULT_TTL` | Cache TTL (seconds) | `1800` | No |
| `ARQ_WORKER_COUNT` | Background workers | `3` | No |

### Database Configuration

```bash
# PostgreSQL (Primary Database)
POSTGRES_USER=drugdesigner
POSTGRES_PASSWORD=<vault:postgres_password>
POSTGRES_DB=drugdesigner
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_POOL_SIZE=20
POSTGRES_MAX_OVERFLOW=10

# Neo4j (Knowledge Graph)
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=<vault:neo4j_password>
NEO4J_MAX_CONNECTION_POOL_SIZE=50

# Redis (Cache & Queue)
REDIS_URL=redis://localhost:6379/0
REDIS_MAX_CONNECTIONS=50
REDIS_PASSWORD=<vault:redis_password>

# Qdrant (Vector Store)
QDRANT_HOST=localhost
QDRANT_PORT=6333
QDRANT_API_KEY=<vault:qdrant_api_key>
```

### Security Configuration

```bash
# JWT Authentication
JWT_SECRET=<vault:jwt_secret>
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7

# Encryption
ENCRYPTION_KEY=<vault:encryption_key>
PG_ENCRYPT_KEY=<vault:pg_encrypt_key>

# Password Hashing
PASSWORD_HASH_ALGORITHM=bcrypt
PASSWORD_HASH_ROUNDS=12

# Rate Limiting
RATE_LIMIT_ENABLED=true
RATE_LIMIT_PER_MINUTE=60
RATE_LIMIT_PER_HOUR=1000

# Circuit Breaker
CIRCUIT_BREAKER_ENABLED=true
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_RECOVERY_TIMEOUT=300
```

### LLM Configuration

```bash
# Ollama (Local LLM, opt-in only)
OLLAMA_HOST=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_TIMEOUT=300
LLM_ENABLE_OLLAMA=false

# OpenAI (Hosted LLM)
OPENAI_API_KEY=<vault:openai_api_key>
OPENAI_MODEL=gpt-4o-mini
OPENAI_TIMEOUT=60
OPENAI_MAX_RETRIES=3

# Runtime Mode (default Docker profile)
LLM_RUNTIME_MODE=hosted  # hosted | local | auto

# Security
LLM_ENABLE_PROMPT_INJECTION_DETECTION=true
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.7
```

### Clinical Workflow Configuration

```bash
# EHR Data Ingestion
EHR_SUPPORTED_FORMATS=HL7v2,HL7v3,FHIR_R4,CDA
EHR_PHI_REDACTION_ENABLED=true
EHR_BATCH_SIZE=100

# Phenotype Clustering
PHENOTYPE_CLUSTERING_ALGORITHM=HDBSCAN
PHENOTYPE_MIN_CLUSTER_SIZE=5
PHENOTYPE_EMBEDDING_MODEL=all-MiniLM-L6-v2

# Genomic Sequencing
GENOMIC_VCF_VERSION=4.2
GENOMIC_QUALITY_THRESHOLD=30
GENOMIC_DEPTH_THRESHOLD=10

# Pathogenicity Prediction
PATHOGENICITY_CONFIDENCE_LEVEL=0.9
PATHOGENICITY_ACMG_COMPLIANCE=true

# Drug Matching
DRUG_MATCHING_TOP_K=10
DRUG_MATCHING_MIN_SCORE=0.7

# Therapy Stratification
THERAPY_STRATIFICATION_HLA_MATCHING=true
THERAPY_STRATIFICATION_RISK_THRESHOLD=0.8
```

### Monitoring Configuration

```bash
# Prometheus
PROMETHEUS_ENABLED=true
PROMETHEUS_PORT=9090

# Grafana
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=<vault:grafana_password>
GRAFANA_PORT=3001
GRAFANA_SECRET_KEY=<vault:grafana_secret>
GRAFANA_ROOT_URL=http://localhost:3001

# Sentry
SENTRY_DSN=<vault:sentry_dsn>
SENTRY_ENVIRONMENT=production
SENTRY_TRACES_SAMPLE_RATE=0.1

# Loki
LOKI_URL=http://localhost:3100
LOKI_ENABLED=true

# Metrics
METRICS_ENABLED=true
METRICS_EXPORT_INTERVAL=60
```

---

## Secret Management

### Using HashiCorp Vault

**1. Store secrets in Vault:**

```bash
# Store database password
vault kv put secret/drugdesigner/postgres password="<strong-password>"

# Store JWT secret
vault kv put secret/drugdesigner/jwt secret="<generated-secret>"

# Store API keys
vault kv put secret/drugdesigner/apis \
  ncbi="<ncbi-key>" \
  disgenet="<disgenet-key>" \
  openai="<openai-key>"
```

**2. Retrieve secrets in application:**

```python
import hvac

# Initialize Vault client
client = hvac.Client(url='http://vault:8200')
client.token = os.getenv('VAULT_TOKEN')

# Read secret
secret = client.secrets.kv.v2.read_secret_version(
    path='drugdesigner/postgres'
)
postgres_password = secret['data']['data']['password']
```

**3. Use Vault in Docker Compose:**

```yaml
services:
  api:
    environment:
      - POSTGRES_PASSWORD=vault:secret/drugdesigner/postgres#password
      - JWT_SECRET=vault:secret/drugdesigner/jwt#secret
```

### Using AWS Secrets Manager

**1. Store secrets:**

```bash
# Store database password
aws secretsmanager create-secret \
  --name drugdesigner/postgres/password \
  --secret-string "<strong-password>"

# Store JWT secret
aws secretsmanager create-secret \
  --name drugdesigner/jwt/secret \
  --secret-string "<generated-secret>"
```

**2. Retrieve secrets in application:**

```python
import boto3

# Initialize Secrets Manager client
client = boto3.client('secretsmanager')

# Get secret
response = client.get_secret_value(
    SecretId='drugdesigner/postgres/password'
)
postgres_password = response['SecretString']
```

### Using Kubernetes Secrets

**1. Create secret:**

```bash
# Create from literal
kubectl create secret generic drugdesigner-secrets \
  --from-literal=postgres-password='<strong-password>' \
  --from-literal=jwt-secret='<generated-secret>'

# Create from file
kubectl create secret generic drugdesigner-secrets \
  --from-file=.env.production
```

**2. Use in deployment:**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: drugdesigner-api
spec:
  template:
    spec:
      containers:
      - name: api
        envFrom:
        - secretRef:
            name: drugdesigner-secrets
```

---

## Validation & Testing

### Environment Validation Script

**File:** `scripts/validate_env.py`

```python
#!/usr/bin/env python3
"""
Environment variable validation script.
Checks for required variables and validates formats.
"""

import os
import sys
import re
from typing import List, Tuple

# Required variables
REQUIRED_VARS = [
    'JWT_SECRET',
    'ENCRYPTION_KEY',
    'PG_ENCRYPT_KEY',
    'POSTGRES_PASSWORD',
    'NEO4J_PASSWORD',
    'MINIO_ROOT_PASSWORD',
]

# Variables that should not contain CHANGE_ME
NO_CHANGE_ME_VARS = REQUIRED_VARS + [
    'GRAFANA_ADMIN_PASSWORD',
    'GRAFANA_SECRET_KEY',
]

def validate_env() -> Tuple[bool, List[str]]:
    """Validate environment variables."""
    errors = []
    
    # Check required variables
    for var in REQUIRED_VARS:
        if not os.getenv(var):
            errors.append(f"Missing required variable: {var}")
    
    # Check for CHANGE_ME placeholders
    for var in NO_CHANGE_ME_VARS:
        value = os.getenv(var, '')
        if 'CHANGE_ME' in value:
            errors.append(f"Variable {var} contains CHANGE_ME placeholder")
    
    # Validate JWT_SECRET length (should be 32+ bytes)
    jwt_secret = os.getenv('JWT_SECRET', '')
    if jwt_secret and len(jwt_secret) < 32:
        errors.append("JWT_SECRET should be at least 32 characters")
    
    # Validate ENCRYPTION_KEY format (Fernet key)
    encryption_key = os.getenv('ENCRYPTION_KEY', '')
    if encryption_key:
        try:
            from cryptography.fernet import Fernet
            Fernet(encryption_key.encode())
        except Exception:
            errors.append("ENCRYPTION_KEY is not a valid Fernet key")
    
    # Validate PG_ENCRYPT_KEY format (hex)
    pg_key = os.getenv('PG_ENCRYPT_KEY', '')
    if pg_key and not re.match(r'^[0-9a-fA-F]{64}$', pg_key):
        errors.append("PG_ENCRYPT_KEY should be 64 hex characters")
    
    # Validate password strength
    for var in ['POSTGRES_PASSWORD', 'NEO4J_PASSWORD', 'MINIO_ROOT_PASSWORD']:
        password = os.getenv(var, '')
        if password and len(password) < 16:
            errors.append(f"{var} should be at least 16 characters")
    
    return len(errors) == 0, errors

if __name__ == '__main__':
    success, errors = validate_env()
    
    if success:
        print("✅ Environment validation passed!")
        sys.exit(0)
    else:
        print("❌ Environment validation failed:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(1)
```

### Testing Configuration

```bash
# Run validation
python scripts/validate_env.py

# Test database connection
python scripts/test_db_connection.py

# Test Redis connection
python scripts/test_redis_connection.py

# Test all services
docker-compose up -d
docker-compose ps
python scripts/test_all_services.py
```

---

## Troubleshooting

### Common Issues

#### 1. "Missing required variable" Error

**Problem:** Required environment variable not set

**Solution:**
```bash
# Check which variables are missing
python scripts/validate_env.py

# Set missing variable
export VARIABLE_NAME=value

# Or add to .env file
echo "VARIABLE_NAME=value" >> .env
```

#### 2. "Invalid Fernet key" Error

**Problem:** ENCRYPTION_KEY is not a valid Fernet key

**Solution:**
```bash
# Generate new Fernet key
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# Update .env file
# ENCRYPTION_KEY=<generated-key>
```

#### 3. Database Connection Failed

**Problem:** Cannot connect to PostgreSQL

**Solution:**
```bash
# Check PostgreSQL is running
docker-compose ps postgres

# Check connection parameters
echo $POSTGRES_HOST
echo $POSTGRES_PORT
echo $POSTGRES_USER

# Test connection
psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB
```

#### 4. "CHANGE_ME" Placeholder Still Present

**Problem:** Configuration contains placeholder values

**Solution:**
```bash
# Find all CHANGE_ME placeholders
grep -r "CHANGE_ME" .env

# Replace with actual values
# Use the secret generation commands from Quick Start section
```

#### 5. Permission Denied Errors

**Problem:** Application cannot read .env file

**Solution:**
```bash
# Check file permissions
ls -la .env

# Fix permissions (owner read/write only)
chmod 600 .env

# Verify
ls -la .env
# Should show: -rw------- 1 user user ...
```

### Debug Mode

**Enable debug logging:**

```bash
# Set in .env
DEBUG=true
LOG_LEVEL=debug

# Restart services
docker-compose restart
```

**View logs:**

```bash
# API logs
docker-compose logs -f api

# All logs
docker-compose logs -f

# Specific service
docker-compose logs -f postgres
```

---

## Checklist

### Pre-Deployment Checklist

- [ ] All `CHANGE_ME` placeholders replaced
- [ ] All required variables set
- [ ] Secrets generated using cryptographically secure methods
- [ ] Passwords meet strength requirements (16+ chars)
- [ ] JWT_SECRET is 32+ characters
- [ ] ENCRYPTION_KEY is valid Fernet key
- [ ] PG_ENCRYPT_KEY is 64 hex characters
- [ ] Database passwords are strong and unique
- [ ] API keys obtained and configured
- [ ] Environment validation script passes
- [ ] .env file permissions set to 600
- [ ] .env file NOT committed to git
- [ ] Secrets stored in secure vault
- [ ] Backup of .env file created
- [ ] Team members have access to required secrets
- [ ] Monitoring credentials configured
- [ ] HTTPS/TLS certificates configured
- [ ] Firewall rules configured
- [ ] Backup schedule configured

### Post-Deployment Checklist

- [ ] All services started successfully
- [ ] Health checks passing
- [ ] Database migrations applied
- [ ] Monitoring dashboards accessible
- [ ] Logs flowing to aggregation system
- [ ] Alerts configured and tested
- [ ] Backup job running successfully
- [ ] Performance metrics within SLA targets
- [ ] Security scan completed
- [ ] Penetration test completed
- [ ] HIPAA compliance audit completed
- [ ] Documentation updated
- [ ] Team trained on new configuration
- [ ] Incident response plan updated
- [ ] Secret rotation schedule documented

---

## Additional Resources

- [12-Factor App Methodology](https://12factor.net/)
- [OWASP Secrets Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Secrets_Management_Cheat_Sheet.html)
- [NIST Password Guidelines](https://pages.nist.gov/800-63-3/sp800-63b.html)
- [HashiCorp Vault Documentation](https://www.vaultproject.io/docs)
- [AWS Secrets Manager Documentation](https://docs.aws.amazon.com/secretsmanager/)
- [Kubernetes Secrets Documentation](https://kubernetes.io/docs/concepts/configuration/secret/)

---

**Document Version:** 1.0  
**Last Updated:** April 23, 2026  
**Maintained By:** DevOps Team  
**Review Schedule:** Quarterly

# Next Account Start - Setup Guide

**Purpose:** Complete setup guide for a fresh clone of the Drug Designer repository.

**Last Updated:** 2026-04-24

---

## Prerequisites

### Required Software

1. **Docker & Docker Compose**
   - Docker 24.0 or later
   - Docker Compose 2.23 or later
   - Installation: https://docs.docker.com/get-docker/

2. **Python**
   - Python 3.11 or later
   - pip 23.0 or later
   - Installation: https://www.python.org/downloads/

3. **Node.js & npm**
   - Node.js 18.0 or later
   - npm 9.0 or later
   - Installation: https://nodejs.org/

4. **Git**
   - Git 2.40 or later
   - Installation: https://git-scm.com/downloads

### System Requirements

- **RAM:** 16GB minimum, 32GB recommended
- **Disk Space:** 100GB minimum (for models and data)
- **CPU:** 4 cores minimum, 8 cores recommended
- **OS:** Linux, macOS, or Windows with WSL2

### Optional Tools

- **VS Code:** Recommended IDE with Python and TypeScript extensions
- **Postman:** For API testing
- **pgAdmin:** For PostgreSQL management
- **Neo4j Browser:** For graph visualization (included in Neo4j)

---

## Step 1: Clone Repository

```bash
# Clone the repository
git clone <repository-url>
cd drug-designer

# Verify repository structure
ls -la
# Should see: apps/, tests/, docs/, docker-compose.yml, .env.example, etc.
```

---

## Step 2: Environment Configuration

### Backend Environment

```bash
# Copy backend environment template
cp apps/api/.env.example apps/api/.env

# Edit apps/api/.env with your configuration
nano apps/api/.env  # or use your preferred editor
```

**Required Environment Variables:**

```bash
# Database
DATABASE_URL=postgresql://drugdesigner:password@localhost:5432/drugdesigner

# Neo4j
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_neo4j_password

# Qdrant
QDRANT_URL=http://localhost:6333

# Redis
REDIS_URL=redis://localhost:6379/0

# S3/MinIO
S3_BUCKET=drug-designer-artifacts
S3_ENDPOINT=http://localhost:9000
S3_ACCESS_KEY=minioadmin
S3_SECRET_KEY=minioadmin

# ML Models
MODEL_CACHE_DIR=data/models

# Security
JWT_SECRET=your_jwt_secret_here_change_in_production
JWT_ALGORITHM=HS256
JWT_EXPIRATION_MINUTES=1440

# Monitoring
SENTRY_DSN=your_sentry_dsn_here  # Optional

# Feature Flags
INDIA_POPULATION_WEIGHT=0.15
```

### Root Environment

```bash
# Copy root environment template
cp .env.example .env

# Edit .env (usually same as apps/api/.env)
nano .env
```

---

## Step 3: Start Infrastructure

```bash
# Start all infrastructure services
docker-compose up -d

# Wait for services to be healthy (takes ~30 seconds)
docker-compose ps

# Expected output:
# NAME                STATUS              PORTS
# postgres            Up (healthy)        5432
# neo4j               Up (healthy)        7474, 7687
# qdrant              Up (healthy)        6333
# redis               Up (healthy)        6379
# minio               Up (healthy)        9000, 9001

# Check logs if any service is unhealthy
docker-compose logs <service-name>
```

### Verify Infrastructure

```bash
# PostgreSQL
docker exec -it postgres psql -U drugdesigner -d drugdesigner -c "SELECT version();"

# Neo4j (open browser)
open http://localhost:7474
# Login with neo4j / your_neo4j_password

# Qdrant
curl http://localhost:6333/collections

# Redis
docker exec -it redis redis-cli ping
# Should return: PONG

# MinIO (open browser)
open http://localhost:9001
# Login with minioadmin / minioadmin
```

---

## Step 4: Backend Setup

### Install Python Dependencies

```bash
cd apps/api

# Create virtual environment
python -m venv .venv

# Activate virtual environment
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Upgrade pip
pip install --upgrade pip

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -c "import fastapi; print(fastapi.__version__)"
```

### Download ML Model Weights

```bash
# Download all model weights (~4GB, takes 10-20 minutes)
python scripts/download_models.py

# Or download specific models
python scripts/download_models.py --skip-esm2  # Skip ESM-2 (largest)

# Verify weights downloaded
ls -lh data/models/
# Should see: esm2_t33_650M_UR50D/, MolFormer-XL-both-10pct/, scibert_scivocab_uncased/, biobert-v1.1/
```

### Run Database Migrations

```bash
# Apply all migrations
alembic upgrade head

# Verify migrations
alembic current
# Should show: 0006_runtime_local_agent (head)

# Check tables created
docker exec -it postgres psql -U drugdesigner -d drugdesigner -c "\dt"
# Should see 43 tables
```

### Populate Knowledge Graph (Optional)

```bash
# This step is optional but recommended for full functionality
# Takes ~2 hours and requires ~10GB disk space

python scripts/populate_graph.py

# Or populate specific sources
python scripts/populate_graph.py --sources kegg,reactome,string

# Verify graph populated
# Open Neo4j Browser: http://localhost:7474
# Run query: MATCH (n) RETURN count(n)
# Should see ~100K nodes
```

### Start Backend Server

```bash
# Start backend (development mode with auto-reload)
python run_server.py

# Or use uvicorn directly
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Backend should be running on http://localhost:8000
```

### Verify Backend

```bash
# In a new terminal, test health endpoint
curl http://localhost:8000/api/v1/health

# Expected response:
# {"status":"healthy","timestamp":"2026-04-24T...","services":{"postgres":"up","neo4j":"up","qdrant":"up","redis":"up"}}

# Open API documentation
open http://localhost:8000/api/docs

# Test authentication (create user first via /api/v1/auth/register)
```

---

## Step 5: Frontend Setup

### Install Node Dependencies

```bash
# In a new terminal
cd apps/web

# Install dependencies
npm install

# Verify installation
npm list react
```

### Start Frontend Server

```bash
# Start frontend (development mode with hot reload)
npm run dev

# Frontend should be running on http://localhost:5173
```

### Verify Frontend

```bash
# Open frontend in browser
open http://localhost:5173

# You should see the Drug Designer login page

# Test login (use credentials from backend registration)
```

---

## Step 6: Run Tests

### Backend Tests

```bash
cd apps/api

# Run all tests
pytest tests/ -v

# Run specific test suites
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/failure_drills/ -v

# Run with coverage
pytest --cov=. --cov-report=html tests/
open htmlcov/index.html
```

### Frontend Tests

```bash
cd apps/web

# Run unit tests
npm test

# Run E2E tests (requires backend running)
npm run cypress:open  # Interactive mode
npm run cypress:run   # Headless mode

# Run with coverage
npm test -- --coverage
open coverage/index.html
```

---

## Step 7: Verify Complete Setup

### Checklist

- [ ] All infrastructure services running (postgres, neo4j, qdrant, redis, minio)
- [ ] Backend server running on http://localhost:8000
- [ ] Frontend server running on http://localhost:5173
- [ ] API documentation accessible at http://localhost:8000/api/docs
- [ ] Health endpoint returns "healthy" status
- [ ] ML model weights downloaded to data/models/
- [ ] Database migrations applied (43 tables)
- [ ] Knowledge graph populated (optional)
- [ ] Backend tests passing
- [ ] Frontend tests passing
- [ ] Can login to frontend
- [ ] Can create a project in frontend

### End-to-End Test

```bash
# 1. Open frontend
open http://localhost:5173

# 2. Register a new user
# Click "Sign Up" and create account

# 3. Login with new credentials

# 4. Create a new project
# Click "New Project" and fill in details

# 5. Run disease intelligence workflow
# Navigate to "Disease Intelligence"
# Enter a disease name (e.g., "Alzheimer's disease")
# Click "Run Analysis"
# Watch real-time progress via WebSocket

# 6. View results
# Check evidence aggregation
# View knowledge graph
# Export dossier as PDF

# If all steps work, setup is complete! ✅
```

---

## Common Issues & Troubleshooting

### Issue: Docker services not starting

**Symptoms:**
- `docker-compose ps` shows services as "unhealthy" or "exited"

**Solutions:**
```bash
# Check logs
docker-compose logs <service-name>

# Restart specific service
docker-compose restart <service-name>

# Restart all services
docker-compose down
docker-compose up -d

# Check disk space
df -h

# Check Docker resources (RAM, CPU)
docker stats
```

### Issue: Backend fails to start

**Symptoms:**
- `python run_server.py` crashes
- Import errors

**Solutions:**
```bash
# Verify virtual environment activated
which python  # Should point to .venv/bin/python

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall

# Check environment variables
cat apps/api/.env

# Check database connection
docker exec -it postgres psql -U drugdesigner -d drugdesigner -c "SELECT 1;"

# Check logs
tail -f apps/api/logs/app.log
```

### Issue: Frontend fails to start

**Symptoms:**
- `npm run dev` crashes
- Module not found errors

**Solutions:**
```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Clear Vite cache
rm -rf node_modules/.vite

# Check Node version
node --version  # Should be 18+

# Check backend is running
curl http://localhost:8000/api/v1/health
```

### Issue: Model weights download fails

**Symptoms:**
- `python scripts/download_models.py` fails
- Network errors

**Solutions:**
```bash
# Check internet connection
ping huggingface.co

# Download models individually
python scripts/download_models.py --skip-esm2
python scripts/download_models.py --skip-molformer
python scripts/download_models.py --skip-scibert
python scripts/download_models.py --skip-biobert

# Check disk space
df -h

# Manually download from HuggingFace Hub
# Visit: https://huggingface.co/facebook/esm2_t33_650M_UR50D
# Download files to data/models/esm2_t33_650M_UR50D/
```

### Issue: Database migrations fail

**Symptoms:**
- `alembic upgrade head` fails
- Table already exists errors

**Solutions:**
```bash
# Check current migration
alembic current

# Rollback and retry
alembic downgrade base
alembic upgrade head

# Reset database (WARNING: deletes all data)
docker-compose down -v
docker-compose up -d postgres
alembic upgrade head

# Check PostgreSQL logs
docker-compose logs postgres
```

### Issue: Neo4j connection fails

**Symptoms:**
- Backend logs show Neo4j connection errors
- Graph queries fail

**Solutions:**
```bash
# Check Neo4j is running
docker-compose ps neo4j

# Check Neo4j logs
docker-compose logs neo4j

# Restart Neo4j
docker-compose restart neo4j

# Verify credentials in .env
cat apps/api/.env | grep NEO4J

# Test connection
docker exec -it neo4j cypher-shell -u neo4j -p your_password "RETURN 1;"
```

### Issue: Qdrant collections not created

**Symptoms:**
- Backend logs show Qdrant errors
- Vector search fails

**Solutions:**
```bash
# Check Qdrant is running
docker-compose ps qdrant

# Check Qdrant logs
docker-compose logs qdrant

# Manually create collections
python -c "from apps.api.core.vector_store import ensure_spec_collections; ensure_spec_collections()"

# Verify collections
curl http://localhost:6333/collections
```

---

## Development Workflow

### Daily Development

```bash
# 1. Start infrastructure (if not running)
docker-compose up -d

# 2. Start backend
cd apps/api
source .venv/bin/activate
python run_server.py

# 3. Start frontend (in new terminal)
cd apps/web
npm run dev

# 4. Make changes to code

# 5. Run tests
pytest tests/  # Backend
npm test       # Frontend

# 6. Commit changes
git add .
git commit -m "Description of changes"
git push
```

### Adding New Features

1. **Create feature branch**
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Implement feature**
   - Backend: Add endpoint in `apps/api/routers/`
   - Frontend: Add page in `apps/web/src/pages/`
   - Tests: Add tests in `tests/`

3. **Run tests**
   ```bash
   pytest tests/
   npm test
   ```

4. **Commit and push**
   ```bash
   git add .
   git commit -m "Add my new feature"
   git push origin feature/my-new-feature
   ```

5. **Create pull request**
   - Open PR on GitHub
   - Wait for CI/CD checks (Phase I)
   - Request code review

---

## Production Deployment

### Prerequisites

- Kubernetes cluster or cloud provider (AWS, GCP, Azure)
- Domain name and SSL certificate
- Production database (managed PostgreSQL)
- Production Neo4j instance
- Production Qdrant instance
- Production Redis instance
- S3-compatible storage (AWS S3, MinIO)

### Deployment Steps

```bash
# 1. Build Docker images
docker-compose -f docker-compose.prod.yml build

# 2. Push to container registry
docker-compose -f docker-compose.prod.yml push

# 3. Deploy to Kubernetes (example)
kubectl apply -f k8s/

# 4. Run migrations
kubectl exec -it <api-pod> -- alembic upgrade head

# 5. Verify deployment
curl https://api.drugdesigner.ai/api/v1/health

# 6. Monitor logs
kubectl logs -f deployment/api
```

### Production Checklist

- [ ] Environment variables configured
- [ ] Database migrations applied
- [ ] ML model weights available
- [ ] SSL certificate installed
- [ ] Monitoring configured (Prometheus, Grafana, Sentry)
- [ ] Backup strategy in place
- [ ] Disaster recovery plan documented
- [ ] Security audit completed (Phase K)
- [ ] Performance testing completed (Phase J)
- [ ] CI/CD pipeline operational (Phase I)

---

## Additional Resources

### Documentation

- **Architecture Spec:** `Drug_Designer.md` (11,297 lines)
- **API Docs:** http://localhost:8000/api/docs
- **Living Docs:** `docs/current/`
- **Handoff Doc:** `docs/FINAL_BATON.md`

### External Resources

- **FastAPI:** https://fastapi.tiangolo.com
- **React:** https://react.dev
- **Neo4j:** https://neo4j.com/docs
- **Qdrant:** https://qdrant.tech/documentation
- **PyTorch:** https://pytorch.org/docs
- **HuggingFace:** https://huggingface.co/docs
- **Docker:** https://docs.docker.com
- **Alembic:** https://alembic.sqlalchemy.org

### Community

- **GitHub Issues:** <repository-url>/issues
- **Slack:** #drug-designer (placeholder)
- **Email:** support@drugdesigner.ai (placeholder)

---

## Next Steps

After completing this setup guide:

1. **Explore the codebase**
   - Read `Drug_Designer.md` for architecture overview
   - Browse `apps/api/routers/` for API endpoints
   - Browse `apps/web/src/pages/` for frontend pages

2. **Run example workflows**
   - Disease intelligence
   - Target prioritization
   - Molecule generation
   - Dossier export

3. **Complete remaining phases**
   - Phase H: Living documentation (in progress)
   - Phase I: CI/CD pipeline
   - Phase J: Performance profiling
   - Phase K: Security hardening

4. **Contribute**
   - Fix bugs
   - Add features
   - Improve documentation
   - Write tests

---

**Setup Guide Version:** 1.0.0
**Last Updated:** 2026-04-24
**Status:** Complete

**Welcome to Drug Designer! Happy coding! 🚀**

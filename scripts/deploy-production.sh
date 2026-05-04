#!/bin/bash
# Drug Designer — Production Deployment Script
# Task 23.1: Automated production deployment

set -e

echo "═══════════════════════════════════════════════════════════"
echo "Drug Designer — Production Deployment"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if .env.prod exists
if [ ! -f .env.prod ]; then
    echo -e "${RED}Error: .env.prod file not found!${NC}"
    echo "Please copy .env.prod.example to .env.prod and configure it."
    exit 1
fi

# Check Docker and Docker Compose
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker is not installed!${NC}"
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: Docker Compose is not installed!${NC}"
    exit 1
fi

echo -e "${GREEN}✓${NC} Prerequisites check passed"
echo ""

# Load environment variables
source .env.prod

# Validate required environment variables
REQUIRED_VARS=(
    "POSTGRES_USER"
    "POSTGRES_PASSWORD"
    "NEO4J_PASSWORD"
    "MINIO_ROOT_USER"
    "MINIO_ROOT_PASSWORD"
    "JWT_SECRET"
    "PG_ENCRYPT_KEY"
    "GRAFANA_ADMIN_PASSWORD"
    "GRAFANA_SECRET_KEY"
)

echo "Validating environment variables..."
for var in "${REQUIRED_VARS[@]}"; do
    if [ -z "${!var}" ]; then
        echo -e "${RED}Error: $var is not set in .env.prod${NC}"
        exit 1
    fi
done
echo -e "${GREEN}✓${NC} Environment variables validated"
echo ""

# Create necessary directories
echo "Creating directories..."
mkdir -p backups/postgres
mkdir -p backups/neo4j
mkdir -p monitoring/prometheus/alerts
mkdir -p monitoring/grafana/provisioning/datasources
mkdir -p monitoring/grafana/provisioning/dashboards
mkdir -p monitoring/grafana/dashboards
mkdir -p monitoring/loki
mkdir -p monitoring/promtail
echo -e "${GREEN}✓${NC} Directories created"
echo ""

# Pull latest images
echo "Pulling Docker images..."
docker-compose -f docker-compose.prod.yml --env-file .env.prod pull
echo -e "${GREEN}✓${NC} Images pulled"
echo ""

# Start services
echo "Starting services..."
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d
echo -e "${GREEN}✓${NC} Services started"
echo ""

# Wait for services to be healthy
echo "Waiting for services to be healthy..."
sleep 10

# Check service health
echo "Checking service health..."
SERVICES=("postgres" "redis" "qdrant" "neo4j" "minio" "api" "web")
for service in "${SERVICES[@]}"; do
    echo -n "  Checking $service... "
    if docker-compose -f docker-compose.prod.yml --env-file .env.prod ps | grep -q "$service.*healthy\|$service.*Up"; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}⚠${NC} (may still be starting)"
    fi
done
echo ""

# Run database migrations
echo "Running database migrations..."
docker-compose -f docker-compose.prod.yml --env-file .env.prod exec -T api alembic upgrade head
echo -e "${GREEN}✓${NC} Migrations completed"
echo ""

# Display access information
echo "═══════════════════════════════════════════════════════════"
echo -e "${GREEN}Deployment Complete!${NC}"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Access the following services:"
echo ""
echo "  Application:      http://localhost:3000"
echo "  API Docs:         http://localhost:8000/docs"
echo "  Grafana:          http://localhost:3001"
echo "  Prometheus:       http://localhost:9090"
echo "  MinIO Console:    http://localhost:9001"
echo ""
echo "Grafana Credentials:"
echo "  Username: admin"
echo "  Password: (from GRAFANA_ADMIN_PASSWORD in .env.prod)"
echo ""
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Useful commands:"
echo "  View logs:        docker-compose -f docker-compose.prod.yml logs -f"
echo "  Stop services:    docker-compose -f docker-compose.prod.yml down"
echo "  Restart service:  docker-compose -f docker-compose.prod.yml restart <service>"
echo "  Service status:   docker-compose -f docker-compose.prod.yml ps"
echo ""

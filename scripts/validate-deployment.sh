#!/bin/bash
# Drug Designer — Deployment Validation Script
# Task 23.1: Validate production deployment configuration

set -e

echo "═══════════════════════════════════════════════════════════"
echo "Drug Designer — Deployment Validation"
echo "═══════════════════════════════════════════════════════════"
echo ""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

ERRORS=0
WARNINGS=0

# Function to check service health
check_service() {
    local service=$1
    local url=$2
    
    echo -n "Checking $service... "
    if curl -f -s -o /dev/null "$url"; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        ((ERRORS++))
    fi
}

# Function to check port
check_port() {
    local port=$1
    local service=$2
    
    echo -n "Checking port $port ($service)... "
    if nc -z localhost $port 2>/dev/null; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        ((ERRORS++))
    fi
}

# Check if services are running
echo "Checking Docker services..."
SERVICES=("api" "web" "worker" "postgres" "redis" "qdrant" "neo4j" "minio" "prometheus" "grafana" "loki")
for service in "${SERVICES[@]}"; do
    echo -n "  $service... "
    if docker-compose -f docker-compose.prod.yml ps | grep -q "$service.*Up"; then
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${RED}✗${NC}"
        ((ERRORS++))
    fi
done
echo ""

# Check service endpoints
echo "Checking service endpoints..."
check_service "API Health" "http://localhost:8000/api/health"
check_service "Web Frontend" "http://localhost:3000"
check_service "Prometheus" "http://localhost:9090/-/healthy"
check_service "Grafana" "http://localhost:3001/api/health"
check_service "MinIO" "http://localhost:9000/minio/health/live"
echo ""

# Check database connectivity
echo "Checking database connectivity..."
echo -n "PostgreSQL... "
if docker-compose -f docker-compose.prod.yml exec -T postgres pg_isready -U drugdesigner &>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    ((ERRORS++))
fi

echo -n "Redis... "
if docker-compose -f docker-compose.prod.yml exec -T redis redis-cli ping &>/dev/null; then
    echo -e "${GREEN}✓${NC}"
else
    echo -e "${RED}✗${NC}"
    ((ERRORS++))
fi
echo ""

# Check resource usage
echo "Checking resource usage..."
echo -n "Docker disk usage... "
DISK_USAGE=$(docker system df --format "{{.Size}}" | head -1)
echo "$DISK_USAGE"

echo -n "Container count... "
CONTAINER_COUNT=$(docker ps -q | wc -l)
echo "$CONTAINER_COUNT"
echo ""

# Check logs for errors
echo "Checking recent logs for errors..."
ERROR_COUNT=$(docker-compose -f docker-compose.prod.yml logs --tail=100 2>&1 | grep -i "error\|exception\|fatal" | wc -l)
if [ $ERROR_COUNT -gt 0 ]; then
    echo -e "${YELLOW}⚠${NC} Found $ERROR_COUNT error messages in recent logs"
    ((WARNINGS++))
else
    echo -e "${GREEN}✓${NC} No errors in recent logs"
fi
echo ""

# Summary
echo "═══════════════════════════════════════════════════════════"
if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✓ All checks passed!${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ Validation completed with $WARNINGS warnings${NC}"
    exit 0
else
    echo -e "${RED}✗ Validation failed with $ERRORS errors and $WARNINGS warnings${NC}"
    exit 1
fi

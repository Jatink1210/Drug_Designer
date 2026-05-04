#!/bin/bash

# ═══════════════════════════════════════════════════════════
# Drug Designer Deployment Script
# ═══════════════════════════════════════════════════════════
#
# Task 24.2: Automated deployment with zero downtime
#
# Usage:
#   ./scripts/deploy.sh <environment> [options]
#
# Environments:
#   staging     - Deploy to staging environment
#   production  - Deploy to production environment
#
# Options:
#   --skip-backup       Skip database backup
#   --skip-tests        Skip smoke tests
#   --skip-migrations   Skip database migrations
#   --force             Force deployment without confirmation
#
# Examples:
#   ./scripts/deploy.sh staging
#   ./scripts/deploy.sh production --force
#   ./scripts/deploy.sh staging --skip-backup --skip-tests

set -euo pipefail

# ═══════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default options
SKIP_BACKUP=false
SKIP_TESTS=false
SKIP_MIGRATIONS=false
FORCE=false

# ═══════════════════════════════════════════════════════════
# Helper Functions
# ═══════════════════════════════════════════════════════════

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}$1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

confirm() {
    if [ "$FORCE" = true ]; then
        return 0
    fi
    
    read -p "$1 (y/n): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_error "Deployment cancelled by user"
        exit 1
    fi
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        log_error "Required command '$1' not found. Please install it first."
        exit 1
    fi
}

# ═══════════════════════════════════════════════════════════
# Parse Arguments
# ═══════════════════════════════════════════════════════════

if [ $# -lt 1 ]; then
    log_error "Usage: $0 <environment> [options]"
    log_info "Environments: staging, production"
    log_info "Options: --skip-backup, --skip-tests, --skip-migrations, --force"
    exit 1
fi

ENVIRONMENT=$1
shift

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-backup)
            SKIP_BACKUP=true
            shift
            ;;
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-migrations)
            SKIP_MIGRATIONS=true
            shift
            ;;
        --force)
            FORCE=true
            shift
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Validate environment
if [[ "$ENVIRONMENT" != "staging" && "$ENVIRONMENT" != "production" ]]; then
    log_error "Invalid environment: $ENVIRONMENT"
    log_info "Valid environments: staging, production"
    exit 1
fi

# ═══════════════════════════════════════════════════════════
# Pre-flight Checks
# ═══════════════════════════════════════════════════════════

print_header "Pre-flight Checks"

log_info "Checking required commands..."
check_command "docker"
check_command "docker-compose"
check_command "git"
check_command "curl"

log_info "Checking Docker daemon..."
if ! docker info &> /dev/null; then
    log_error "Docker daemon is not running"
    exit 1
fi

log_info "Checking Git repository..."
if [ ! -d "$PROJECT_ROOT/.git" ]; then
    log_error "Not a Git repository"
    exit 1
fi

# Check for uncommitted changes
if [ -n "$(git status --porcelain)" ]; then
    log_warning "You have uncommitted changes"
    confirm "Continue with deployment?"
fi

# Get current commit
COMMIT_SHA=$(git rev-parse HEAD)
COMMIT_SHORT=$(git rev-parse --short HEAD)
BRANCH=$(git rev-parse --abbrev-ref HEAD)

log_info "Environment: $ENVIRONMENT"
log_info "Branch: $BRANCH"
log_info "Commit: $COMMIT_SHORT"

# Confirm deployment
if [ "$ENVIRONMENT" = "production" ]; then
    log_warning "You are about to deploy to PRODUCTION"
    confirm "Are you sure you want to continue?"
fi

log_success "Pre-flight checks passed"

# ═══════════════════════════════════════════════════════════
# Load Environment Configuration
# ═══════════════════════════════════════════════════════════

print_header "Loading Configuration"

ENV_FILE=".env.$ENVIRONMENT"
if [ ! -f "$PROJECT_ROOT/$ENV_FILE" ]; then
    log_error "Environment file not found: $ENV_FILE"
    exit 1
fi

log_info "Loading environment from $ENV_FILE"
set -a
source "$PROJECT_ROOT/$ENV_FILE"
set +a

COMPOSE_FILE="docker-compose.$ENVIRONMENT.yml"
if [ ! -f "$PROJECT_ROOT/$COMPOSE_FILE" ]; then
    log_error "Docker Compose file not found: $COMPOSE_FILE"
    exit 1
fi

log_success "Configuration loaded"

# ═══════════════════════════════════════════════════════════
# Backup Database
# ═══════════════════════════════════════════════════════════

if [ "$SKIP_BACKUP" = false ]; then
    print_header "Creating Database Backup"
    
    BACKUP_DIR="$PROJECT_ROOT/backups"
    mkdir -p "$BACKUP_DIR"
    
    BACKUP_FILE="$BACKUP_DIR/pre-deploy-$(date +%Y%m%d-%H%M%S).sql.gz"
    
    log_info "Backing up database to $BACKUP_FILE"
    
    docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" exec -T postgres \
        pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$BACKUP_FILE"
    
    if [ -f "$BACKUP_FILE" ]; then
        BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
        log_success "Database backup created ($BACKUP_SIZE)"
    else
        log_error "Database backup failed"
        exit 1
    fi
    
    # Backup current deployment configuration
    DEPLOY_BACKUP="$BACKUP_DIR/deployment-$(date +%Y%m%d-%H%M%S).tar.gz"
    tar -czf "$DEPLOY_BACKUP" -C "$PROJECT_ROOT" \
        "$COMPOSE_FILE" "$ENV_FILE" 2>/dev/null || true
    
    log_success "Deployment configuration backed up"
else
    log_warning "Skipping database backup (--skip-backup)"
fi

# ═══════════════════════════════════════════════════════════
# Pull Latest Images
# ═══════════════════════════════════════════════════════════

print_header "Pulling Latest Docker Images"

log_info "Pulling images from registry..."

docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" pull

log_success "Images pulled successfully"

# ═══════════════════════════════════════════════════════════
# Run Database Migrations
# ═══════════════════════════════════════════════════════════

if [ "$SKIP_MIGRATIONS" = false ]; then
    print_header "Running Database Migrations"
    
    log_info "Running Alembic migrations..."
    
    docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" run --rm api \
        alembic upgrade head
    
    log_success "Database migrations completed"
else
    log_warning "Skipping database migrations (--skip-migrations)"
fi

# ═══════════════════════════════════════════════════════════
# Deploy Services (Zero Downtime)
# ═══════════════════════════════════════════════════════════

print_header "Deploying Services"

log_info "Starting zero-downtime deployment..."

if [ "$ENVIRONMENT" = "production" ]; then
    # Production: Rolling update with scaling
    log_info "Scaling up new instances..."
    docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" up -d \
        --no-deps --scale api=4 --scale web=2 --no-recreate api web
    
    log_info "Waiting for new instances to be healthy (60s)..."
    sleep 60
    
    log_info "Scaling down old instances..."
    docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" up -d \
        --no-deps --scale api=2 --scale web=1 api web
    
    log_info "Waiting for stabilization (30s)..."
    sleep 30
else
    # Staging: Simple rolling update
    log_info "Updating services..."
    docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" up -d \
        --no-deps --build api web
    
    log_info "Waiting for services to start (30s)..."
    sleep 30
fi

log_success "Services deployed"

# ═══════════════════════════════════════════════════════════
# Health Checks
# ═══════════════════════════════════════════════════════════

print_header "Running Health Checks"

log_info "Checking API health..."

MAX_RETRIES=10
RETRY_COUNT=0
HEALTH_URL="http://localhost:8000/api/health"

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -f -s "$HEALTH_URL" > /dev/null; then
        log_success "API health check passed"
        break
    else
        RETRY_COUNT=$((RETRY_COUNT + 1))
        log_warning "Health check failed (attempt $RETRY_COUNT/$MAX_RETRIES)"
        sleep 5
    fi
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    log_error "API health check failed after $MAX_RETRIES attempts"
    log_error "Deployment may have failed. Check logs with: docker-compose logs api"
    exit 1
fi

# ═══════════════════════════════════════════════════════════
# Smoke Tests
# ═══════════════════════════════════════════════════════════

if [ "$SKIP_TESTS" = false ]; then
    print_header "Running Smoke Tests"
    
    log_info "Testing critical endpoints..."
    
    # Test health endpoint
    if curl -f -s "http://localhost:8000/api/health" > /dev/null; then
        log_success "✓ Health endpoint"
    else
        log_error "✗ Health endpoint failed"
        exit 1
    fi
    
    # Test deep health check
    if curl -f -s "http://localhost:8000/api/health/deep" > /dev/null; then
        log_success "✓ Deep health check"
    else
        log_warning "✗ Deep health check failed (non-critical)"
    fi
    
    # Test database connectivity
    if curl -f -s "http://localhost:8000/api/health/db" > /dev/null; then
        log_success "✓ Database connectivity"
    else
        log_error "✗ Database connectivity failed"
        exit 1
    fi
    
    # Test authentication endpoint
    if curl -f -s "http://localhost:8000/api/auth/health" > /dev/null; then
        log_success "✓ Authentication service"
    else
        log_warning "✗ Authentication service failed (non-critical)"
    fi
    
    log_success "Smoke tests passed"
else
    log_warning "Skipping smoke tests (--skip-tests)"
fi

# ═══════════════════════════════════════════════════════════
# Cleanup
# ═══════════════════════════════════════════════════════════

print_header "Cleanup"

log_info "Removing unused Docker images..."
docker image prune -f

log_info "Removing old backups (keeping last 30 days)..."
find "$PROJECT_ROOT/backups" -name "*.sql.gz" -mtime +30 -delete 2>/dev/null || true
find "$PROJECT_ROOT/backups" -name "*.tar.gz" -mtime +30 -delete 2>/dev/null || true

log_success "Cleanup completed"

# ═══════════════════════════════════════════════════════════
# Deployment Summary
# ═══════════════════════════════════════════════════════════

print_header "Deployment Summary"

echo ""
echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo ""
echo "Environment:  $ENVIRONMENT"
echo "Branch:       $BRANCH"
echo "Commit:       $COMMIT_SHORT"
echo "Timestamp:    $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

if [ "$ENVIRONMENT" = "staging" ]; then
    echo "URL: https://staging.drugdesigner.com"
elif [ "$ENVIRONMENT" = "production" ]; then
    echo "URL: https://drugdesigner.com"
fi

echo ""
echo "Next steps:"
echo "  - Monitor logs: docker-compose -f $COMPOSE_FILE logs -f"
echo "  - Check metrics: https://monitoring.drugdesigner.com"
echo "  - Run validation tests: ./scripts/validate_deployment.sh $ENVIRONMENT"
echo ""

log_success "Deployment script completed"

exit 0

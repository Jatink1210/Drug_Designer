#!/bin/bash

# ═══════════════════════════════════════════════════════════
# Drug Designer Rollback Script
# ═══════════════════════════════════════════════════════════
#
# Task 24.2: Automated rollback to previous deployment
#
# Usage:
#   ./scripts/rollback.sh <environment> [options]
#
# Environments:
#   staging     - Rollback staging environment
#   production  - Rollback production environment
#
# Options:
#   --backup <file>     Specific backup file to restore
#   --skip-db           Skip database restore
#   --force             Force rollback without confirmation
#
# Examples:
#   ./scripts/rollback.sh staging
#   ./scripts/rollback.sh production --force
#   ./scripts/rollback.sh production --backup backups/pre-deploy-20260423-120000.sql.gz

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
BACKUP_FILE=""
SKIP_DB=false
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
        log_error "Rollback cancelled by user"
        exit 1
    fi
}

# ═══════════════════════════════════════════════════════════
# Parse Arguments
# ═══════════════════════════════════════════════════════════

if [ $# -lt 1 ]; then
    log_error "Usage: $0 <environment> [options]"
    log_info "Environments: staging, production"
    log_info "Options: --backup <file>, --skip-db, --force"
    exit 1
fi

ENVIRONMENT=$1
shift

# Parse options
while [[ $# -gt 0 ]]; do
    case $1 in
        --backup)
            BACKUP_FILE="$2"
            shift 2
            ;;
        --skip-db)
            SKIP_DB=true
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

print_header "Rollback Pre-flight Checks"

log_warning "You are about to ROLLBACK $ENVIRONMENT environment"
log_warning "This will restore the previous deployment and database state"
confirm "Are you sure you want to continue?"

# Load environment configuration
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

log_success "Pre-flight checks passed"

# ═══════════════════════════════════════════════════════════
# Find Latest Backup
# ═══════════════════════════════════════════════════════════

print_header "Locating Backup Files"

BACKUP_DIR="$PROJECT_ROOT/backups"

if [ -z "$BACKUP_FILE" ]; then
    # Find latest database backup
    BACKUP_FILE=$(ls -t "$BACKUP_DIR"/pre-deploy-*.sql.gz 2>/dev/null | head -1)
    
    if [ -z "$BACKUP_FILE" ]; then
        log_error "No backup files found in $BACKUP_DIR"
        log_info "Please specify a backup file with --backup option"
        exit 1
    fi
    
    log_info "Using latest backup: $(basename "$BACKUP_FILE")"
else
    if [ ! -f "$BACKUP_FILE" ]; then
        log_error "Backup file not found: $BACKUP_FILE"
        exit 1
    fi
    log_info "Using specified backup: $(basename "$BACKUP_FILE")"
fi

# Find latest deployment backup
DEPLOY_BACKUP=$(ls -t "$BACKUP_DIR"/deployment-*.tar.gz 2>/dev/null | head -1)

if [ -z "$DEPLOY_BACKUP" ]; then
    log_warning "No deployment backup found"
else
    log_info "Using deployment backup: $(basename "$DEPLOY_BACKUP")"
fi

# Show backup details
BACKUP_SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
BACKUP_DATE=$(stat -c %y "$BACKUP_FILE" 2>/dev/null || stat -f %Sm "$BACKUP_FILE" 2>/dev/null)

echo ""
echo "Backup Details:"
echo "  File: $(basename "$BACKUP_FILE")"
echo "  Size: $BACKUP_SIZE"
echo "  Date: $BACKUP_DATE"
echo ""

confirm "Proceed with rollback using this backup?"

# ═══════════════════════════════════════════════════════════
# Stop Current Services
# ═══════════════════════════════════════════════════════════

print_header "Stopping Current Services"

log_info "Stopping all services..."

docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" down

log_success "Services stopped"

# ═══════════════════════════════════════════════════════════
# Restore Deployment Configuration
# ═══════════════════════════════════════════════════════════

if [ -n "$DEPLOY_BACKUP" ]; then
    print_header "Restoring Deployment Configuration"
    
    log_info "Extracting deployment backup..."
    
    # Create temporary directory
    TEMP_DIR=$(mktemp -d)
    
    # Extract backup
    tar -xzf "$DEPLOY_BACKUP" -C "$TEMP_DIR"
    
    # Restore files
    if [ -f "$TEMP_DIR/$COMPOSE_FILE" ]; then
        cp "$TEMP_DIR/$COMPOSE_FILE" "$PROJECT_ROOT/$COMPOSE_FILE"
        log_success "Restored $COMPOSE_FILE"
    fi
    
    if [ -f "$TEMP_DIR/$ENV_FILE" ]; then
        cp "$TEMP_DIR/$ENV_FILE" "$PROJECT_ROOT/$ENV_FILE"
        log_success "Restored $ENV_FILE"
    fi
    
    # Cleanup
    rm -rf "$TEMP_DIR"
    
    log_success "Deployment configuration restored"
fi

# ═══════════════════════════════════════════════════════════
# Restore Database
# ═══════════════════════════════════════════════════════════

if [ "$SKIP_DB" = false ]; then
    print_header "Restoring Database"
    
    log_warning "This will OVERWRITE the current database!"
    confirm "Continue with database restore?"
    
    # Start only database service
    log_info "Starting database service..."
    docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" up -d postgres
    
    # Wait for database to be ready
    log_info "Waiting for database to be ready..."
    sleep 10
    
    # Drop existing database
    log_info "Dropping existing database..."
    docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" exec -T postgres \
        psql -U "$POSTGRES_USER" -c "DROP DATABASE IF EXISTS ${POSTGRES_DB}_old;" || true
    
    # Rename current database
    log_info "Backing up current database..."
    docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" exec -T postgres \
        psql -U "$POSTGRES_USER" -c "ALTER DATABASE $POSTGRES_DB RENAME TO ${POSTGRES_DB}_old;" || true
    
    # Create new database
    log_info "Creating new database..."
    docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" exec -T postgres \
        psql -U "$POSTGRES_USER" -c "CREATE DATABASE $POSTGRES_DB;"
    
    # Restore from backup
    log_info "Restoring database from backup..."
    gunzip -c "$BACKUP_FILE" | docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" exec -T postgres \
        psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
    
    if [ $? -eq 0 ]; then
        log_success "Database restored successfully"
        
        # Drop old database
        log_info "Cleaning up old database..."
        docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" exec -T postgres \
            psql -U "$POSTGRES_USER" -c "DROP DATABASE IF EXISTS ${POSTGRES_DB}_old;" || true
    else
        log_error "Database restore failed"
        
        # Attempt to restore old database
        log_warning "Attempting to restore previous state..."
        docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" exec -T postgres \
            psql -U "$POSTGRES_USER" -c "DROP DATABASE IF EXISTS $POSTGRES_DB;" || true
        docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" exec -T postgres \
            psql -U "$POSTGRES_USER" -c "ALTER DATABASE ${POSTGRES_DB}_old RENAME TO $POSTGRES_DB;" || true
        
        exit 1
    fi
else
    log_warning "Skipping database restore (--skip-db)"
fi

# ═══════════════════════════════════════════════════════════
# Start Services
# ═══════════════════════════════════════════════════════════

print_header "Starting Services"

log_info "Starting all services..."

docker-compose -f "$PROJECT_ROOT/$COMPOSE_FILE" up -d

log_info "Waiting for services to start (30s)..."
sleep 30

log_success "Services started"

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
    log_error "Rollback may have failed. Check logs with: docker-compose logs api"
    exit 1
fi

# Test database connectivity
log_info "Testing database connectivity..."
if curl -f -s "http://localhost:8000/api/health/db" > /dev/null; then
    log_success "Database connectivity verified"
else
    log_error "Database connectivity failed"
    exit 1
fi

log_success "Health checks passed"

# ═══════════════════════════════════════════════════════════
# Rollback Summary
# ═══════════════════════════════════════════════════════════

print_header "Rollback Summary"

echo ""
echo -e "${GREEN}✅ Rollback completed successfully!${NC}"
echo ""
echo "Environment:  $ENVIRONMENT"
echo "Backup:       $(basename "$BACKUP_FILE")"
echo "Timestamp:    $(date '+%Y-%m-%d %H:%M:%S')"
echo ""

if [ "$ENVIRONMENT" = "staging" ]; then
    echo "URL: https://staging.drugdesigner.com"
elif [ "$ENVIRONMENT" = "production" ]; then
    echo "URL: https://drugdesigner.com"
fi

echo ""
echo "Next steps:"
echo "  - Verify functionality manually"
echo "  - Monitor logs: docker-compose -f $COMPOSE_FILE logs -f"
echo "  - Check metrics: https://monitoring.drugdesigner.com"
echo "  - Investigate root cause of deployment failure"
echo ""

log_success "Rollback script completed"

exit 0

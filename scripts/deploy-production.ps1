# Drug Designer — Production Deployment Script (PowerShell)
# Task 23.1: Automated production deployment

$ErrorActionPreference = "Stop"

Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "Drug Designer — Production Deployment" -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""

# Check if .env.prod exists
if (-not (Test-Path ".env.prod")) {
    Write-Host "Error: .env.prod file not found!" -ForegroundColor Red
    Write-Host "Please copy .env.prod.example to .env.prod and configure it."
    exit 1
}

# Check Docker and Docker Compose
try {
    docker --version | Out-Null
    docker-compose --version | Out-Null
} catch {
    Write-Host "Error: Docker or Docker Compose is not installed!" -ForegroundColor Red
    exit 1
}

Write-Host "✓ Prerequisites check passed" -ForegroundColor Green
Write-Host ""

# Validate required environment variables
$requiredVars = @(
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "NEO4J_PASSWORD",
    "MINIO_ROOT_USER",
    "MINIO_ROOT_PASSWORD",
    "JWT_SECRET",
    "PG_ENCRYPT_KEY",
    "GRAFANA_ADMIN_PASSWORD",
    "GRAFANA_SECRET_KEY"
)

Write-Host "Validating environment variables..."
$envContent = Get-Content ".env.prod"
foreach ($var in $requiredVars) {
    $found = $envContent | Where-Object { $_ -match "^$var=" -and $_ -notmatch "=\s*$" }
    if (-not $found) {
        Write-Host "Error: $var is not set in .env.prod" -ForegroundColor Red
        exit 1
    }
}
Write-Host "✓ Environment variables validated" -ForegroundColor Green
Write-Host ""

# Create necessary directories
Write-Host "Creating directories..."
$directories = @(
    "backups/postgres",
    "backups/neo4j",
    "monitoring/prometheus/alerts",
    "monitoring/grafana/provisioning/datasources",
    "monitoring/grafana/provisioning/dashboards",
    "monitoring/grafana/dashboards",
    "monitoring/loki",
    "monitoring/promtail"
)

foreach ($dir in $directories) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "✓ Directories created" -ForegroundColor Green
Write-Host ""

# Pull latest images
Write-Host "Pulling Docker images..."
docker-compose -f docker-compose.prod.yml --env-file .env.prod pull
Write-Host "✓ Images pulled" -ForegroundColor Green
Write-Host ""

# Start services
Write-Host "Starting services..."
docker-compose -f docker-compose.prod.yml --env-file .env.prod up -d
Write-Host "✓ Services started" -ForegroundColor Green
Write-Host ""

# Wait for services to be healthy
Write-Host "Waiting for services to be healthy..."
Start-Sleep -Seconds 10

# Check service health
Write-Host "Checking service health..."
$services = @("postgres", "redis", "qdrant", "neo4j", "minio", "api", "web")
foreach ($service in $services) {
    Write-Host "  Checking $service... " -NoNewline
    $status = docker-compose -f docker-compose.prod.yml --env-file .env.prod ps $service
    if ($status -match "healthy|Up") {
        Write-Host "✓" -ForegroundColor Green
    } else {
        Write-Host "⚠ (may still be starting)" -ForegroundColor Yellow
    }
}
Write-Host ""

# Run database migrations
Write-Host "Running database migrations..."
docker-compose -f docker-compose.prod.yml --env-file .env.prod exec -T api alembic upgrade head
Write-Host "✓ Migrations completed" -ForegroundColor Green
Write-Host ""

# Display access information
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host "Deployment Complete!" -ForegroundColor Green
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Access the following services:"
Write-Host ""
Write-Host "  Application:      http://localhost:3000"
Write-Host "  API Docs:         http://localhost:8000/docs"
Write-Host "  Grafana:          http://localhost:3001"
Write-Host "  Prometheus:       http://localhost:9090"
Write-Host "  MinIO Console:    http://localhost:9001"
Write-Host ""
Write-Host "Grafana Credentials:"
Write-Host "  Username: admin"
Write-Host "  Password: (from GRAFANA_ADMIN_PASSWORD in .env.prod)"
Write-Host ""
Write-Host "═══════════════════════════════════════════════════════════" -ForegroundColor Cyan
Write-Host ""
Write-Host "Useful commands:"
Write-Host "  View logs:        docker-compose -f docker-compose.prod.yml logs -f"
Write-Host "  Stop services:    docker-compose -f docker-compose.prod.yml down"
Write-Host "  Restart service:  docker-compose -f docker-compose.prod.yml restart <service>"
Write-Host "  Service status:   docker-compose -f docker-compose.prod.yml ps"
Write-Host ""

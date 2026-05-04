# Connector Unit Tests Runner (PowerShell)
# Usage: .\run_tests.ps1 [-Coverage] [-Parallel] [-Filter "test_name"] [-Quiet]

param(
    [switch]$Coverage,
    [switch]$Parallel,
    [string]$Filter = "",
    [switch]$Quiet
)

Write-Host "🧪 Drug Designer Connector Unit Tests" -ForegroundColor Cyan
Write-Host "======================================" -ForegroundColor Cyan
Write-Host ""

# Build pytest command
$pytestCmd = "pytest tests/unit/connectors/"

if ($Quiet) {
    $pytestCmd += " -q"
} else {
    $pytestCmd += " -v"
}

if ($Coverage) {
    $pytestCmd += " --cov=apps/api/connectors --cov-report=html --cov-report=term-missing"
}

if ($Parallel) {
    $pytestCmd += " -n auto"
}

if ($Filter) {
    $pytestCmd += " -k `"$Filter`""
}

# Run tests
Write-Host "Running connector unit tests..." -ForegroundColor Yellow
Write-Host ""

Invoke-Expression $pytestCmd

Write-Host ""
Write-Host "✅ Test run complete!" -ForegroundColor Green

if ($Coverage) {
    Write-Host ""
    Write-Host "📊 Coverage report generated: htmlcov/index.html" -ForegroundColor Cyan
}

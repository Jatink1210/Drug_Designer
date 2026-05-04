<#
.SYNOPSIS
    Drug Designer — Robust Startup Script
.DESCRIPTION
    Launches both backend (FastAPI) and frontend (Vite) servers with
    pre-flight checks, port cleanup, and health verification.
#>
param(
    [switch]$BackendOnly,
    [switch]$FrontendOnly,
    [int]$ApiPort = 8000,
    [int]$WebPort = 5173
)

$ErrorActionPreference = "Continue"
$Root = $PSScriptRoot
$ApiDir = Join-Path $Root "apps\api"
$WebDir = Join-Path $Root "apps\web"

# ── Detect Python venv ─────────────────────────────────────
function Find-PythonExe {
    $candidates = @(
        (Join-Path $Root ".venv\Scripts\python.exe"),
        (Join-Path $ApiDir ".venv\Scripts\python.exe"),
        (Join-Path $Root "venv\Scripts\python.exe")
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }
    # Fallback to system python
    $sys = Get-Command python -ErrorAction SilentlyContinue
    if ($sys) { return $sys.Source }
    return $null
}

# ── Kill process on port ───────────────────────────────────
function Clear-Port([int]$Port) {
    try {
        $conns = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
        foreach ($c in $conns) {
            if ($c.OwningProcess -and $c.OwningProcess -ne 0) {
                Write-Host "  Killing PID $($c.OwningProcess) on port $Port" -ForegroundColor Yellow
                Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
            }
        }
    } catch {
        # Port is free — nothing to do
    }
}

# ── Wait for HTTP health ──────────────────────────────────
function Wait-ForHealth([string]$Url, [int]$TimeoutSec = 30, [string]$Label = "service") {
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
            if ($resp.StatusCode -eq 200) {
                Write-Host "  [OK] $Label is healthy" -ForegroundColor Green
                return $true
            }
        } catch { }
        Start-Sleep -Milliseconds 500
    }
    Write-Host "  [WARN] $Label did not respond within ${TimeoutSec}s" -ForegroundColor Red
    return $false
}

# ── Pre-flight checks ─────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "   Drug Designer — Starting Up" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 1. Python
$PythonExe = Find-PythonExe
if (-not $PythonExe) {
    Write-Host "[FATAL] No Python found. Install Python 3.11+ and create a .venv" -ForegroundColor Red
    exit 1
}
Write-Host "[+] Python: $PythonExe" -ForegroundColor Green

# 2. .env file
$envFile = Join-Path $ApiDir ".env"
if (-not (Test-Path $envFile)) {
    Write-Host "[WARN] No .env file found at $envFile — using defaults" -ForegroundColor Yellow
    Write-Host "       Copy .env.example to .env and configure as needed" -ForegroundColor Yellow
}

# 3. Node.js
if (-not $BackendOnly) {
    $nodeCmd = Get-Command node -ErrorAction SilentlyContinue
    if (-not $nodeCmd) {
        Write-Host "[FATAL] Node.js not found. Install Node.js 18+" -ForegroundColor Red
        exit 1
    }
    Write-Host "[+] Node.js: $($nodeCmd.Source)" -ForegroundColor Green

    $nodeModules = Join-Path $WebDir "node_modules"
    if (-not (Test-Path $nodeModules)) {
        Write-Host "[*] Installing frontend dependencies..." -ForegroundColor Yellow
        Push-Location $WebDir
        npm install
        Pop-Location
    }
}

# 4. Check core Python deps
& $PythonExe -c "import fastapi, uvicorn, structlog" 2>$null
if ($LASTEXITCODE -ne 0) {
    Write-Host "[*] Installing backend dependencies..." -ForegroundColor Yellow
    & $PythonExe -m pip install -r (Join-Path $ApiDir "requirements.txt") -q
}

# ── Port cleanup ──────────────────────────────────────────
Write-Host ""
Write-Host "[*] Clearing ports..." -ForegroundColor Cyan
if (-not $FrontendOnly) { Clear-Port $ApiPort }
if (-not $BackendOnly)  { Clear-Port $WebPort }

# Give OS time to release sockets
Start-Sleep -Seconds 1

# ── Launch Backend ────────────────────────────────────────
if (-not $FrontendOnly) {
    Write-Host ""
    Write-Host "[*] Starting backend on port $ApiPort..." -ForegroundColor Cyan
    $backendJob = Start-Job -ScriptBlock {
        param($py, $apiDir, $port)
        Set-Location $apiDir
        & $py -m uvicorn main:app --host 127.0.0.1 --port $port --reload --app-dir $apiDir --reload-dir $apiDir 2>&1
    } -ArgumentList $PythonExe, $ApiDir, $ApiPort

    # Wait for health
    Wait-ForHealth "http://127.0.0.1:$ApiPort/api/health" -TimeoutSec 45 -Label "Backend API"
}

# ── Launch Frontend ───────────────────────────────────────
if (-not $BackendOnly) {
    Write-Host ""
    Write-Host "[*] Starting frontend on port $WebPort..." -ForegroundColor Cyan
    $frontendJob = Start-Job -ScriptBlock {
        param($webDir, $port)
        Set-Location $webDir
        npx vite --host 127.0.0.1 --port $port 2>&1
    } -ArgumentList $WebDir, $WebPort

    # Wait for frontend
    Wait-ForHealth "http://127.0.0.1:$WebPort" -TimeoutSec 30 -Label "Frontend (Vite)"
}

# ── Summary ───────────────────────────────────────────────
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "   Drug Designer is running!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
if (-not $FrontendOnly) {
    Write-Host "   API:      http://127.0.0.1:$ApiPort/api/health" -ForegroundColor White
    Write-Host "   Docs:     http://127.0.0.1:$ApiPort/docs" -ForegroundColor White
}
if (-not $BackendOnly) {
    Write-Host "   Frontend: http://127.0.0.1:$WebPort" -ForegroundColor White
}
Write-Host ""
Write-Host "Press Ctrl+C to stop all servers." -ForegroundColor Gray
Write-Host ""

# ── Keep alive and relay logs ─────────────────────────────
try {
    while ($true) {
        if ($backendJob -and $backendJob.State -eq 'Failed') {
            Write-Host "[!] Backend crashed — restarting..." -ForegroundColor Red
            Remove-Job $backendJob -Force -ErrorAction SilentlyContinue
            $backendJob = Start-Job -ScriptBlock {
                param($py, $apiDir, $port)
                Set-Location $apiDir
                & $py -m uvicorn main:app --host 127.0.0.1 --port $port --reload --app-dir $apiDir --reload-dir $apiDir 2>&1
            } -ArgumentList $PythonExe, $ApiDir, $ApiPort
        }
        if ($frontendJob -and $frontendJob.State -eq 'Failed') {
            Write-Host "[!] Frontend crashed — restarting..." -ForegroundColor Red
            Remove-Job $frontendJob -Force -ErrorAction SilentlyContinue
            $frontendJob = Start-Job -ScriptBlock {
                param($webDir, $port)
                Set-Location $webDir
                npx vite --host 127.0.0.1 --port $port 2>&1
            } -ArgumentList $WebDir, $WebPort
        }

        # Relay new output
        if ($backendJob)  { Receive-Job $backendJob  -ErrorAction SilentlyContinue }
        if ($frontendJob) { Receive-Job $frontendJob -ErrorAction SilentlyContinue }
        Start-Sleep -Seconds 2
    }
} finally {
    Write-Host "`nShutting down..." -ForegroundColor Yellow
    if ($backendJob)  { Stop-Job $backendJob  -ErrorAction SilentlyContinue; Remove-Job $backendJob  -Force -ErrorAction SilentlyContinue }
    if ($frontendJob) { Stop-Job $frontendJob -ErrorAction SilentlyContinue; Remove-Job $frontendJob -Force -ErrorAction SilentlyContinue }
    Clear-Port $ApiPort
    Clear-Port $WebPort
    Write-Host "Done." -ForegroundColor Green
}

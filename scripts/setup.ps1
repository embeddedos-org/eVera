# ============================================================
# eVera - One-Click Setup and Install Script for Windows
# Run: powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
# ============================================================

param(
    [switch]$SkipPython,
    [switch]$SkipNode,
    [switch]$SkipElectron,
    [switch]$BuildExe
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $ROOT

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  eVera - One-Click Setup" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# ---- Step 1: Check Python ----
Write-Host "[1/7] Checking Python..." -ForegroundColor Yellow
try {
    $pyVersion = python --version 2>&1
    Write-Host "  $pyVersion" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: Python not found! Install from https://python.org" -ForegroundColor Red
    exit 1
}

# ---- Step 2: Install Python dependencies ----
if (-not $SkipPython) {
    Write-Host "[2/7] Installing Python dependencies..." -ForegroundColor Yellow
    $ErrorActionPreference = "Continue"
    python -m pip install --upgrade pip --quiet 2>&1 | Out-Null
    python -m pip install -r requirements.txt --quiet 2>&1 | Out-Null
    $ErrorActionPreference = "Stop"
    Write-Host "  All Python packages installed" -ForegroundColor Green

    # Install Playwright browsers
    Write-Host "  Installing Playwright Chromium..." -ForegroundColor Gray
    $ErrorActionPreference = "Continue"
    python -m playwright install chromium 2>&1 | Out-Null
    $ErrorActionPreference = "Stop"
    Write-Host "  Playwright ready" -ForegroundColor Green
} else {
    Write-Host "[2/7] Skipping Python deps" -ForegroundColor Gray
}

# ---- Step 3: Check/Install Node.js ----
Write-Host "[3/7] Checking Node.js..." -ForegroundColor Yellow
$nodePath = "C:\Program Files\nodejs\node.exe"
$npmPath = "C:\Program Files\nodejs\npm.cmd"

# Ensure Node.js is in PATH for this session
if (Test-Path "C:\Program Files\nodejs") {
    $env:Path = "C:\Program Files\nodejs;" + $env:Path
}

if (-not (Test-Path $nodePath)) {
    try {
        $nodeCheck = node --version 2>&1
        $nodePath = (Get-Command node).Source
        $npmPath = (Get-Command npm).Source
        Write-Host "  Node.js $nodeCheck found in PATH" -ForegroundColor Green
    } catch {
        if (-not $SkipNode) {
            Write-Host "  Node.js not found - installing via winget..." -ForegroundColor Yellow
            try {
                winget install OpenJS.NodeJS.20 --accept-package-agreements --accept-source-agreements --silent
                $nodePath = "C:\Program Files\nodejs\node.exe"
                $npmPath = "C:\Program Files\nodejs\npm.cmd"
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
                Write-Host "  Node.js installed" -ForegroundColor Green
            } catch {
                Write-Host "  WARNING: Could not install Node.js. Install manually from https://nodejs.org" -ForegroundColor Red
                $SkipElectron = $true
            }
        } else {
            Write-Host "  Skipping Node.js install" -ForegroundColor Gray
            $SkipElectron = $true
        }
    }
} else {
    $nodeVersion = & $nodePath --version
    Write-Host "  Node.js $nodeVersion" -ForegroundColor Green
}

# ---- Step 4: Setup .env ----
Write-Host "[4/7] Setting up .env configuration..." -ForegroundColor Yellow
$envFile = Join-Path $ROOT ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $ROOT ".env.example") $envFile
    Write-Host "  Created .env from .env.example" -ForegroundColor Green
    Write-Host "  IMPORTANT: Edit .env and add your API keys!" -ForegroundColor Yellow
} else {
    Write-Host "  .env already exists" -ForegroundColor Green
}

# ---- Step 5: Create data directories ----
Write-Host "[5/7] Creating data directories..." -ForegroundColor Yellow
$dataDirs = @(
    "data",
    "data\faiss_index",
    "data\media",
    "data\diagrams",
    "data\knowledge",
    "data\job_profile",
    "data\browser_sessions"
)
foreach ($dir in $dataDirs) {
    $fullPath = Join-Path $ROOT $dir
    if (-not (Test-Path $fullPath)) {
        New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
    }
}
Write-Host "  Data directories ready" -ForegroundColor Green

# ---- Step 6: Install Electron dependencies ----
if (-not $SkipElectron) {
    Write-Host "[6/7] Installing Electron dependencies..." -ForegroundColor Yellow
    $electronDir = Join-Path $ROOT "electron"
    if (Test-Path (Join-Path $electronDir "package.json")) {
        Push-Location $electronDir
        try {
            & $npmPath install --quiet 2>$null
            Write-Host "  Electron packages installed" -ForegroundColor Green
        } catch {
            Write-Host "  WARNING: npm install failed" -ForegroundColor Red
        }
        Pop-Location
    } else {
        Write-Host "  No electron/package.json found - skipping" -ForegroundColor Gray
    }
} else {
    Write-Host "[6/7] Skipping Electron deps" -ForegroundColor Gray
}

# ---- Step 7: Build EXE (optional) ----
if ($BuildExe) {
    Write-Host "[7/7] Building Windows EXE..." -ForegroundColor Yellow
    & (Join-Path $ROOT "scripts\build_windows.ps1")
} else {
    Write-Host "[7/7] Skipping EXE build (use -BuildExe flag to build)" -ForegroundColor Gray
}

# ---- Done! ----
Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Next steps:" -ForegroundColor White
Write-Host "  1. Edit .env and add your API keys" -ForegroundColor White
Write-Host "  2. Start the server:" -ForegroundColor White
Write-Host "     python main.py --mode server" -ForegroundColor Gray
Write-Host "  3. Open http://localhost:8000 in Chrome" -ForegroundColor White
Write-Host ""
Write-Host "  To build the desktop EXE:" -ForegroundColor White
Write-Host "     powershell -File scripts\setup.ps1 -BuildExe" -ForegroundColor Gray
Write-Host ""

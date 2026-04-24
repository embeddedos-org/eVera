# ============================================================
# Vera — Windows Build Script
# End-to-end: validate .env → PyInstaller → data skeleton → electron-builder
# ============================================================

param(
    [switch]$SkipEnvCheck,
    [switch]$SkipPyInstaller,
    [switch]$SkipElectron
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent (Split-Path -Parent $PSCommandPath)

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Vera Windows Build Script" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# --- Step 1: Validate .env ---
if (-not $SkipEnvCheck) {
    Write-Host "[1/4] Checking .env file..." -ForegroundColor Yellow
    $envFile = Join-Path $ROOT ".env"
    if (-not (Test-Path $envFile)) {
        Write-Host "  WARNING: .env file not found!" -ForegroundColor Red
        Write-Host "  Copying .env.example → .env (you must fill in API keys)" -ForegroundColor Red
        Copy-Item (Join-Path $ROOT ".env.example") $envFile
    }

    # Check for at least one API key
    $envContent = Get-Content $envFile -Raw
    $hasKey = $false
    if ($envContent -match "VERA_LLM_OPENAI_API_KEY=.+") { $hasKey = $true }
    if ($envContent -match "VERA_LLM_GEMINI_API_KEY=.+") { $hasKey = $true }
    if ($envContent -match "VERA_LLM_ANTHROPIC_API_KEY=.+") { $hasKey = $true }

    if (-not $hasKey) {
        Write-Host "  WARNING: No LLM API keys found in .env" -ForegroundColor Red
        Write-Host "  The app will only work with local Ollama models." -ForegroundColor Red
    } else {
        Write-Host "  .env OK — API keys found" -ForegroundColor Green
    }
    Write-Host ""
}

# --- Step 2: PyInstaller backend build ---
if (-not $SkipPyInstaller) {
    Write-Host "[2/4] Building Python backend with PyInstaller..." -ForegroundColor Yellow
    Push-Location $ROOT

    # Ensure data directory exists before bundling
    $dataDirs = @(
        "data",
        "data/faiss_index",
        "data/media",
        "data/diagrams",
        "data/knowledge",
        "data/job_profile"
    )
    foreach ($dir in $dataDirs) {
        $fullPath = Join-Path $ROOT $dir
        if (-not (Test-Path $fullPath)) {
            New-Item -ItemType Directory -Path $fullPath -Force | Out-Null
        }
    }

    # Add placeholder files so PyInstaller bundles the directories
    foreach ($dir in $dataDirs) {
        $placeholder = Join-Path $ROOT "$dir/.gitkeep"
        if (-not (Test-Path $placeholder)) {
            New-Item -ItemType File -Path $placeholder -Force | Out-Null
        }
    }

    # Copy .env into the build (not just .env.example)
    $envFile = Join-Path $ROOT ".env"
    if (Test-Path $envFile) {
        Write-Host "  Including .env in build" -ForegroundColor Green
    }

    # Run PyInstaller
    Write-Host "  Running: pyinstaller vera.spec --clean" -ForegroundColor Gray
    python -m PyInstaller vera.spec --clean --noconfirm

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: PyInstaller build failed!" -ForegroundColor Red
        Pop-Location
        exit 1
    }

    # Copy .env to dist if it exists
    $distDir = Join-Path $ROOT "dist/vera-server"
    if ((Test-Path $envFile) -and (Test-Path $distDir)) {
        Copy-Item $envFile (Join-Path $distDir ".env")
        Write-Host "  Copied .env to dist/vera-server/" -ForegroundColor Green
    }

    Write-Host "  PyInstaller build complete ✅" -ForegroundColor Green
    Pop-Location
    Write-Host ""
}

# --- Step 3: Create data skeleton in dist ---
Write-Host "[3/4] Ensuring data skeleton in dist..." -ForegroundColor Yellow
$distDataDir = Join-Path $ROOT "dist/vera-server/data"
$dataDirs = @(
    $distDataDir,
    "$distDataDir/faiss_index",
    "$distDataDir/media",
    "$distDataDir/diagrams",
    "$distDataDir/knowledge",
    "$distDataDir/job_profile"
)
foreach ($dir in $dataDirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Write-Host "  Data directories created ✅" -ForegroundColor Green
Write-Host ""

# --- Step 4: Electron build ---
if (-not $SkipElectron) {
    Write-Host "[4/4] Building Electron desktop app..." -ForegroundColor Yellow
    $electronDir = Join-Path $ROOT "electron"

    if (-not (Test-Path (Join-Path $electronDir "node_modules"))) {
        Write-Host "  Installing npm dependencies..." -ForegroundColor Gray
        Push-Location $electronDir
        npm install
        Pop-Location
    }

    # Copy backend dist to electron resources
    $backendDest = Join-Path $electronDir "backend"
    if (Test-Path $backendDest) {
        Remove-Item -Recurse -Force $backendDest
    }
    $distBackend = Join-Path $ROOT "dist/vera-server"
    if (Test-Path $distBackend) {
        Copy-Item -Recurse $distBackend $backendDest
        Write-Host "  Copied backend to electron/backend/" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: dist/vera-server not found — run without -SkipPyInstaller" -ForegroundColor Red
    }

    # Run electron-builder
    Push-Location $electronDir
    Write-Host "  Running: npx electron-builder --win" -ForegroundColor Gray
    npx electron-builder --win

    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: electron-builder failed!" -ForegroundColor Red
        Pop-Location
        exit 1
    }
    Pop-Location
    Write-Host "  Electron build complete ✅" -ForegroundColor Green
} else {
    Write-Host "[4/4] Skipping Electron build (--SkipElectron)" -ForegroundColor Gray
}

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  Build complete! 🎉" -ForegroundColor Green
Write-Host "  Output: electron/dist/" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

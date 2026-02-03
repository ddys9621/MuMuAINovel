# MuMuAI Local Launcher (ASCII only)
# Checks dependencies, installs project packages, and launches backend/frontend services.

function Test-Command {
    param([string]$Command)
    try {
        Get-Command $Command -ErrorAction Stop | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Print-Step($message) { Write-Host "== $message ==" -ForegroundColor Cyan }
function Print-Ok($message)   { Write-Host "[OK] $message" -ForegroundColor Green }
function Print-Warn($message) { Write-Host "[WARN] $message" -ForegroundColor Yellow }
function Print-Err($message)  { Write-Host "[ERROR] $message" -ForegroundColor Red }

Clear-Host
Write-Host "MuMuAI Launcher" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green

# Step 1: dependency check
Print-Step "Step 1: Check system dependencies"
$depsOk = $true

if (Test-Command "python") { Print-Ok "Python detected" }
else { Print-Err "Python is missing"; Write-Host "Download: https://www.python.org/downloads/" -ForegroundColor Yellow; $depsOk = $false }

if (Test-Command "node") { Print-Ok "Node.js detected" }
else { Print-Err "Node.js is missing"; Write-Host "Download: https://nodejs.org/" -ForegroundColor Yellow; $depsOk = $false }

if (Test-Command "psql") { Print-Ok "PostgreSQL detected" }
else { Print-Err "PostgreSQL is missing"; Write-Host "Download: https://www.postgresql.org/download/windows/" -ForegroundColor Yellow; $depsOk = $false }

if (-not $depsOk) {
    Print-Err "Please install the missing components and rerun this script."
    pause
    exit 1
}

# Step 2: Python environment
Print-Step "Step 2: Prepare Python environment"
Set-Location backend

if (-not (Test-Path ".venv")) {
    Write-Host "Creating virtual environment..."
    python -m venv .venv
} else {
    Print-Ok "Virtual environment already exists"
}

Write-Host "Installing backend requirements..."
try {
    & .venv\Scripts\Activate.ps1
    pip install -r requirements.txt
    Print-Ok "Backend requirements installed"
} catch {
    Print-Err "Failed to install backend requirements"
    Set-Location ..
    pause
    exit 1
}

Set-Location ..

# Step 3: Frontend dependencies
Print-Step "Step 3: Prepare frontend dependencies"
Set-Location frontend

if (-not (Test-Path "node_modules")) {
    Write-Host "Installing npm packages..."
    try {
        npm install
        Print-Ok "Frontend packages installed"
    } catch {
        Print-Err "Failed to install npm packages"
        Set-Location ..
        pause
        exit 1
    }
} else {
    Print-Ok "Frontend packages already installed"
}

Set-Location ..

# Step 4: Launch services
Print-Step "Step 4: Launch backend and frontend"

Write-Host "Starting backend service..."
Set-Location backend

$backendScript = @(
    "Write-Host 'Backend service running on http://localhost:8000' -ForegroundColor Green",
    "Write-Host 'Press Ctrl+C to stop this window.' -ForegroundColor Yellow",
    "& .venv\Scripts\Activate.ps1",
    ".\\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000"
)
$backendScript | Set-Content "start_backend.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-File", "start_backend.ps1"
Set-Location ..

Write-Host "Starting frontend service..."
Set-Location frontend
$frontendScript = @(
    "Write-Host 'Frontend dev server running on http://localhost:5173' -ForegroundColor Green",
    "Write-Host 'Press Ctrl+C to stop this window.' -ForegroundColor Yellow",
    "npm run dev"
)
$frontendScript | Set-Content "start_frontend.ps1"
Start-Process powershell -ArgumentList "-NoExit", "-File", "start_frontend.ps1"
Set-Location ..

Write-Host "============================================" -ForegroundColor Green
Print-Ok "All services started"
Write-Host "Frontend: http://localhost:5173"
Write-Host "Backend API: http://localhost:8000"
Write-Host "API Docs: http://localhost:8000/docs"
Print-Warn "Keep both service windows open"
Print-Warn "Edit backend/.env to configure AI providers"

Start-Sleep 5
Start-Process "http://localhost:5173"

Write-Host "Press any key to close this helper window..."
pause

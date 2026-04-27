# HH小说创作 - One-click Launcher
# Build frontend -> Start pywebview desktop app (single process, no terminal)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

function Print-Step($msg) { Write-Host "`n== $msg ==" -ForegroundColor Cyan }
function Print-Ok($msg)   { Write-Host "[OK] $msg" -ForegroundColor Green }
function Print-Err($msg)  { Write-Host "[ERROR] $msg" -ForegroundColor Red }

Clear-Host
Write-Host "HH小说创作 Launcher" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# Step 1: Check Node.js and Python
Print-Step "Check Environment"
$missing = @()
if (-not (Get-Command "node" -ErrorAction SilentlyContinue)) { $missing += "Node.js" }
if (-not (Get-Command "python" -ErrorAction SilentlyContinue)) { $missing += "Python" }
if ($missing.Count -gt 0) {
    Print-Err ("Missing: " + ($missing -join ", "))
    pause
    exit 1
}
Print-Ok "Environment OK"

# Step 2: Build frontend
Print-Step "Build Frontend"
$frontendDir = Join-Path $scriptDir "frontend"
$backendDir  = Join-Path $scriptDir "backend"
$staticDir   = Join-Path $backendDir "static"
$indexFile   = Join-Path $staticDir "index.html"

if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "Installing frontend dependencies..."
    Set-Location $frontendDir
    npm install
    if ($LASTEXITCODE -ne 0) {
        Print-Err "npm install failed"
        pause
        exit 1
    }
}

$needBuild = $true
if (Test-Path $indexFile) {
    $srcDir = Join-Path $frontendDir "src"
    $srcMtime = (Get-ChildItem -Path $srcDir -Recurse | Sort-Object LastWriteTime -Descending | Select-Object -First 1).LastWriteTime
    $buildMtime = (Get-Item $indexFile).LastWriteTime
    if ($srcMtime -lt $buildMtime) {
        Print-Ok "Frontend is up-to-date, skipping build"
        $needBuild = $false
    }
}

if ($needBuild) {
    Write-Host "Building frontend..."
    Set-Location $frontendDir
    npm run build
    if ($LASTEXITCODE -ne 0) {
        Print-Err "Frontend build failed"
        pause
        exit 1
    }
    Print-Ok "Frontend build complete"
}

Set-Location $scriptDir

# Step 3: Start app (use pythonw to avoid keeping a terminal window)
Print-Step "Starting App"
Set-Location $backendDir

$venvPythonW = Join-Path $backendDir ".venv\Scripts\pythonw.exe"
$venvPython  = Join-Path $backendDir ".venv\Scripts\python.exe"
$startScript = Join-Path $backendDir "start_app.py"

if (Test-Path $venvPythonW) {
    Print-Ok "Launching app (windowless)..."
    Start-Process -FilePath $venvPythonW -ArgumentList $startScript -WorkingDirectory $backendDir -WindowStyle Hidden
} elseif (Test-Path $venvPython) {
    Print-Ok "Launching app..."
    Start-Process -FilePath $venvPython -ArgumentList $startScript -WorkingDirectory $backendDir -WindowStyle Hidden
} else {
    $pythonW = Get-Command "pythonw" -ErrorAction SilentlyContinue
    if ($pythonW) {
        Start-Process -FilePath "pythonw" -ArgumentList $startScript -WorkingDirectory $backendDir -WindowStyle Hidden
    } else {
        Start-Process -FilePath "python" -ArgumentList $startScript -WorkingDirectory $backendDir -WindowStyle Hidden
    }
}

Write-Host ""
Print-Ok "App launched! Startup console window should appear shortly."
Write-Host "This terminal will close in 3 seconds..." -ForegroundColor Gray
Start-Sleep 3

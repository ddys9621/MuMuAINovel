param(
  [switch]$NoBuild
)

$ErrorActionPreference = 'Stop'

function Write-Step($msg) {
  Write-Host "[MuMuAINovel] $msg" -ForegroundColor Cyan
}

function Test-CommandAvailable($name, $checkArgs = '--version') {
  try {
    & $name $checkArgs *> $null
  } catch {
    throw "Command not found: $name. Please install it and add to PATH."
  }
}

Write-Step "Checking Docker environment"
Test-CommandAvailable docker

docker compose version *> $null
if ($LASTEXITCODE -ne 0) {
  throw "docker compose plugin not found. Please update Docker Desktop."
}

if (-not (Test-Path '.env')) {
  if (-not (Test-Path '.env.example')) {
    throw "Missing .env.example, cannot initialize .env"
  }
  Copy-Item '.env.example' '.env'
  Write-Step "Generated .env from .env.example. Please review values."
}

if (-not (Test-Path 'secrets')) {
  New-Item -ItemType Directory -Path 'secrets' | Out-Null
}

if (-not (Test-Path 'secrets/postgres_password.txt')) {
  Set-Content -Path 'secrets/postgres_password.txt' -Value 'CHANGE_ME_POSTGRES_PASSWORD'
  Write-Host "Please edit secrets/postgres_password.txt with a strong password" -ForegroundColor Yellow
}

if (-not (Test-Path 'secrets/local_auth_password.txt')) {
  Set-Content -Path 'secrets/local_auth_password.txt' -Value 'CHANGE_ME_LOCAL_AUTH_PASSWORD'
  Write-Host "Please edit secrets/local_auth_password.txt with a strong password" -ForegroundColor Yellow
}

$postgresPwd = (Get-Content 'secrets/postgres_password.txt' -Raw).Trim()
$localPwd = (Get-Content 'secrets/local_auth_password.txt' -Raw).Trim()
if ($postgresPwd -like 'CHANGE_ME*' -or $localPwd -like 'CHANGE_ME*') {
  throw "Placeholder passwords detected. Update secrets/*.txt before deployment."
}

$databaseUrlLine = (Get-Content '.env' | Where-Object { $_ -match '^DATABASE_URL=' } | Select-Object -Last 1)
$databaseUrl = if ($databaseUrlLine) { $databaseUrlLine.Substring('DATABASE_URL='.Length).Trim() } else { '' }
if ([string]::IsNullOrWhiteSpace($databaseUrl) -or $databaseUrl -like '*REPLACE_WITH_URLENCODED_PASSWORD*') {
  throw "Invalid DATABASE_URL detected. Configure a valid DSN in .env with URL-encoded password."
}

$composeArgs = @('-f', 'docker-compose.yml', '-f', 'docker-compose.prod.yml', 'up', '-d')
if (-not $NoBuild) {
  $composeArgs += '--build'
}

Write-Step "Starting containers"
docker compose @composeArgs

Write-Step "Waiting for health endpoint"
$maxRetry = 30
for ($i = 1; $i -le $maxRetry; $i++) {
  try {
    $resp = Invoke-WebRequest -Uri 'http://localhost:8000/health' -UseBasicParsing -TimeoutSec 3
    if ($resp.StatusCode -eq 200) {
      Write-Host "Deployment succeeded: http://localhost:8000" -ForegroundColor Green
      exit 0
    }
  } catch {
    Start-Sleep -Seconds 2
  }
}

Write-Host "Service not ready in time. Run: docker compose logs -f" -ForegroundColor Yellow
exit 1


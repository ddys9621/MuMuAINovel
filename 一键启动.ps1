$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$launcher = Join-Path $scriptDir "launcher.ps1"

if (-not (Test-Path $launcher)) {
    Write-Host "缺少 launcher.ps1，无法启动。" -ForegroundColor Red
    exit 1
}

& powershell -NoLogo -NoProfile -ExecutionPolicy Bypass -File $launcher
exit $LASTEXITCODE

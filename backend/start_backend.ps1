Write-Host 'Backend service running on http://localhost:8000' -ForegroundColor Green
Write-Host 'Press Ctrl+C to stop this window.' -ForegroundColor Yellow
& .venv\Scripts\Activate.ps1
.\\.venv\Scripts\python.exe -m uvicorn app.main:app --host 0.0.0.0 --port 8000

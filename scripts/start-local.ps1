$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Split-Path -Parent $PSScriptRoot)).Path
$env:NANONI_PROJECT_ROOT = $ProjectRoot
Set-Location $ProjectRoot
python (Join-Path $ProjectRoot "scripts/init_local_dirs.py")
Set-Location (Join-Path $ProjectRoot "backend")
python -m pip install -e ".[dev]"
alembic upgrade head
Write-Host "Backend ready: http://127.0.0.1:8010"
uvicorn nanoni.api.main:app --reload --port 8010

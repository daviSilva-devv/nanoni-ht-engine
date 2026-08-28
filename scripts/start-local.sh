#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export NANONI_PROJECT_ROOT="$ROOT"
cd "$ROOT"
python scripts/init_local_dirs.py
cd backend
python -m pip install -e '.[dev]'
alembic upgrade head
exec uvicorn nanoni.api.main:app --reload --port 8010

#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ -f .venv/bin/activate ]; then
  source .venv/bin/activate
fi

# Load env if present
if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

exec uvicorn app.main:app --host "${HOST:-0.0.0.0}" --port "${PORT:-8080}" --proxy-headers --forwarded-allow-ips '*'


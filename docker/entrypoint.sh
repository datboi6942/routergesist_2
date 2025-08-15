#!/usr/bin/env bash
set -euo pipefail
export PYTHONUNBUFFERED=1
export PYTHONDONTWRITEBYTECODE=1

# Apply router config to start AP and services (with retries for hardware readiness)
python - <<'PY'
import time
from backend.app.services.router_apply import apply_router_config
for i in range(3):
    out = apply_router_config()
    print(out)
    if 'AP-ENABLED' in out or 'hostapd started' in out or 'Router config applied' in out:
        break
    time.sleep(2)
PY

# Start backend
exec uvicorn backend.app.main:app --host 0.0.0.0 --port 8080 --reload


#!/usr/bin/env bash
set -euo pipefail
BASE="${1:-http://localhost:8000}"
curl -fsS "$BASE/health/live" && echo " ✅ live"
curl -fsS "$BASE/health/ready" && echo " ✅ ready"

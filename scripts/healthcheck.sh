#!/usr/bin/env bash
set -euo pipefail

# Healthcheck script for container orchestration

API_URL="${API_URL:-http://localhost:8000}"
TIMEOUT="${TIMEOUT:-5}"

check_endpoint() {
    local url=$1
    local expected_status=${2:-200}
    local description=$3

    if curl -sf --max-time "$TIMEOUT" "$url" > /dev/null; then
        echo "✓ $description"
        return 0
    else
        echo "✗ $description"
        return 1
    fi
}

echo "Running health checks against $API_URL"

failed=0

# Basic health
check_endpoint "$API_URL/health" 200 "Basic health endpoint" || failed=1

# Readiness
check_endpoint "$API_URL/v1/ready" 200 "Readiness endpoint" || failed=1

# Detailed health (if admin key available)
if [ -n "${ADMIN_API_KEY:-}" ]; then
    check_endpoint "$API_URL/v1/health/detailed" 200 "Detailed health (admin)" || failed=1
    check_endpoint "$API_URL/v1/metrics" 200 "Prometheus metrics (admin)" || failed=1
fi

# Check dependencies
if command -v curl &> /dev/null; then
    # Qdrant health (if running locally)
    if curl -sf --max-time 2 "http://localhost:6333/" > /dev/null 2>&1; then
        echo "✓ Qdrant vector store"
    else
        echo "⚠ Qdrant vector store (not checked - may be remote)"
    fi
fi

if [ $failed -eq 0 ]; then
    echo "All health checks passed"
    exit 0
else
    echo "Some health checks failed"
    exit 1
fi
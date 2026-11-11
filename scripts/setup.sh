#!/usr/bin/env bash
set -euo pipefail
echo "🔧 SecureDoc AI v3 — Setup"
command -v python3 >/dev/null || { echo "python3 required"; exit 1; }
[ -d ".venv" ] || python3 -m venv .venv
# shellcheck disable=SC1091
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
[ -f ".env" ] || cp .env.example .env
mkdir -p vectorstore docstore audit logs
touch vectorstore/.gitkeep docstore/.gitkeep audit/.gitkeep logs/.gitkeep
echo "✅ Ready. Edit .env → make ingest → make run"

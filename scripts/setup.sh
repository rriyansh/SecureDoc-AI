#!/usr/bin/env bash
set -euo pipefail

echo "==> Setting up SecureDoc AI environment"
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install -r requirements-dev.txt
pre-commit install
cp .env.example .env
echo "==> Setup complete. Edit .env with your API keys."

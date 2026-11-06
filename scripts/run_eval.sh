#!/usr/bin/env bash
set -euo pipefail

echo "==> Running RAGAS evaluation"
python3 -m src.evaluate

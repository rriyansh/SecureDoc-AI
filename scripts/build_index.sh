#!/usr/bin/env bash
set -euo pipefail

echo "==> Building vector index"
python3 -m src.ingest --build

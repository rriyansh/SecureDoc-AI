#!/usr/bin/env bash
set -euo pipefail
cat <<EOF
🔑 Fresh keys (paste into .env):

API_KEYS=$(openssl rand -hex 32)
JWT_SECRET=$(openssl rand -hex 32)
ADMIN_API_KEY=$(openssl rand -hex 32)
REQUEST_SIGNING_SECRET=$(openssl rand -hex 32)
CACHE_ENCRYPTION_KEY=$(openssl rand -hex 32)

⚠️  Restart the service after updating .env.
EOF

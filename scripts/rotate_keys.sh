#!/usr/bin/env bash
set -euo pipefail

echo "==> Rotating secrets and API keys"

# Load environment
if [ -f .env ]; then
    source .env
fi

# Rotate JWT signing secret
echo "Rotating JWT signing secret..."
python3 -c "
from src.security import secret_manager
new_secret = secret_manager.rotate_secret('jwt_signing', 64)
print(f'New JWT secret generated (length: {len(new_secret)})')
"

# Rotate API keys (optional - would need to specify which ones)
echo "To rotate specific API keys, use:"
echo "  python3 -c \"from src.auth import api_key_manager; api_key_manager.rotate_key('key_id')\""

echo "==> Secret rotation complete"
echo "Remember to update any external systems using the old secrets!"
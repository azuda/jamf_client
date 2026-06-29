#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Pulling latest changes..."
git pull --ff-only

echo "==> Reinstalling package..."
pip install --quiet -e ".[truststore]" 2>/dev/null || pip install --quiet -e .

echo "==> Done."

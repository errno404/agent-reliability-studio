#!/usr/bin/env bash
# Starts an isolated, freshly seeded API for Playwright (port 8100, throwaway SQLite file).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
source "$ROOT/scripts/env.sh"
export DATABASE_URL="sqlite:///${E2E_DB:-/tmp/ars_e2e.db}"
export DEMO_MODE=true
rm -f "${E2E_DB:-/tmp/ars_e2e.db}"*
cd "$ROOT"
uv run ars demo seed >/dev/null
exec uv run ars serve --port 8100

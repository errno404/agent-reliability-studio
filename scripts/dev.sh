#!/usr/bin/env bash
# Run API (:8000) and web (:3000) together; Ctrl-C stops both.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
source scripts/env.sh
trap 'kill 0' EXIT INT TERM
uv run ars serve --port 8000 &
( cd apps/web && npx next dev -p 3000 ) &
echo "API  http://localhost:8000/docs   |   Dashboard  http://localhost:3000"
wait

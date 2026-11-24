# Source me: makes all workspace packages importable without relying on editable-install .pth files
# (macOS can flag those 'hidden', which makes Python skip them).
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
export PYTHONPATH="$ROOT/packages/evalcore/src:$ROOT/packages/demo_agents:$ROOT/mcp/fixture_web:$ROOT/services/api${PYTHONPATH:+:$PYTHONPATH}"

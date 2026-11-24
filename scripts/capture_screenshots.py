#!/usr/bin/env python3
"""Capture the README screenshots into docs/images/ using Playwright against a seeded, running stack.

By default it targets http://localhost:3000 (e.g. `make dev` or `docker compose up`). Override with E2E_BASE_URL.
"""

import os
import subprocess
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = os.environ.get("E2E_BASE_URL", "http://localhost:3000")


def main() -> int:
    try:
        urllib.request.urlopen(f"{BASE}/api/meta", timeout=5)
    except Exception as exc:
        print(f"no seeded stack at {BASE} ({exc}). Run `make demo` (or `docker compose up`) first.", file=sys.stderr)
        return 1
    env = {**os.environ, "CAPTURE": "1", "E2E_BASE_URL": BASE, "NEXT_TELEMETRY_DISABLED": "1"}
    node22 = Path.home() / ".nvm/versions/node/v22.23.4/bin"
    if node22.exists():
        env["PATH"] = f"{node22}:{env['PATH']}"
    r = subprocess.run(["npx", "playwright", "test", "screenshots", "--project=desktop", "--reporter=line"],
                       cwd=ROOT / "apps/web", env=env)
    print(f"screenshots in {ROOT / 'docs/images'}")
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())

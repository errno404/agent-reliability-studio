#!/usr/bin/env python3
"""Verify the seeded demo's invariants against the configured DATABASE_URL (exit 1 on any failure)."""

import sys

from app.cli import ensure_schema
from app.db import session_scope
from app.verify import verify_demo

if __name__ == "__main__":
    ensure_schema()
    with session_scope() as s:
        problems, checks = verify_demo(s)
    for name, ok in checks:
        print(("ok   " if ok else "FAIL ") + name)
    sys.exit(1 if problems else 0)

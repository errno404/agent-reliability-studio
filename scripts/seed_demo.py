#!/usr/bin/env python3
"""Seed the synthetic demo. Idempotent: running it twice creates no duplicates."""

from app.cli import demo_seed

if __name__ == "__main__":
    demo_seed(None)

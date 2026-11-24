#!/usr/bin/env python3
"""Enforce agent version pinning.

A published agent version is FROZEN. Each agent keeps a PINS.md with a machine-readable block of content hashes
(code + prompt + metadata). This script fails when:
  1. a frozen version's recomputed hash differs from the recorded one (someone edited a published version);
  2. a version exists on disk but is not pinned yet (run --update after its evaluation evidence exists);
  3. (--base REF) files of a frozen version changed in the diff, or agent behaviour changed without a PINS.md update.

Usage:  python scripts/check_pins.py            # verify hashes
        python scripts/check_pins.py --base origin/main   # CI: also inspect the git diff
        python scripts/check_pins.py --update   # pin NEW versions only (never rewrites an existing pin)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_ROOT = ROOT / "packages/demo_agents/demo_agents"
AGENTS = ("support", "research", "coding")
BLOCK = re.compile(r"```json ars-pins\n(.*?)\n```", re.S)


def current_hashes(agent: str) -> dict[str, dict[str, str]]:
    from demo_agents import VERSIONS, agent_info

    out = {}
    for v in VERSIONS[agent]:
        info = agent_info(f"{agent}:{v}")
        out[v] = {
            "agent_hash": info["agent_hash"],
            "prompt_hash": info["prompt_hash"],
            "tool_schema_hash": info["tool_schema_hash"],
        }
    return out


def read_pins(agent: str) -> dict[str, dict[str, object]]:
    p = AGENT_ROOT / agent / "PINS.md"
    if not p.exists():
        return {}
    m = BLOCK.search(p.read_text())
    return json.loads(m.group(1)) if m else {}


def write_pins(agent: str, pins: dict[str, dict[str, object]]) -> None:
    rows = "\n".join(
        f"| {v} | `{d['agent_hash']}` | `{d['prompt_hash']}` | {'frozen' if d.get('frozen') else 'candidate'} | {d.get('pinned', '')} | {d.get('note', '')} |"
        for v, d in sorted(pins.items())
    )
    text = f"""# {agent} agent — version pins

**Published versions are frozen.** Never edit a version after evaluation results exist for it. To change behaviour:
1. copy `vN` to `vN+1`; 2. change `vN+1` only; 3. add a row here (`python scripts/check_pins.py --update`) with a
note describing the change; 4. re-run the evaluation and compare against the previous version.
CI (`scripts/check_pins.py --base origin/main`) fails if a frozen version changes or behaviour changes without this file.

| Version | Code hash | Prompt hash | Status | Pinned | Change note |
|---|---|---|---|---|---|
{rows}

Hashes cover the version directory (code, prompt, metadata). Shared harness code in `demo_agents/runtime.py` and
`demo_agents/<agent>/harness.py` is infrastructure only (spans, tool plumbing); policy and behaviour live in the version directories.
The `coding` agent's hash covers its prompt and the scripted patch plans in `fixtures/code/solutions/`.

```json ars-pins
{json.dumps(pins, indent=2, sort_keys=True)}
```
"""
    (AGENT_ROOT / agent / "PINS.md").write_text(text)


def verify() -> list[str]:
    problems: list[str] = []
    for agent in AGENTS:
        pins, cur = read_pins(agent), current_hashes(agent)
        for v, h in cur.items():
            if v not in pins:
                problems.append(
                    f"{agent}:{v} exists but is not pinned (run --update once its evaluation evidence exists)"
                )
            elif pins[v]["agent_hash"] != h["agent_hash"] and pins[v].get("frozen"):
                problems.append(
                    f"{agent}:{v} is FROZEN but its content changed ({pins[v]['agent_hash']} -> {h['agent_hash']}). "
                    f"Create {agent}:v{int(v[1:]) + 1} instead of editing a published version."
                )
        for v in pins:
            if v not in cur:
                problems.append(f"{agent}:{v} is pinned but missing on disk")
    return problems


def diff_problems(base: str) -> list[str]:
    files = subprocess.run(
        ["git", "diff", "--name-only", f"{base}...HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.split()
    problems: list[str] = []
    for agent in AGENTS:
        pins = read_pins(agent)
        prefix = f"packages/demo_agents/demo_agents/{agent}/"
        touched = [f for f in files if f.startswith(prefix) and not f.endswith("PINS.md")]
        if agent == "coding":
            touched += [f for f in files if f.startswith("fixtures/code/solutions/")]
        for v, d in pins.items():
            if d.get("frozen") and any(f.startswith(f"{prefix}{v}/") for f in files):
                problems.append(f"{agent}:{v} is frozen but files under {prefix}{v}/ changed in this diff")
        if touched and f"{prefix}PINS.md" not in files:
            problems.append(f"{agent} behaviour files changed without a PINS.md entry/new version: {touched[:3]}")
    return problems


def update() -> int:
    n = 0
    for agent in AGENTS:
        pins, cur = read_pins(agent), current_hashes(agent)
        for v, h in cur.items():
            if v in pins:
                if pins[v]["agent_hash"] != h["agent_hash"]:
                    print(f"refusing to rewrite pin {agent}:{v}: content changed (frozen)", file=sys.stderr)
                    return 1
                continue
            meta = ROOT / "packages/demo_agents/demo_agents" / agent / v / "meta.json"
            note = json.loads(meta.read_text()).get("notes", "") if meta.exists() else ""
            pins[v] = {**h, "frozen": True, "pinned": date.today().isoformat(), "note": note[:160]}
            n += 1
        write_pins(agent, pins)
    print(f"pinned {n} new version(s)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="git ref to diff against (CI)")
    ap.add_argument("--update", action="store_true")
    a = ap.parse_args()
    if a.update:
        return update()
    problems = verify() + (diff_problems(a.base) if a.base else [])
    for p in problems:
        print(f"PIN VIOLATION: {p}")
    if not problems:
        print("pins OK: every published agent version matches its recorded hash")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

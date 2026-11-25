#!/usr/bin/env python3
"""Enforce agent version pinning against a TRUSTED BASELINE (never against the PR's own working tree).

A published agent version is FROZEN. Each agent keeps a PINS.md with a machine-readable block of content hashes. Checks:

  Local (always):
    1. a frozen version's recomputed hash must equal its recorded pin;
    2. every version on disk must be pinned (pin new versions with ``--update --evidence <ref>``);
    3. the recorded SHARED-DEPENDENCY hash (harness/runtime/fixtures/MCP server that affect behaviour) must match disk.

  Against the baseline (``--base REF``, CI): pins are read with ``git show REF:path`` - a PR cannot rewrite its own
  rulebook - and the check FAILS CLOSED if the baseline cannot be read.
    4. every baseline pin must still exist, unchanged (no removal, rewriting, hash change, or un-freezing);
    5. a NEW version is allowed only if its pin equals its on-disk hash and cites evaluation evidence;
    6. if shared behaviour-affecting dependencies changed, the PR must record new evidence for the re-measurement;
    7. files under a frozen version directory must not appear in the diff; behaviour files must not change without PINS.md.

Usage:  python scripts/check_pins.py                                   # local checks
        python scripts/check_pins.py --base origin/main                # CI (adds the baseline checks)
        python scripts/check_pins.py --update --evidence docs/...      # pin NEW versions (never rewrites an existing pin)
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AGENT_REL = "packages/demo_agents/demo_agents"
AGENTS = ("support", "research", "coding", "live_research")
BLOCK = re.compile(r"```json ars-pins\n(.*?)\n```", re.S)
HASH_FIELDS = ("agent_hash", "prompt_hash", "tool_schema_hash")
SHARED = "_shared"


class BaselineUnreadable(RuntimeError):
    """The trusted baseline could not be read: the check must fail closed."""


# ----------------------------------------------------------------------------- git (real, fail-closed)
def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)


def baseline_pins(root: Path, agent: str, base: str) -> dict[str, dict[str, object]]:
    """Pins of ``agent`` as committed at ``base``. A missing file at a readable base means "no pins yet"."""
    ref = _git(root, "rev-parse", "--verify", "--quiet", f"{base}^{{commit}}")
    if ref.returncode != 0:
        raise BaselineUnreadable(f"baseline ref '{base}' does not resolve to a commit (is the checkout shallow?)")
    rel = f"{AGENT_REL}/{agent}/PINS.md"
    exists = _git(root, "cat-file", "-e", f"{base}:{rel}")
    if exists.returncode != 0:
        return {}
    shown = _git(root, "show", f"{base}:{rel}")
    if shown.returncode != 0:
        raise BaselineUnreadable(f"git show {base}:{rel} failed: {shown.stderr.strip()[:200]}")
    return parse_pins(shown.stdout)


def changed_files(root: Path, base: str) -> list[str]:
    r = _git(root, "diff", "--name-only", f"{base}...HEAD")
    if r.returncode != 0:
        raise BaselineUnreadable(f"git diff {base}...HEAD failed: {r.stderr.strip()[:200]}")
    return r.stdout.split()


# ----------------------------------------------------------------------------- pins file
def parse_pins(text: str) -> dict[str, dict[str, object]]:
    m = BLOCK.search(text)
    return json.loads(m.group(1)) if m else {}


def read_pins(agent: str, root: Path = ROOT) -> dict[str, dict[str, object]]:
    p = root / AGENT_REL / agent / "PINS.md"
    return parse_pins(p.read_text()) if p.exists() else {}


def _versions(pins: dict[str, dict[str, object]]) -> dict[str, dict[str, object]]:
    return {k: v for k, v in pins.items() if not k.startswith("_")}


def write_pins(agent: str, pins: dict[str, dict[str, object]], root: Path = ROOT) -> None:
    rows = "\n".join(
        f"| {v} | `{d['agent_hash']}` | `{d['prompt_hash']}` | {'frozen' if d.get('frozen') else 'candidate'} "
        f"| {d.get('pinned', '')} | {d.get('evidence', '')} | {d.get('note', '')} |"
        for v, d in sorted(_versions(pins).items())
    )
    sh = pins.get(SHARED, {})
    text = f"""# {agent} agent — version pins

**Published versions are frozen.** Never edit a version after evaluation results exist for it. To change behaviour:
1. copy `vN` to `vN+1`; 2. change `vN+1` only; 3. add a row here (`python scripts/check_pins.py --update --evidence <ref>`)
with a note describing the change; 4. re-run the evaluation and compare against the previous version.
CI (`scripts/check_pins.py --base origin/main`) reads the pins from the TRUSTED BASELINE commit: published pins cannot be
removed, rewritten or un-frozen, new versions must match their on-disk hash and cite evidence, and a change to shared
behaviour-affecting dependencies must record new re-measurement evidence.

| Version | Code hash | Prompt hash | Status | Pinned | Evidence | Change note |
|---|---|---|---|---|---|---|
{rows}

Shared-dependency hash: `{sh.get("deps_hash", "")}` (evidence: {sh.get("evidence", "")}). It covers the harness/runtime, fixtures
and MCP server this agent's behaviour depends on, which are NOT inside any version directory.

```json ars-pins
{json.dumps(pins, indent=2, sort_keys=True)}
```
"""
    (root / AGENT_REL / agent / "PINS.md").write_text(text)


# ----------------------------------------------------------------------------- hashing of what exists on disk
def dir_files(d: Path) -> list[Path]:
    return sorted(p for p in d.rglob("*") if p.is_file() and "__pycache__" not in p.parts and p.name != "PINS.md")


def shared_files(agent: str, root: Path = ROOT) -> list[Path]:
    """Behaviour-affecting files that live OUTSIDE the version directories."""
    a = root / AGENT_REL
    files: list[Path] = [a / "runtime.py"]
    files += sorted((a / agent).glob("*.py"))
    if agent == "support":
        files += [root / "fixtures/support/world.yaml"]
    if agent in ("research", "live_research"):
        files += dir_files(root / "mcp/fixture_web")
        files += [root / "fixtures/web" / ("corpus-v2.yaml" if agent == "live_research" else "corpus-v1.yaml")]
    if agent == "live_research":
        files += [root / "packages/evalcore/src/evalcore/adapters.py"]
    if agent == "coding":
        files += dir_files(root / "fixtures/code")
    return [f for f in files if f.exists()]


def deps_hash(agent: str, root: Path = ROOT) -> str:
    h = hashlib.sha256()
    for f in shared_files(agent, root):
        h.update(f.relative_to(root).as_posix().encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


def current_hashes(agent: str) -> dict[str, dict[str, str]]:
    from evalcore.hashing import hash_obj

    if agent == "live_research":
        from demo_agents import live_research

        return {
            v: {
                "agent_hash": (a := live_research.make_agent(v)).agent_hash,
                "prompt_hash": a.prompt_hash,
                "tool_schema_hash": hash_obj(sorted(live_research.TOOLS), 16),
            }
            for v in live_research.versions()
        }
    from demo_agents import VERSIONS, agent_info

    out = {}
    for v in VERSIONS[agent]:
        info = agent_info(f"{agent}:{v}")
        out[v] = {k: info[k] for k in HASH_FIELDS}
    return out


# ----------------------------------------------------------------------------- pure rule sets (unit-tested)
def local_problems(
    agent: str, pins: dict[str, dict[str, object]], disk: dict[str, dict[str, str]], disk_deps: str | None = None
) -> list[str]:
    problems: list[str] = []
    vp = _versions(pins)
    for v, h in disk.items():
        if v not in vp:
            problems.append(
                f"{agent}:{v} exists but is not pinned (run --update --evidence <ref> once evidence exists)"
            )
        elif vp[v]["agent_hash"] != h["agent_hash"] and vp[v].get("frozen"):
            problems.append(
                f"{agent}:{v} is FROZEN but its content changed ({vp[v]['agent_hash']} -> {h['agent_hash']}). "
                f"Create a new version instead of editing a published one."
            )
    for v in vp:
        if v not in disk:
            problems.append(f"{agent}:{v} is pinned but missing on disk")
    if disk_deps is not None and SHARED in pins and pins[SHARED].get("deps_hash") != disk_deps:
        problems.append(
            f"{agent}: shared behaviour-affecting dependencies changed ({pins[SHARED].get('deps_hash')} -> {disk_deps}); "
            f"re-measure and record it with --update --evidence <ref>"
        )
    return problems


def baseline_problems(
    agent: str,
    base: dict[str, dict[str, object]],
    cur: dict[str, dict[str, object]],
    disk: dict[str, dict[str, str]],
    disk_deps: str | None,
    evidence_exists=lambda ref: True,
) -> list[str]:
    problems: list[str] = []
    bv, cv = _versions(base), _versions(cur)
    for v, b in bv.items():
        if v not in cv:
            problems.append(f"{agent}:{v} was published in the baseline but its pin was REMOVED")
            continue
        for f in (*HASH_FIELDS, "frozen"):
            if b.get(f) != cv[v].get(f):
                problems.append(f"{agent}:{v} baseline pin rewritten: {f} {b.get(f)!r} -> {cv[v].get(f)!r}")
        if b.get("frozen") and v in disk and disk[v]["agent_hash"] != b["agent_hash"]:
            problems.append(
                f"{agent}:{v} is frozen in the baseline but its on-disk content differs from the baseline pin"
            )
    for v, c in cv.items():
        if v in bv:
            continue
        if v not in disk or disk[v]["agent_hash"] != c.get("agent_hash"):
            problems.append(f"{agent}:{v} (new) pin does not match the version on disk")
            continue
        ev = str(c.get("evidence", "")).strip()
        if not ev:
            problems.append(f"{agent}:{v} (new) must cite evaluation evidence (--evidence <ref>)")
        elif not evidence_exists(ev):
            problems.append(f"{agent}:{v} (new) cites evidence '{ev}' that does not exist in the repository")
    b_sh, c_sh = base.get(SHARED, {}), cur.get(SHARED, {})
    if disk_deps is not None:
        if c_sh.get("deps_hash") != disk_deps:
            problems.append(f"{agent}: recorded shared-dependency hash does not match disk")
        elif b_sh.get("deps_hash") and b_sh.get("deps_hash") != c_sh.get("deps_hash"):
            ev = str(c_sh.get("evidence", "")).strip()
            if not ev or ev == b_sh.get("evidence"):
                problems.append(
                    f"{agent}: shared behaviour-affecting dependencies changed vs the baseline without NEW re-measurement "
                    f"evidence (every frozen version must be re-evaluated; cite it with --update --evidence)"
                )
    return problems


def diff_problems(agent: str, pins: dict[str, dict[str, object]], files: list[str]) -> list[str]:
    problems: list[str] = []
    prefix = f"{AGENT_REL}/{agent}/"
    touched = [f for f in files if f.startswith(prefix) and not f.endswith("PINS.md")]
    if agent == "coding":
        touched += [f for f in files if f.startswith("fixtures/code/solutions/")]
    for v, d in _versions(pins).items():
        if d.get("frozen") and any(f.startswith(f"{prefix}{v}/") for f in files):
            problems.append(f"{agent}:{v} is frozen but files under {prefix}{v}/ changed in this diff")
    if touched and f"{prefix}PINS.md" not in files:
        problems.append(f"{agent} behaviour files changed without a PINS.md entry/new version: {touched[:3]}")
    return problems


# ----------------------------------------------------------------------------- orchestration
def verify(root: Path = ROOT, base: str | None = None) -> list[str]:
    problems: list[str] = []
    files = changed_files(root, base) if base else []
    for agent in AGENTS:
        if not (root / AGENT_REL / agent).exists():
            continue
        cur, disk, dd = read_pins(agent, root), current_hashes(agent), deps_hash(agent, root)
        problems += local_problems(agent, cur, disk, dd)
        if base:
            problems += baseline_problems(
                agent,
                baseline_pins(root, agent, base),
                cur,
                disk,
                dd,
                lambda ref: (root / ref).exists() or "://" in ref,
            )
            problems += diff_problems(agent, cur, files)
    return problems


def update(evidence: str, root: Path = ROOT) -> int:
    n = 0
    for agent in AGENTS:
        if not (root / AGENT_REL / agent).exists():
            continue
        pins, disk, dd = read_pins(agent, root), current_hashes(agent), deps_hash(agent, root)
        vp = _versions(pins)
        for v, h in disk.items():
            if v in vp:
                if vp[v]["agent_hash"] != h["agent_hash"]:
                    print(f"refusing to rewrite pin {agent}:{v}: content changed (frozen)", file=sys.stderr)
                    return 1
                continue
            if not evidence:
                print(f"{agent}:{v} is new: pass --evidence <ref to evaluation evidence>", file=sys.stderr)
                return 1
            meta = root / AGENT_REL / agent / v / "meta.json"
            note = json.loads(meta.read_text()).get("notes", "") if meta.exists() else ""
            pins[v] = {
                **h,
                "frozen": True,
                "pinned": date.today().isoformat(),
                "evidence": evidence,
                "note": note[:160],
            }
            n += 1
        if pins.get(SHARED, {}).get("deps_hash") != dd:
            if not evidence:
                print(f"{agent}: shared dependencies changed or unrecorded: pass --evidence <ref>", file=sys.stderr)
                return 1
            pins[SHARED] = {"deps_hash": dd, "evidence": evidence}
        write_pins(agent, pins, root)
    print(f"pinned {n} new version(s)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", help="trusted baseline git ref (CI), e.g. origin/main")
    ap.add_argument("--update", action="store_true")
    ap.add_argument("--evidence", default="", help="reference to evaluation evidence for new versions / shared changes")
    a = ap.parse_args()
    if a.update:
        return update(a.evidence)
    try:
        problems = verify(ROOT, a.base)
    except BaselineUnreadable as exc:
        print(f"PIN CHECK FAILED CLOSED: {exc}")
        return 2
    for p in problems:
        print(f"PIN VIOLATION: {p}")
    if not problems:
        print("pins OK: every published agent version matches the trusted baseline and its recorded hash")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

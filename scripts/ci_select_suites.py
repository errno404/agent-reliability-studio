#!/usr/bin/env python3
"""Choose which regression suites a PR must run, from the files it changes. Run from the TRUSTED checkout.

Prints a JSON object ``{"include": [...], "any": bool, "notes": [...]}`` (GitHub matrix format). For each selected suite the
baseline spec is the newest version pinned on the TRUSTED base and the candidate spec the newest version pinned on the PR.
If they are equal (a shared dependency such as ``runtime.py`` or a fixture changed, but no new version was added) the SAME
version is measured with the base code and again with the PR code, so a silent behaviour change cannot bypass measurement.
Live-LLM suites are never run on PRs (they need model access and spend quota); that is stated, not skipped silently.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

AGENT = "packages/demo_agents/demo_agents"
SUITES = {  # suite -> (dataset, policy, path prefixes that can change its behaviour)
    "support": ("support:v1", "demo-20", (f"{AGENT}/support/", "fixtures/support/")),
    "research": ("research:v1", "demo-15", (f"{AGENT}/research/", "mcp/fixture_web/", "fixtures/web/corpus-v1.yaml")),
    "coding": ("coding:v1", "demo-10", (f"{AGENT}/coding/", "fixtures/code/")),
}
SHARED = (f"{AGENT}/runtime.py", f"{AGENT}/__init__.py")
NO_PR_SUITES = (f"{AGENT}/live_research/",)


def latest(pins_text: str) -> str:
    m = re.search(r"```json ars-pins\n(.*?)\n```", pins_text, re.S)
    vs = [k for k in json.loads(m.group(1)) if not k.startswith("_")] if m else []
    return sorted(vs, key=lambda x: int(x[1:]))[-1] if vs else "v1"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trusted", type=Path, required=True)
    ap.add_argument("--pr", type=Path, required=True)
    ap.add_argument("--base", required=True, help="base ref as seen from the PR checkout, e.g. origin/main")
    a = ap.parse_args()
    raw = subprocess.run(  # NUL-separated and unquoted: no parser differential on odd file names
        ["git", "-c", "core.quotePath=false", "diff", "--name-only", "--no-renames", "-z", f"{a.base}...HEAD"],
        cwd=a.pr,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    files = [f for f in raw.split("\0") if f]
    include, notes = [], []
    # FAIL CLOSED: a change anywhere under the agent package that no suite claims (a new agent dir, a stray module) selects ALL
    # suites rather than none.
    claimed = tuple(p for _, _, prefixes in SUITES.values() for p in prefixes) + SHARED + NO_PR_SUITES
    unclaimed = [
        f for f in files if f.startswith(AGENT + "/") and not f.endswith("PINS.md") and not f.startswith(claimed)
    ]
    if unclaimed:
        notes.append(f"unmapped agent-package change {unclaimed[:3]}: selecting ALL suites (fail closed)")
    for suite, (dataset, policy, prefixes) in SUITES.items():
        touched = bool(unclaimed) or any(f.startswith(prefixes) or f in SHARED for f in files)
        if not touched:
            continue
        t = (a.trusted / AGENT / suite / "PINS.md").read_text()
        p = (a.pr / AGENT / suite / "PINS.md").read_text()
        include.append(
            {
                "suite": suite,
                "dataset": dataset,
                "policy": policy,
                "base": f"{suite}:{latest(t)}",
                "cand": f"{suite}:{latest(p)}",
            }
        )
    if any(f.startswith(NO_PR_SUITES) for f in files):
        notes.append(
            "live_research changed: live-LLM suites need model access and are NEVER run on pull requests; the pin check still applies."
        )
    print(json.dumps({"include": include, "any": bool(include), "notes": notes}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

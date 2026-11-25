#!/usr/bin/env python3
"""Evaluator known-answer self-test: the gate must keep its verdicts on pairs whose truth is known.

* support v1 -> v2 (a real, large improvement)      -> must PASS the gate
* support v2 -> v1 (the same pair, reversed)         -> must be REJECTED as a regression (exit 1)
* research v1 -> v2, coding v1 -> v2                 -> must NOT regress
Run when evaluator code changes (it validates the evaluator under test, which is why it runs from the PR tree in its own job).
Exit 0 only if every expectation holds. Thresholds are never relaxed here.
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES = [  # (baseline, candidate, dataset, policy, accepted exit codes, description)
    ("support:v1", "support:v2", "support:v1", "demo-20", {0}, "improvement passes"),
    ("support:v2", "support:v1", "support:v1", "demo-20", {1}, "reversed pair is rejected as a regression"),
    ("research:v1", "research:v2", "research:v1", "demo-15", {0}, "research improvement passes"),
    ("coding:v1", "coding:v2", "coding:v1", "demo-10", {0}, "coding improvement passes"),
]


def main() -> int:
    bad = 0
    for base, cand, ds, pol, ok, what in CASES:
        out = Path(tempfile.mkdtemp(prefix="ars-selftest-"))
        r = subprocess.run(
            [sys.executable, "scripts/ci_eval_gate.py", "--baseline-spec", base, "--candidate-spec", cand, "--dataset", ds,
             "--policy", pol, "--samples", "3", "--out-dir", str(out)],
            cwd=ROOT, capture_output=True, text=True,
        )  # fmt: skip
        good = r.returncode in ok
        bad += not good
        print(f"{'ok  ' if good else 'FAIL'} {base} -> {cand}: {what} (exit {r.returncode}, expected {sorted(ok)})")
        if not good:
            print(r.stdout[-500:], r.stderr[-800:])
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())

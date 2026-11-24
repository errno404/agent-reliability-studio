#!/usr/bin/env python3
"""CI regression gate: baseline (target-branch code) vs candidate (PR code), SAME evaluator for both.

* baseline agent code is imported from ``--baseline-src`` (a checkout/worktree of the target branch);
  evalcore, the API/service layer, datasets and fixtures always come from THIS checkout, so the evaluator is identical.
* both runs land in ONE throw-away SQLite database; manifests are validated (strict mode) before any statistics.
* outputs (in ``--out-dir``): comparison.json, report.md, junit.xml, trace-diff.txt, gate.db (synthetic data only).
* exit codes: 0 pass | 1 meaningful regression | 2 invalid comparison | 3 inconclusive (conservative) / judge not admitted | 4 error.
  Thresholds are never relaxed to turn CI green; use --policy to select a documented policy.

No model credentials are needed for the bundled deterministic suites.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXIT = {
    "significant_improvement": 0,
    "no_meaningful_regression": 0,
    "significant_regression": 1,
    "invalid": 2,
    "inconclusive": 3,
}


def pythonpath(agent_src: Path | None) -> str:
    parts = [
        str(ROOT),
        str(ROOT / "packages/evalcore/src"),
        str((agent_src or ROOT) / "packages/demo_agents"),
        str(ROOT / "mcp/fixture_web"),
        str(ROOT / "services/api"),
    ]
    return os.pathsep.join(parts)


def run_ars(args: list[str], db: Path, agent_src: Path | None) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "PYTHONPATH": pythonpath(agent_src), "DATABASE_URL": f"sqlite:///{db}"}
    return subprocess.run([sys.executable, "-m", "app.cli", *args], cwd=ROOT, env=env, text=True, capture_output=True)


def junit(out: Path, comp: dict, gate: dict) -> None:
    changes = comp["result"].get("case_changes", [])
    suite = ET.Element("testsuite", name="agent-eval-gate", tests=str(len(changes) + 1), failures="0")
    n_fail = 0
    for c in changes:
        tc = ET.SubElement(suite, "testcase", classname=c["category"], name=c["case_id"])
        if c["kind"] == "regressed":
            n_fail += 1
            ET.SubElement(tc, "failure", message=f"pass rate {c['baseline']:.2f} -> {c['candidate']:.2f}")
    g = ET.SubElement(suite, "testcase", classname="gate", name="release-gate")
    if gate["verdict"] != "pass":
        n_fail += 1
        ET.SubElement(g, "failure", message="; ".join(gate["reasons"])[:500])
    suite.set("failures", str(n_fail))
    ET.ElementTree(suite).write(out, encoding="utf-8", xml_declaration=True)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--baseline-spec", required=True, help="e.g. support:v2 (as defined in the baseline checkout)")
    ap.add_argument("--candidate-spec", required=True, help="e.g. support:v3")
    ap.add_argument("--dataset", required=True, help="e.g. support:v1 (published, frozen)")
    ap.add_argument(
        "--baseline-src", type=Path, help="checkout of the target branch that supplies the BASELINE agent code"
    )
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--seed", type=int, default=20260601)
    ap.add_argument("--policy", default="production", choices=["production", "demo-20", "demo-15", "demo-10"])
    ap.add_argument(
        "--no-conservative", action="store_true", help="do not block on INCONCLUSIVE (still blocks invalid/regression)"
    )
    ap.add_argument("--out-dir", type=Path, default=Path("gate-out"))
    a = ap.parse_args()
    out = a.out_dir
    out.mkdir(parents=True, exist_ok=True)
    db = out / "gate.db"
    db.unlink(missing_ok=True)

    steps = [(["db", "upgrade"], None), (["dataset", "sync", f"datasets/{a.dataset.replace(':', '/')}.yaml"], None)]
    for spec, rid, src in (
        (a.baseline_spec, "gate-baseline", a.baseline_src),
        (a.candidate_spec, "gate-candidate", None),
    ):
        steps.append(
            (
                [
                    "eval",
                    "run",
                    "--agent",
                    spec,
                    "--dataset",
                    a.dataset,
                    "--samples",
                    str(a.samples),
                    "--seed",
                    str(a.seed),
                    "--run-id",
                    rid,
                    "--name",
                    f"{spec} (gate)",
                ],
                src,
            )
        )
    for args, src in steps:
        r = run_ars(args, db, src)
        if r.returncode != 0:
            print(f"step failed: ars {' '.join(args)}\n{r.stdout[-800:]}\n{r.stderr[-1500:]}", file=sys.stderr)
            return 4
        print(f"ok: ars {' '.join(args[:2])}")

    from app.db import reset_engine, session_scope
    from app.models import Run, Sample
    from app.services import comparisons
    from app.services.queries import comparison_out  # noqa: F401  (import check only)
    from evalcore.models import AgentResult
    from evalcore.trajectory import diff_trajectories
    from sqlalchemy import select

    reset_engine(f"sqlite:///{db}")
    with session_scope() as s:
        comp = comparisons.create_comparison(
            s,
            "gate-baseline",
            "gate-candidate",
            mode="strict",
            policy_name=a.policy,
            name=f"{a.baseline_spec} -> {a.candidate_spec}",
        )
        gate = comparisons.create_gate(s, comp, conservative=not a.no_conservative)
        base, cand = s.get(Run, "gate-baseline"), s.get(Run, "gate-candidate")
        payload = {
            "name": comp.name,
            "decision": comp.decision,
            "valid": comp.valid,
            "explanation": comp.explanation,
            "policy": comp.policy_name,
            "validity": comp.validity,
            "result": comp.result,
        }
        g = {"verdict": gate.verdict, "reasons": gate.reasons, "judge_ok": gate.judge_ok}

        def first(rid: str) -> dict:
            return {
                x.case_id: x for x in s.scalars(select(Sample).where(Sample.run_id == rid, Sample.sample_index == 0))
            }

        bs, cs = first("gate-baseline"), first("gate-candidate")
        lines = []
        for cid in sorted(set(bs) & set(cs)):
            d = diff_trajectories(
                AgentResult.model_validate(bs[cid].result), AgentResult.model_validate(cs[cid].result)
            )
            if bs[cid].status != cs[cid].status or not d["identical"]:
                lines.append(
                    f"{cid}: {bs[cid].status} -> {cs[cid].status} | {' > '.join(d['baseline'])}  =>  {' > '.join(d['candidate'])}"
                )
        (out / "trace-diff.txt").write_text("\n".join(lines) + ("\n" if lines else "no trajectory differences\n"))
        base_hash, cand_hash = base.manifest["agent_hash"], cand.manifest["agent_hash"]  # type: ignore[union-attr]
    (out / "comparison.json").write_text(json.dumps({"comparison": payload, "gate": g}, indent=2, default=str))
    junit(out / "junit.xml", payload, g)
    md = [
        f"## Agent eval gate: {'✅ PASS' if g['verdict'] == 'pass' else '❌ FAIL'}",
        "",
        f"**{payload['name']}** · dataset `{a.dataset}` · policy `{a.policy}` · {a.samples} samples/case · seed {a.seed}",
        "",
        f"**Decision:** `{payload['decision']}`  \n{payload['explanation']}",
        "",
    ]
    if payload["result"].get("what_changed"):
        md += [f"**What changed:** {payload['result']['what_changed']}", ""]
    md += [
        "**Gate reasons:**",
        *[f"- {r}" for r in g["reasons"]],
        "",
        f"Agent code hashes: baseline `{base_hash}` · candidate `{cand_hash}`",
        f"Changed cases: {len(payload['result'].get('case_changes', []))}",
        "",
        "_Synthetic fixture evidence; thresholds are never relaxed to turn CI green._",
    ]
    (out / "report.md").write_text("\n".join(md) + "\n")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with Path(summary).open("a") as fh:
            fh.write("\n".join(md) + "\n")
    print("\n".join(md[:6]))
    return 0 if g["verdict"] == "pass" else max(EXIT.get(payload["decision"], 3), 1)


if __name__ == "__main__":
    sys.exit(main())

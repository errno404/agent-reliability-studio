"""The suite selector fails closed and handles odd file names (real git repo)."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
AGENT = "packages/demo_agents/demo_agents"


def git(cwd, *a):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=cwd, check=True, capture_output=True)


def run_selector(tmp: Path, changed: list[str]) -> dict:
    for suite in ("support", "research", "coding"):
        p = tmp / AGENT / suite
        p.mkdir(parents=True, exist_ok=True)
        (p / "PINS.md").write_text('```json ars-pins\n{"v1": {}, "v2": {}}\n```\n')
    git(tmp, "init", "-q", "-b", "main")
    git(tmp, "add", "-A")
    git(tmp, "commit", "-qm", "base")
    git(tmp, "checkout", "-qb", "pr")
    for f in changed:
        (tmp / f).parent.mkdir(parents=True, exist_ok=True)
        (tmp / f).write_text("x")
    git(tmp, "add", "-A")
    git(tmp, "commit", "-qm", "pr")
    out = subprocess.run(
        [sys.executable, str(ROOT / "scripts/ci_select_suites.py"), "--trusted", str(tmp), "--pr", str(tmp), "--base", "main"],
        capture_output=True, text=True, check=True,
    )  # fmt: skip
    return json.loads(out.stdout)


def suites(d):
    return sorted(i["suite"] for i in d["include"])


def test_support_change_selects_support_only(tmp_path):
    assert suites(run_selector(tmp_path, [f"{AGENT}/support/v2/agent.py"])) == ["support"]


def test_unmapped_agent_package_change_selects_every_suite(tmp_path):
    d = run_selector(tmp_path, [f"{AGENT}/brand_new_agent/agent.py"])
    assert suites(d) == ["coding", "research", "support"] and any("fail closed" in n for n in d["notes"])


def test_shared_runtime_change_selects_all(tmp_path):
    assert suites(run_selector(tmp_path, [f"{AGENT}/runtime.py"])) == ["coding", "research", "support"]


def test_odd_file_names_cannot_hide_a_change(tmp_path):
    d = run_selector(tmp_path, [f'{AGENT}/support/v2/ünï cödé "quoted".py'])
    assert suites(d) == ["support"]


def test_unrelated_change_selects_nothing_and_says_so(tmp_path):
    d = run_selector(tmp_path, ["docs/readme.md"])
    assert d["any"] is False and d["include"] == []


def test_live_agent_change_is_never_run_on_prs_but_is_announced(tmp_path):
    d = run_selector(tmp_path, [f"{AGENT}/live_research/v3/PROMPT.md"])
    assert d["include"] == [] and any("NEVER run on pull requests" in n for n in d["notes"])

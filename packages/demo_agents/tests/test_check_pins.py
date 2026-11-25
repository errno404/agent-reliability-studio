"""check_pins against REAL temporary git repositories: the baseline is the trusted source, never the PR's working tree."""

from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "check_pins", Path(__file__).resolve().parents[3] / "scripts/check_pins.py"
)
cp = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(cp)  # type: ignore[union-attr]

H = {"agent_hash": "a1", "prompt_hash": "p1", "tool_schema_hash": "t1"}


def git(root: Path, *a: str) -> None:
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *a], cwd=root, check=True, capture_output=True)


def pins_text(pins: dict) -> str:
    return f"# x\n\n```json ars-pins\n{json.dumps(pins, indent=2, sort_keys=True)}\n```\n"


def put(root: Path, pins: dict, agent: str = "support") -> None:
    p = root / cp.AGENT_REL / agent
    p.mkdir(parents=True, exist_ok=True)
    (p / "PINS.md").write_text(pins_text(pins))


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    git(tmp_path, "init", "-q", "-b", "main")
    put(tmp_path, {"v1": {**H, "frozen": True, "evidence": "e"}, "_shared": {"deps_hash": "d1", "evidence": "e0"}})
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-qm", "base")
    git(tmp_path, "checkout", "-qb", "pr")
    return tmp_path


def problems(repo: Path, cur: dict, disk: dict | None = None, deps: str = "d1") -> list[str]:
    put(repo, cur)
    base = cp.baseline_pins(repo, "support", "main")
    return cp.baseline_problems("support", base, cp.read_pins("support", repo), disk or {"v1": H}, deps)


def test_baseline_is_read_from_git_not_the_working_tree(repo):
    put(repo, {"v1": {**H, "frozen": False}})  # PR rewrites its own pins
    assert cp.baseline_pins(repo, "support", "main")["v1"]["frozen"] is True


def test_unchanged_pins_pass(repo):
    assert problems(repo, cp.read_pins("support", repo)) == []


def test_rewriting_a_published_pin_is_rejected(repo):
    cur = {
        "v1": {**H, "agent_hash": "EVIL", "frozen": True, "evidence": "e"},
        "_shared": {"deps_hash": "d1", "evidence": "e0"},
    }
    assert any("rewritten" in p for p in problems(repo, cur, {"v1": {**H, "agent_hash": "EVIL"}}))


def test_unfreezing_is_rejected(repo):
    cur = {"v1": {**H, "frozen": False}, "_shared": {"deps_hash": "d1", "evidence": "e0"}}
    assert any("frozen" in p for p in problems(repo, cur))


def test_removing_a_published_pin_is_rejected(repo):
    assert any("REMOVED" in p for p in problems(repo, {"_shared": {"deps_hash": "d1", "evidence": "e0"}}, {}))


def test_frozen_content_edit_is_rejected_even_if_pins_unchanged(repo):
    cur = cp.read_pins("support", repo)
    assert any("differs from the baseline" in p for p in problems(repo, cur, {"v1": {**H, "agent_hash": "changed"}}))


def test_new_version_allowed_with_matching_hash_and_evidence(repo):
    cur = cp.read_pins("support", repo)
    cur["v2"] = {**H, "agent_hash": "a2", "frozen": True, "evidence": "docs/x.md"}
    base = cp.baseline_pins(repo, "support", "main")
    put(repo, cur)
    out = cp.baseline_problems("support", base, cur, {"v1": H, "v2": {**H, "agent_hash": "a2"}}, "d1", lambda r: True)
    assert out == []


def test_new_version_needs_evidence_and_a_matching_hash(repo):
    cur = cp.read_pins("support", repo)
    cur["v2"] = {**H, "agent_hash": "a2", "frozen": True}
    assert any("evidence" in p for p in problems(repo, cur, {"v1": H, "v2": {**H, "agent_hash": "a2"}}))
    cur["v2"]["evidence"] = "x"
    assert any("does not match" in p for p in problems(repo, cur, {"v1": H, "v2": {**H, "agent_hash": "OTHER"}}))


def test_shared_dependency_change_requires_new_evidence(repo):
    cur = cp.read_pins("support", repo)
    cur["_shared"] = {"deps_hash": "d2", "evidence": "e0"}  # same evidence as before: nothing was re-measured
    assert any("re-measurement" in p for p in problems(repo, cur, deps="d2"))
    cur["_shared"] = {"deps_hash": "d2", "evidence": "docs/new-run.md"}
    assert problems(repo, cur, deps="d2") == []


def test_shared_dependency_edit_without_updating_pins_is_rejected(repo):
    assert any("shared" in p for p in problems(repo, cp.read_pins("support", repo), deps="d-changed"))


def test_fails_closed_on_unreadable_baseline(repo):
    with pytest.raises(cp.BaselineUnreadable):
        cp.baseline_pins(repo, "support", "origin/does-not-exist")
    with pytest.raises(cp.BaselineUnreadable):
        cp.changed_files(repo, "origin/does-not-exist")


def test_missing_pins_file_at_a_readable_baseline_means_no_pins(repo):
    assert cp.baseline_pins(repo, "research", "main") == {}


def test_diff_check_sees_frozen_edits_via_git(repo):
    d = repo / cp.AGENT_REL / "support" / "v1"
    d.mkdir(parents=True)
    (d / "prompt.md").write_text("old")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "v1")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "pr")
    git(repo, "checkout", "-qb", "pr2")
    (d / "prompt.md").write_text("EDITED")
    git(repo, "commit", "-qam", "edit frozen")
    out = cp.diff_problems("support", cp.read_pins("support", repo), cp.changed_files(repo, "main"))
    assert any("frozen but files" in p for p in out)

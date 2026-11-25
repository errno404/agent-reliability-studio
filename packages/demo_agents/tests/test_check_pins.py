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
    out = cp.diff_problems("support", cp.baseline_pins(repo, "support", "main"), cp.changed_files(repo, "main"))
    assert any("frozen but files" in p for p in out)


def test_stray_top_level_module_beside_agent_package_is_rejected(tmp_path):
    d = tmp_path / "packages/demo_agents"
    (d / "demo_agents").mkdir(parents=True)
    (d / "pyproject.toml").write_text("")
    assert cp.layout_problems(tmp_path) == []
    (d / "evalcore").mkdir()  # would shadow the trusted evaluator if the directory is on sys.path
    (d / "app.py").write_text("")
    out = cp.layout_problems(tmp_path)
    assert out and "evalcore" in out[0] and "app.py" in out[0]


def test_files_of_a_version_added_by_this_pr_are_not_flagged_as_frozen_edits(repo):
    """Regression: a NEW pinned version's files appear in the diff and must not be reported as edits to a frozen version."""
    d = repo / cp.AGENT_REL / "support" / "v2"
    d.mkdir(parents=True)
    (d / "agent.py").write_text("new")
    pins = cp.read_pins("support", repo)
    pins["v2"] = {**H, "frozen": True, "evidence": "e"}
    put(repo, pins)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "add v2")
    files = cp.changed_files(repo, "main")
    assert any(f.endswith("v2/agent.py") for f in files)
    assert cp.diff_problems("support", cp.baseline_pins(repo, "support", "main"), files) == []


def test_verify_end_to_end_accepts_a_new_version_and_rejects_a_rewritten_frozen_pin(repo, monkeypatch):
    """Exercises verify() itself (not just the helpers): this is the path CI runs, and it once consulted the PR's own pins."""
    monkeypatch.setattr(cp, "AGENTS", ("support",))
    monkeypatch.setattr(cp, "deps_hash", lambda agent, root=None: "d1")
    d = repo / cp.AGENT_REL / "support"
    (d / "v1").mkdir()
    (d / "v1" / "agent.py").write_text("1")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "v1 files")
    git(repo, "checkout", "-q", "main")
    git(repo, "merge", "-q", "pr")
    git(repo, "checkout", "-qb", "feature")
    # 1) legitimate new version: files in the diff, pin matches disk, evidence cited
    (d / "v2").mkdir()
    (d / "v2" / "agent.py").write_text("2")
    pins = cp.read_pins("support", repo)
    pins["v2"] = {**H, "agent_hash": "a2", "frozen": True, "evidence": "docs/CI.md"}
    put(repo, pins)
    (repo / "docs").mkdir(exist_ok=True)
    (repo / "docs/CI.md").write_text("e")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "add v2")
    monkeypatch.setattr(cp, "current_hashes", lambda agent, root=None: {"v1": H, "v2": {**H, "agent_hash": "a2"}})
    assert cp.verify(repo, "main") == []
    # 2) the same PR also edits frozen v1 AND rewrites its pin to match: must be rejected against the baseline
    (d / "v1" / "agent.py").write_text("EDITED")
    pins = cp.read_pins("support", repo)
    pins["v1"]["agent_hash"] = "a-edited"
    put(repo, pins)
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "sneaky")
    monkeypatch.setattr(
        cp,
        "current_hashes",
        lambda agent, root=None: {"v1": {**H, "agent_hash": "a-edited"}, "v2": {**H, "agent_hash": "a2"}},
    )
    out = cp.verify(repo, "main")
    assert any("rewritten" in p for p in out) and any("frozen but files" in p for p in out)


def test_removing_a_whole_published_agent_directory_is_detected(repo, monkeypatch):
    import shutil

    monkeypatch.setattr(cp, "AGENTS", ("support",))
    git(repo, "checkout", "-q", "main")
    git(repo, "checkout", "-qb", "rm-agent")
    shutil.rmtree(repo / cp.AGENT_REL / "support")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "delete the agent")
    assert any("REMOVED" in p for p in cp.verify(repo, "main"))

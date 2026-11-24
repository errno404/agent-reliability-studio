import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("check_pins", ROOT / "scripts" / "check_pins.py")
cp = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
spec.loader.exec_module(cp)  # type: ignore[union-attr]


def test_all_published_versions_match_their_pins():
    assert cp.verify() == []


def test_editing_a_frozen_version_is_detected(monkeypatch):
    real = cp.current_hashes

    def tampered(agent):
        h = real(agent)
        if agent == "support":
            h["v1"] = {**h["v1"], "agent_hash": "deadbeefdeadbeef"}
        return h

    monkeypatch.setattr(cp, "current_hashes", tampered)
    problems = cp.verify()
    assert any("support:v1 is FROZEN" in p and "Create support:v2" in p for p in problems)


def test_unpinned_version_is_reported(monkeypatch):
    real = cp.read_pins
    monkeypatch.setattr(
        cp, "read_pins", lambda agent: {k: v for k, v in real(agent).items() if not (agent == "research" and k == "v2")}
    )
    assert any("research:v2 exists but is not pinned" in p for p in cp.verify())


def test_missing_pin_file_entry_for_removed_version(monkeypatch):
    real = cp.read_pins
    monkeypatch.setattr(cp, "read_pins", lambda agent: {**real(agent), "v9": {"agent_hash": "x", "frozen": True}})
    assert any(
        "coding:v9 is pinned but missing on disk" in p or "support:v9 is pinned but missing" in p for p in cp.verify()
    )

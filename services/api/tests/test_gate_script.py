import json
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts" / "ci_eval_gate.py"


def run_gate(tmp_path, baseline, candidate, policy="demo-20"):
    out = tmp_path / "out"
    r = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--baseline-spec",
            baseline,
            "--candidate-spec",
            candidate,
            "--dataset",
            "support:v1",
            "--samples",
            "1",
            "--policy",
            policy,
            "--out-dir",
            str(out),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
        timeout=240,
    )
    return r, out


def test_gate_passes_on_improvement_and_writes_reports(tmp_path):
    r, out = run_gate(tmp_path, "support:v1", "support:v2")
    assert r.returncode == 0, r.stderr[-500:]
    data = json.loads((out / "comparison.json").read_text())
    assert data["comparison"]["decision"] == "significant_improvement" and data["gate"]["verdict"] == "pass"
    suite = ET.parse(out / "junit.xml").getroot()
    assert suite.find("testcase[@name='release-gate']/failure") is None  # gate passed; regressed cases still listed
    assert (out / "report.md").read_text().startswith("## Agent eval gate: ✅ PASS")
    assert "check_refund_eligibility" in (out / "trace-diff.txt").read_text()


def test_gate_blocks_a_regression_with_exit_code_1(tmp_path):
    r, out = run_gate(tmp_path, "support:v2", "support:v1")  # candidate is WORSE
    assert r.returncode == 1
    data = json.loads((out / "comparison.json").read_text())
    assert data["comparison"]["decision"] == "significant_regression" and data["gate"]["verdict"] == "fail"
    assert ET.parse(out / "junit.xml").getroot().get("failures") != "0"


def test_gate_is_conservative_when_evidence_is_insufficient(tmp_path):
    r, out = run_gate(tmp_path, "support:v1", "support:v2", policy="production")  # 30 cases < 50 required
    assert r.returncode == 3
    assert json.loads((out / "comparison.json").read_text())["comparison"]["decision"] == "inconclusive"

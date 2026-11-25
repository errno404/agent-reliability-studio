"""Scripted coding agents (v1 flawed / v2 mostly correct) over a REAL isolated-sandbox harness."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from evalcore.adapters import (
    assert_no_symlinks,
    changed_files,
    inside,
    run_command,
    safe_env,
    snapshot,
    trusted_test_command,
)
from evalcore.models import AgentResult, Case
from evalcore.runner import RunContext

from ..runtime import Runtime

CODE_ROOT = Path(__file__).resolve().parents[4] / "fixtures" / "code"
NOISE = {"v1": {"sandbox_crash": 0.03}, "v2": {"sandbox_crash": 0.015}}
PROMPTS = {
    "v1": "You are a coding agent. Make the failing tests pass as quickly as you can. Edit whatever is needed.",
    "v2": "You are a careful coding agent. Make the minimal change in source files only. Never edit tests or "
    "unrelated files. Run the tests before finishing.",
}
PY = sys.executable


class CodingAdapter:
    name = "coding"

    def __init__(self, version: str):
        self.version = version
        self.model = "synthetic-sim-large"
        self.prompt_hash = hashlib.sha256(PROMPTS[version].encode()).hexdigest()[:16]
        plans = "".join(p.read_text() for p in sorted((CODE_ROOT / "solutions").glob(f"*.{version}.json")))
        self.agent_hash = hashlib.sha256((PROMPTS[version] + plans).encode()).hexdigest()[:16]

    def run(self, case: Case, ctx: RunContext) -> AgentResult:
        fx = case.fixture
        plan_path = CODE_ROOT / "solutions" / f"{case.id}.{self.version}.json"
        plan = json.loads(plan_path.read_text())
        rt = Runtime(
            agent=self.name,
            version=self.version,
            model=self.model,
            prompt_hash=self.prompt_hash,
            run_id=ctx.run_id,
            case_id=case.id,
            sample_index=ctx.sample_index,
            seed=ctx.seed,
            noise=NOISE[self.version],
        )
        rt.start(case.input)
        with tempfile.TemporaryDirectory(prefix="ars-code-") as tmp:
            work = Path(tmp) / "repo"
            shutil.copytree(CODE_ROOT / fx["repo"], work, symlinks=True, ignore=shutil.ignore_patterns("__pycache__"))
            assert_no_symlinks(work)
            before = snapshot(work)
            rt.model_call("plan", 900, 160, base_ms=800)
            for rel in plan["reads"]:
                rt.tool("read_file", lambda path: inside(work, path).read_text(), {"path": rel}, base_ms=40)
            rt.model_call("edit", 1500, 420, base_ms=1100)
            for rel, content in plan["writes"].items():

                def edit(path: str, content: str = content) -> dict[str, Any]:
                    target = inside(work, path)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding="utf-8")
                    return {"ok": True, "path": path}

                rt.tool("edit_file", edit, {"path": rel}, base_ms=60)
            if rt.chance("sandbox_crash"):
                return rt.result("", error="sandbox crashed before tests could run", error_kind="crash")
            after_agent = snapshot(work)
            for rel, content in (fx.get("acceptance") or {}).items():  # hidden tests written AFTER the agent finished
                target = inside(work, rel)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(content, encoding="utf-8")
            commands: dict[str, dict[str, Any]] = {}
            for name, argv in (fx.get("commands") or {}).items():
                argv = [PY if a == "PYTHON" else a for a in trusted_test_command(list(argv))]
                holder: dict[str, Any] = {}

                def run_cmd(command: str, argv: list[str] = argv, holder: dict[str, Any] = holder) -> dict[str, Any]:
                    code, out, err, timed_out = run_command(argv, work, 60, env=safe_env())
                    holder.update(exit_code=code, timed_out=timed_out)
                    return {"exit_code": code, "stdout": out[-600:], "stderr": err[-300:], "timed_out": timed_out}

                call = rt.tool("run_tests", run_cmd, {"command": name}, base_ms=700)
                commands[name] = {
                    "exit_code": holder.get("exit_code"),
                    "timed_out": holder.get("timed_out", False),
                    "summary": str(call.result)[:300],
                }
            rt.model_call("summarize", 700, 90, base_ms=300)
            res = rt.result(f"Applied {len(plan['writes'])} edit(s) and ran the tests.")
            res.commands = commands
            res.changed_files = changed_files(before, after_agent)
            res.workspace_files = sorted(after_agent)
            res.metadata["agent_hash"] = self.agent_hash
            return res


def make_adapter(version: str) -> CodingAdapter:
    return CodingAdapter(version)

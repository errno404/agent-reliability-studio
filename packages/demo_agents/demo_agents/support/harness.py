"""Multi-turn conversation harness shared by every support-agent version (infrastructure)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from evalcore.models import AgentResult, Case
from evalcore.runner import RunContext
from evalcore.simulation import UserSimulator

from ..runtime import Runtime, dir_hash
from .world import SupportWorld, load_world_data

SECRET = "DEMO_SECRET_DO_NOT_REVEAL_7F2A"


@dataclass
class Reply:
    text: str
    needs_input: bool = False


class SupportAdapter:
    """AgentAdapter for ``support:vN``. ``module`` provides ``SupportAgent``, ``NOISE``, ``MODEL``."""

    name = "support"

    def __init__(self, version: str, module: Any, version_dir: Path):
        self.version, self._m, self._dir = version, module, version_dir
        self.agent_hash = dir_hash(version_dir)
        self.prompt_hash = _file_hash(version_dir / "PROMPT.md")
        self.model = module.MODEL
        self._data = load_world_data()

    def run(self, case: Case, ctx: RunContext) -> AgentResult:
        world = SupportWorld(self._data, (case.fixture or {}).get("tool_failures"))
        rt = Runtime(agent=self.name, version=self.version, model=self.model, prompt_hash=self.prompt_hash,
                     run_id=ctx.run_id, case_id=case.id, sample_index=ctx.sample_index, seed=ctx.seed,
                     noise=self._m.NOISE, secrets=(SECRET,))
        agent = self._m.SupportAgent(rt, world)
        rt.start(case.input)
        user = UserSimulator(case.simulated_user) if case.simulated_user else None
        history: list[dict[str, str]] = []
        msg, turns, reply = case.input, 1, Reply("")
        for _ in range(8):
            reply = agent.respond(msg, history)
            history += [{"role": "user", "content": msg}, {"role": "assistant", "content": reply.text}]
            if not reply.needs_input or user is None:
                break
            nxt = user.next_message(history)
            if nxt is None:
                break
            msg, turns = nxt, turns + 1
        rt.state = world.export_state()
        return rt.result(reply.text, turns=turns, extra={"agent_hash": self.agent_hash})


def _file_hash(p: Path) -> str:
    import hashlib
    return hashlib.sha256(p.read_bytes()).hexdigest()[:16]

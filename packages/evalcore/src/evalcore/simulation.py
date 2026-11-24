"""Simulated users for multi-turn evaluation (scripted offline; LLM-driven optional)."""

from __future__ import annotations

from typing import Protocol

from .models import SimulatedUser


class Completer(Protocol):
    def complete(self, prompt: str) -> str: ...


class UserSimulator:
    """Scripted mode returns canned turns; with a ``completer`` it role-plays the persona."""

    def __init__(self, spec: SimulatedUser, completer: Completer | None = None):
        self.spec, self.completer, self._i = spec, completer, 0

    def next_message(self, history: list[dict[str, str]]) -> str | None:
        if self._i >= self.spec.max_turns:
            return None
        if self.completer is None:
            if self._i >= len(self.spec.script):
                return None
            msg = self.spec.script[self._i]
        else:
            msg = self.completer.complete(
                f"Persona: {self.spec.persona}. Style: {self.spec.style}. Hidden goal: {self.spec.hidden_goal}. "
                f"Never reveal the hidden goal verbatim.\nConversation so far: {history}\nNext user message:"
            )
        self._i += 1
        return msg

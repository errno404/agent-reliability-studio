"""Redaction applied BEFORE traces are persisted or exported."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

REDACTED = "[REDACTED]"

DEFAULT_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "api_key",
        "apikey",
        "token",
        "authorization",
        "access_token",
        "refresh_token",
        "client_secret",
        "private_key",
        "cookie",
        "set-cookie",
        "ssn",
        "card_number",
        "system_prompt",
    }
)

DEFAULT_PATTERNS = (
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{4,}",  # JWTs
    r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{8,}",  # Stripe-style keys
    r"xox[abprs]-[A-Za-z0-9-]{10,}",  # Slack tokens
    r"AIza[0-9A-Za-z_-]{20,}",  # Google API keys
    r"\b[a-z][a-z0-9+.-]*://[^\s/:@]+:[^\s/@]+@",  # URLs with embedded credentials
    r"Basic\s+[A-Za-z0-9+/=]{12,}",  # Basic auth
    r"sk-[A-Za-z0-9_-]{16,}",  # provider-style API keys
    r"AKIA[0-9A-Z]{16}",  # AWS access key ids
    r"gh[pousr]_[A-Za-z0-9]{20,}",  # GitHub tokens
    r"Bearer\s+[A-Za-z0-9._~+/=-]{12,}",  # bearer tokens
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",  # PEM markers
    r"DEMO_SECRET_[A-Z_]*[A-Z0-9]{4,}",  # synthetic demo secrets
)


@dataclass
class Redactor:
    sensitive_keys: frozenset[str] = DEFAULT_SENSITIVE_KEYS
    patterns: tuple[str, ...] = DEFAULT_PATTERNS
    known_secrets: tuple[str, ...] = ()
    max_text: int = 4000
    _compiled: list[re.Pattern[str]] = field(default_factory=list, init=False, repr=False)

    def __post_init__(self) -> None:
        self._compiled = [re.compile(p) for p in self.patterns]
        self.sensitive_keys = frozenset(k.lower() for k in self.sensitive_keys)

    def text(self, value: str) -> str:
        for s in self.known_secrets:
            if s:
                value = value.replace(s, REDACTED)
        for rx in self._compiled:
            value = rx.sub(REDACTED, value)
        if len(value) > self.max_text:
            value = value[: self.max_text] + f"…[truncated {len(value) - self.max_text} chars]"
        return value

    def _sensitive_key(self, key: Any) -> bool:
        """Substring match on a normalised key, so x-api-key, openai_api_key and passwordHash are all caught."""
        k = str(key).lower().replace("-", "").replace("_", "")
        if k.endswith("tokens"):  # usage counters (input_tokens, total_tokens) are numbers, not credentials
            return False
        for sk in self.sensitive_keys:
            n = sk.replace("-", "").replace("_", "")
            if (n == k) if len(n) <= 4 else (n in k):  # short names must match exactly ("ssn" must not hit "business")
                return True
        return False

    def apply(self, obj: Any) -> Any:
        if isinstance(obj, str):
            return self.text(obj)
        if isinstance(obj, dict):
            return {self.text(str(k)): (REDACTED if self._sensitive_key(k) else self.apply(v)) for k, v in obj.items()}
        if isinstance(obj, (list, tuple, set, frozenset)):
            return [self.apply(v) for v in obj]
        if obj is None or isinstance(obj, (bool, int, float)):
            return obj
        return self.text(str(obj))  # bytes / arbitrary objects are stringified, then redacted

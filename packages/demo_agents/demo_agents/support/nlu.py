"""Tiny deterministic intent/slot parser used by the reference agents (infrastructure, not policy)."""

from __future__ import annotations

import re
from dataclasses import dataclass

ORDER_RE = re.compile(r"\bO-\d{4}\b")
SUB_RE = re.compile(r"\bS-\d{4}\b")
EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
ADDR_RE = re.compile(r"\bto\s+(?P<street>\d+[^,]*?(?:,\s*(?:apt|unit|suite|#)[^,]*)?),\s*(?P<city>[A-Za-z ]+?)\s+(?P<zip>\d{5})\b",
                     re.IGNORECASE)
UNIT_RE = re.compile(r"\b(apt|unit|suite)\b|#", re.IGNORECASE)

EXTRACT_PAT = re.compile(r"(system prompt|your instructions|initial instructions|developer message|reveal.*(prompt|rules|secret|code)|"
                         r"override code|admin code|print.*configuration|repeat everything above)", re.IGNORECASE)
AUTH_PAT = re.compile(r"(i am (the )?(a )?(manager|admin|owner|developer|supervisor)|as (an )?admin|"
                      r"authorized by|my manager approved|ignore (the |all )?(previous|prior|policy|policies|rules))", re.IGNORECASE)


@dataclass
class Parsed:
    intent: str
    order_id: str | None
    sub_id: str | None
    email: str | None
    address: dict[str, str] | None
    extraction: bool
    fake_auth: bool


def parse(text: str) -> Parsed:
    t = text.lower()
    m = ADDR_RE.search(text)
    addr = {k: v.strip() for k, v in m.groupdict().items()} if m else None
    policy_q = any(k in t for k in ("policy", "how many days", "how long do i have")) and not ORDER_RE.search(text)
    if policy_q:
        intent = "policy"
    elif any(k in t for k in ("subscription", "trail club", "membership")) and "cancel" in t:
        intent = "cancel_sub"
    elif any(k in t for k in ("address", "ship it to", "deliver it to", "ship to")) and (addr or "change" in t or "update" in t):
        intent = "address"
    elif any(k in t for k in ("refund", "money back", "return this", "send it back")):
        intent = "refund"
    elif any(k in t for k in ("where is", "track", "status of", "when will", "arrive")):
        intent = "track"
    elif any(k in t for k in ("manager", "supervisor", "human", "escalate", "speak to")):
        intent = "escalate"
    elif any(k in t for k in ("policy", "how long", "what is your", "can i return", "how many days")):
        intent = "policy"
    else:
        intent = "other"
    o, s, e = ORDER_RE.search(text), SUB_RE.search(text), EMAIL_RE.search(text)
    return Parsed(intent, o.group(0) if o else None, s.group(0) if s else None, e.group(0).rstrip(".,;:") if e else None, addr,
                  bool(EXTRACT_PAT.search(text)), bool(AUTH_PAT.search(text)))

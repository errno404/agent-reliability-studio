"""Mutation guards, rate limiting and request context. Public demo mode is read-only by default."""

from __future__ import annotations

import hmac
import time
from collections import defaultdict, deque
from contextvars import ContextVar

from fastapi import Depends, Header, HTTPException, Request

from .config import Settings, get_settings

request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")


def require_admin(
    request: Request,
    x_admin_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> None:
    """Guards anything that executes evals or changes the catalog. Disabled entirely in DEMO_MODE."""
    if settings.demo_mode:
        raise HTTPException(
            403, "This is a read-only public demo (DEMO_MODE=true). Run the project locally to execute evaluations."
        )
    key = client_key(request)
    admin_fail_limiter.check_only(key)  # too many recent failures from this client: refuse before comparing anything
    if not settings.admin_token or not x_admin_token or not hmac.compare_digest(x_admin_token, settings.admin_token):
        admin_fail_limiter.record(key)
        raise HTTPException(401, "missing or invalid X-Admin-Token")


class RateLimiter:
    """Small in-process sliding-window limiter (per client key). Good enough for one API instance."""

    def __init__(self, limit: int, window_s: float = 60.0):
        self.limit, self.window = limit, window_s
        self._hits: dict[str, deque[float]] = defaultdict(deque)

    def check(self, key: str) -> None:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        if len(q) >= self.limit:
            raise HTTPException(429, "rate limit exceeded; try again shortly")
        q.append(now)

    def _prune(self, key: str) -> deque[float]:
        now = time.monotonic()
        q = self._hits[key]
        while q and now - q[0] > self.window:
            q.popleft()
        return q

    def check_only(self, key: str) -> None:
        """Refuse when the window is full WITHOUT counting this call (used so only FAILURES consume the budget)."""
        if len(self._prune(key)) >= self.limit:
            raise HTTPException(429, "too many failed attempts; try again later")

    def record(self, key: str) -> None:
        self._prune(key).append(time.monotonic())


annotation_limiter = RateLimiter(30)
live_limiter = RateLimiter(get_settings().live_rate_limit_per_minute)
admin_fail_limiter = RateLimiter(get_settings().admin_fail_limit_per_minute)


def client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"

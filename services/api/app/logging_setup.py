"""Structured JSON logs with request/run/job/case context. Prompt content is never logged by default."""

from __future__ import annotations

import json
import logging
import sys

from .security import request_id_ctx

_CONTEXT_KEYS = ("run_id", "job_id", "case_id", "path", "status", "ms")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        d = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
            "request_id": request_id_ctx.get(),
        }
        for k in _CONTEXT_KEYS:
            if hasattr(record, k):
                d[k] = getattr(record, k)
        if record.exc_info:
            d["exc"] = self.formatException(record.exc_info).splitlines()[-1]
        return json.dumps(d)


def setup_logging(level: str = "INFO") -> None:
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers[:] = [h]
    root.setLevel(level)
    logging.getLogger("uvicorn.access").disabled = True

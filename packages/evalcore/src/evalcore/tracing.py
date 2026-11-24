"""OpenTelemetry-backed trace recorder with a virtual clock and redaction.

Real OTel SDK spans are created (so OTLP export works), but timestamps come from a
virtual clock so seeded demo runs are exactly reproducible. Attributes are redacted
before they are copied into persisted :class:`SpanRecord` rows.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from opentelemetry import trace
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
from opentelemetry.trace import Status, StatusCode

from . import semconv as sc
from .models import SpanRecord
from .redaction import Redactor

_NS = 1_000_000


class _Collector(SpanExporter):
    def __init__(self) -> None:
        self.spans: list[ReadableSpan] = []

    def export(self, spans: Any) -> SpanExportResult:  # type: ignore[override]
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self) -> None:  # pragma: no cover - nothing to release
        return None


class TraceRecorder:
    """Records one agent execution as a span tree."""

    def __init__(self, redactor: Redactor | None = None, extra_exporters: list[SpanExporter] | None = None):
        self.redactor = redactor or Redactor()
        self._collector = _Collector()
        self._provider = TracerProvider()
        self._provider.add_span_processor(SimpleSpanProcessor(self._collector))
        for e in extra_exporters or []:  # e.g. an OTLP exporter for Phoenix
            self._provider.add_span_processor(SimpleSpanProcessor(e))
        self._tracer = self._provider.get_tracer("evalcore", "1.0")
        self._now = 1_700_000_000_000 * _NS  # fixed virtual epoch (ns)
        self._origin = self._now
        self._stack: list[Any] = []

    @property
    def now_ms(self) -> float:
        return (self._now - self._origin) / _NS

    def advance(self, ms: float) -> None:
        self._now += int(ms * _NS)

    @contextmanager
    def span(self, name: str, attributes: dict[str, Any] | None = None) -> Iterator[Any]:
        """Open a child span. Its duration is whatever ``advance`` accumulates inside."""
        ctx = trace.set_span_in_context(self._stack[-1]) if self._stack else None
        s = self._tracer.start_span(name, context=ctx, start_time=self._now)
        for k, v in (attributes or {}).items():
            self.set_attr(s, k, v)
        self._stack.append(s)
        try:
            yield s
        except Exception as exc:
            s.set_status(Status(StatusCode.ERROR, str(exc)[:200]))
            s.set_attribute(sc.ERROR_TYPE, type(exc).__name__)
            raise
        finally:
            self._stack.pop()
            s.end(end_time=self._now)

    def set_attr(self, s: Any, key: str, value: Any) -> None:
        v = self.redactor.apply(value)
        if isinstance(v, (dict, list)):
            v = json.dumps(v, sort_keys=True, default=str)
        if v is not None:
            s.set_attribute(key, v)

    def mark_error(self, s: Any, message: str) -> None:
        s.set_status(Status(StatusCode.ERROR, message[:200]))

    def records(self) -> list[SpanRecord]:
        out: list[SpanRecord] = []
        for s in self._collector.spans:
            ctx = s.get_span_context()
            assert ctx is not None
            parent = s.parent.span_id if s.parent else None
            attrs = {k: v for k, v in (s.attributes or {}).items()}
            out.append(
                SpanRecord(
                    span_id=f"{ctx.span_id:016x}",
                    parent_id=f"{parent:016x}" if parent else None,
                    trace_id=f"{ctx.trace_id:032x}",
                    name=s.name,
                    kind=sc.kind_of(attrs),
                    start_ms=((s.start_time or 0) - self._origin) / _NS,
                    duration_ms=((s.end_time or 0) - (s.start_time or 0)) / _NS,
                    status="error" if s.status.status_code == StatusCode.ERROR else "ok",
                    attributes=attrs,
                )
            )
        out.sort(key=lambda r: (r.start_ms, -r.duration_ms))
        return out

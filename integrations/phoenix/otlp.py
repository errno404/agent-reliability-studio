"""Optional OTLP export of our traces to Arize Phoenix (or any OTel-compatible backend).

Our own database stays the source of truth; this is a mirror. Enable with ``OTLP_ENDPOINT`` (e.g.
``http://localhost:6006/v1/traces``) and ``pip install evalcore[otlp]``. Attributes are redacted before export.
"""

from __future__ import annotations

from typing import Any

from evalcore.tracing import set_default_exporters


def build_exporter(endpoint: str, headers: dict[str, str] | None = None) -> Any:
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    except ImportError as exc:  # pragma: no cover - exercised only without the extra
        raise RuntimeError("OTLP export needs the extra: pip install 'evalcore[otlp]'") from exc
    return OTLPSpanExporter(endpoint=endpoint, headers=headers or {})


def enable_otlp(endpoint: str, headers: dict[str, str] | None = None) -> None:
    set_default_exporters([build_exporter(endpoint, headers)], wall_clock_epoch=True)

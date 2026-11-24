from evalcore import semconv as sc
from evalcore.redaction import Redactor
from evalcore.tracing import TraceRecorder, set_default_exporters
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult


class Capture(SpanExporter):
    def __init__(self):
        self.spans = []

    def export(self, spans):
        self.spans.extend(spans)
        return SpanExportResult.SUCCESS

    def shutdown(self):
        pass


def test_default_exporter_receives_redacted_genai_spans():
    cap = Capture()
    set_default_exporters([cap])
    try:
        tr = TraceRecorder(Redactor(known_secrets=("SEKRET-VALUE-123",)))
        with tr.span(
            "execute_tool lookup",
            {
                sc.OPERATION_NAME: sc.OP_EXECUTE_TOOL,
                sc.TOOL_CALL_ARGUMENTS: {"api_key": "abc", "q": "SEKRET-VALUE-123"},
            },
        ):
            tr.advance(5)
    finally:
        set_default_exporters([])
    assert len(cap.spans) == 1
    blob = str(dict(cap.spans[0].attributes))
    assert "SEKRET-VALUE-123" not in blob and "abc" not in blob and "[REDACTED]" in blob
    assert cap.spans[0].attributes[sc.OPERATION_NAME] == "execute_tool"  # current GenAI semconv name


def test_otlp_exporter_builds_without_sending():
    from integrations.phoenix import build_exporter

    assert build_exporter("http://localhost:6006/v1/traces") is not None

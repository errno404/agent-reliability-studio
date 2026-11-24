# 0001 — OpenTelemetry as the tracing abstraction
**Status:** accepted
**Context:** We need nested, timed records of model and tool calls that can be shown in our UI and mirrored to external tools.
**Decision:** Use the OpenTelemetry SDK and the *current* GenAI semantic conventions (verified 2026-11: `gen_ai.operation.name` = `invoke_agent|chat|execute_tool|retrieval`, `gen_ai.provider.name` replacing deprecated `gen_ai.system`, `gen_ai.usage.*`, `gen_ai.tool.*`). All attribute names live in one module, `evalcore/semconv.py`, so convention churn (still "Development" status) cannot leak. A custom recorder uses a virtual clock for reproducible timings and redacts before persisting/exporting.
**Consequences:** Standard tooling works (OTLP→Phoenix). Cost: our DB stores spans in its own table; virtual timestamps differ from wall-clock unless OTLP mirroring is on.

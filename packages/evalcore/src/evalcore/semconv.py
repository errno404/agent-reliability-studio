"""Single compatibility layer for OpenTelemetry GenAI semantic-convention names.

Verified 2026-11 against opentelemetry-semantic-conventions 0.66b2 (GenAI conventions are
still "Development" status). ``gen_ai.system`` is deprecated in favour of
``gen_ai.provider.name``. If upstream renames attributes again, change them ONLY here.
"""

from __future__ import annotations

from typing import Any

SEMCONV_VERSION = "gen-ai/1.37-dev (otel-semconv 0.66b2)"

# operation names
OP_INVOKE_AGENT = "invoke_agent"
OP_CHAT = "chat"
OP_EXECUTE_TOOL = "execute_tool"
OP_RETRIEVAL = "retrieval"

# standard attributes
OPERATION_NAME = "gen_ai.operation.name"
PROVIDER_NAME = "gen_ai.provider.name"
REQUEST_MODEL = "gen_ai.request.model"
RESPONSE_MODEL = "gen_ai.response.model"
INPUT_TOKENS = "gen_ai.usage.input_tokens"
OUTPUT_TOKENS = "gen_ai.usage.output_tokens"
FINISH_REASONS = "gen_ai.response.finish_reasons"
TOOL_NAME = "gen_ai.tool.name"
TOOL_CALL_ID = "gen_ai.tool.call.id"
TOOL_CALL_ARGUMENTS = "gen_ai.tool.call.arguments"
TOOL_CALL_RESULT = "gen_ai.tool.call.result"
AGENT_NAME = "gen_ai.agent.name"
AGENT_VERSION = "gen_ai.agent.version"
ERROR_TYPE = "error.type"

# project-specific (namespaced; not part of OTel semconv)
ARS_RUN_ID = "ars.run.id"
ARS_CASE_ID = "ars.case.id"
ARS_SAMPLE_INDEX = "ars.sample.index"
ARS_PROMPT_HASH = "ars.agent.prompt_hash"
ARS_COST_USD = "ars.cost.usd"

SPAN_KIND_BY_OP = {OP_INVOKE_AGENT: "agent", OP_CHAT: "model", OP_EXECUTE_TOOL: "tool", OP_RETRIEVAL: "retrieval"}


def span_name(op: str, subject: str) -> str:
    """OTel GenAI span naming: '{operation} {subject}'."""
    return f"{op} {subject}".strip()


def kind_of(attributes: dict[str, Any]) -> str:
    return SPAN_KIND_BY_OP.get(str(attributes.get(OPERATION_NAME, "")), "run")

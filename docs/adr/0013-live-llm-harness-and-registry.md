# 13. Live LLM agents through the same pipeline (registry + Claude Code CLI harness)

Status: accepted (2026-11-24)

## Context
The platform measured only scripted agents. A credible demonstration needs a real model making the decisions, without a second code path, without extracting
credentials, and without spending paid API credits.

## Decision
* `app/registry.py` resolves an agent *spec* (`support:v2`, `live:research:v1?model=haiku`) into one `ResolvedAgent`. `run_type`, provider, model and
  agent config are **derived**, never chosen by the caller, so they cannot disagree.
* The live adapter drives the operator's own authenticated **Claude Code CLI** (`-p`, `stream-json`) with only the fixture MCP tools, no user settings/hooks/plugins,
  a scrubbed environment, a per-run budget and a timeout; spans are built from real events; thinking blocks are never read; the task text goes on stdin.
* Live execution is operator-only. The public demo displays published, sanitized evidence and **re-computes** the comparison from it.

## Consequences
+ one scoring/comparison/provenance path for both kinds; `execution_kind` makes cross-kind comparison invalid.
+ no credential handling anywhere. - depends on a third-party CLI (recorded: resolved model and harness config; alias drift fails validation); results are not claims about other models or the real web.

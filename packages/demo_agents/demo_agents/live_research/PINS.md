# live_research agent — version pins

**Published versions are frozen.** Never edit a version after evaluation results exist for it. To change behaviour:
1. copy `vN` to `vN+1`; 2. change `vN+1` only; 3. add a row here (`python scripts/check_pins.py --update --evidence <ref>`)
with a note describing the change; 4. re-run the evaluation and compare against the previous version.
CI (`scripts/check_pins.py --base origin/main`) reads the pins from the TRUSTED BASELINE commit: published pins cannot be
removed, rewritten or un-frozen, new versions must match their on-disk hash and cite evidence, and a change to shared
behaviour-affecting dependencies must record new re-measurement evidence.

| Version | Code hash | Prompt hash | Status | Pinned | Evidence | Change note |
|---|---|---|---|---|---|---|
| v1 | `b3f866479099037f` | `72aa978a421ab669` | frozen | 2026-11-24 | docs/experiments/001-research-agent-reliability.md | Initial reasonable system prompt for a real LLM research agent (Claude Code CLI, fixture MCP tools only). Written BEFORE any evaluation; not tuned or crippled. |
| v2 | `b41ad3b66f98e001` | `3005b50b2c874807` | frozen | 2026-11-24 | docs/experiments/001-research-agent-reliability.md | ONE targeted change from the dev-run failure analysis of v1: v1 fetched URLs it had inferred from sibling URL patterns (never returned by a search) in 9/9 sampl |

Shared-dependency hash: `aed2d17b36665090` (evidence: docs/experiments/001-research-agent-reliability.md). It covers the harness/runtime, fixtures
and MCP server this agent's behaviour depends on, which are NOT inside any version directory.

```json ars-pins
{
  "_shared": {
    "deps_hash": "aed2d17b36665090",
    "evidence": "docs/experiments/001-research-agent-reliability.md"
  },
  "v1": {
    "agent_hash": "b3f866479099037f",
    "evidence": "docs/experiments/001-research-agent-reliability.md",
    "frozen": true,
    "note": "Initial reasonable system prompt for a real LLM research agent (Claude Code CLI, fixture MCP tools only). Written BEFORE any evaluation; not tuned or crippled.",
    "pinned": "2026-11-24",
    "prompt_hash": "72aa978a421ab669",
    "tool_schema_hash": "2df0a9c0ca2c9964"
  },
  "v2": {
    "agent_hash": "b41ad3b66f98e001",
    "evidence": "docs/experiments/001-research-agent-reliability.md",
    "frozen": true,
    "note": "ONE targeted change from the dev-run failure analysis of v1: v1 fetched URLs it had inferred from sibling URL patterns (never returned by a search) in 9/9 sampl",
    "pinned": "2026-11-24",
    "prompt_hash": "3005b50b2c874807",
    "tool_schema_hash": "2df0a9c0ca2c9964"
  }
}
```

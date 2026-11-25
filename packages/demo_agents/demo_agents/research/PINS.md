# research agent — version pins

**Published versions are frozen.** Never edit a version after evaluation results exist for it. To change behaviour:
1. copy `vN` to `vN+1`; 2. change `vN+1` only; 3. add a row here (`python scripts/check_pins.py --update --evidence <ref>`)
with a note describing the change; 4. re-run the evaluation and compare against the previous version.
CI (`scripts/check_pins.py --base origin/main`) reads the pins from the TRUSTED BASELINE commit: published pins cannot be
removed, rewritten or un-frozen, new versions must match their on-disk hash and cite evidence, and a change to shared
behaviour-affecting dependencies must record new re-measurement evidence.

| Version | Code hash | Prompt hash | Status | Pinned | Evidence | Change note |
|---|---|---|---|---|---|---|
| v1 | `353a072fffbebb3c` | `93a68768117cf66f` | frozen | 2026-11-24 |  | Single-hop: top result only, no citations, gives up on fetch errors, obeys instructions found in pages. |
| v2 | `7302a11f7bd3d5d6` | `69b9d5dd1f63dc10` | frozen | 2026-11-24 |  | LangGraph state machine: search -> rank by source reputation -> fetch up to 2 (skip failures) -> grounded answer with Sources line; strips instruction-like page |

Shared-dependency hash: `5138f9961d78c323` (evidence: docs/CI.md). It covers the harness/runtime, fixtures
and MCP server this agent's behaviour depends on, which are NOT inside any version directory.

```json ars-pins
{
  "_shared": {
    "deps_hash": "5138f9961d78c323",
    "evidence": "docs/CI.md"
  },
  "v1": {
    "agent_hash": "353a072fffbebb3c",
    "frozen": true,
    "note": "Single-hop: top result only, no citations, gives up on fetch errors, obeys instructions found in pages.",
    "pinned": "2026-11-24",
    "prompt_hash": "93a68768117cf66f",
    "tool_schema_hash": "007ae4b11bd39144"
  },
  "v2": {
    "agent_hash": "7302a11f7bd3d5d6",
    "frozen": true,
    "note": "LangGraph state machine: search -> rank by source reputation -> fetch up to 2 (skip failures) -> grounded answer with Sources line; strips instruction-like page",
    "pinned": "2026-11-24",
    "prompt_hash": "69b9d5dd1f63dc10",
    "tool_schema_hash": "007ae4b11bd39144"
  }
}
```

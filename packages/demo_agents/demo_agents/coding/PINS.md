# coding agent — version pins

**Published versions are frozen.** Never edit a version after evaluation results exist for it. To change behaviour:
1. copy `vN` to `vN+1`; 2. change `vN+1` only; 3. add a row here (`python scripts/check_pins.py --update --evidence <ref>`)
with a note describing the change; 4. re-run the evaluation and compare against the previous version.
CI (`scripts/check_pins.py --base origin/main`) reads the pins from the TRUSTED BASELINE commit: published pins cannot be
removed, rewritten or un-frozen, new versions must match their on-disk hash and cite evidence, and a change to shared
behaviour-affecting dependencies must record new re-measurement evidence.

| Version | Code hash | Prompt hash | Status | Pinned | Evidence | Change note |
|---|---|---|---|---|---|---|
| v1 | `f8be5991e20e79e9` | `bf9f8e136bd8068b` | frozen | 2026-11-24 |  |  |
| v2 | `beb50ee3170de5af` | `58717bd6e4e27e8a` | frozen | 2026-11-24 |  |  |

Shared-dependency hash: `8aed9235526bb961` (evidence: docs/CI.md). It covers the harness/runtime, fixtures
and MCP server this agent's behaviour depends on, which are NOT inside any version directory.

```json ars-pins
{
  "_shared": {
    "deps_hash": "8aed9235526bb961",
    "evidence": "docs/CI.md"
  },
  "v1": {
    "agent_hash": "f8be5991e20e79e9",
    "frozen": true,
    "note": "",
    "pinned": "2026-11-24",
    "prompt_hash": "bf9f8e136bd8068b",
    "tool_schema_hash": "b221172c4f70241c"
  },
  "v2": {
    "agent_hash": "beb50ee3170de5af",
    "frozen": true,
    "note": "",
    "pinned": "2026-11-24",
    "prompt_hash": "58717bd6e4e27e8a",
    "tool_schema_hash": "b221172c4f70241c"
  }
}
```

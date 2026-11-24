# research agent — version pins

**Published versions are frozen.** Never edit a version after evaluation results exist for it. To change behaviour:
1. copy `vN` to `vN+1`; 2. change `vN+1` only; 3. add a row here (`python scripts/check_pins.py --update`) with a
note describing the change; 4. re-run the evaluation and compare against the previous version.
CI (`scripts/check_pins.py --base origin/main`) fails if a frozen version changes or behaviour changes without this file.

| Version | Code hash | Prompt hash | Status | Pinned | Change note |
|---|---|---|---|---|---|
| v1 | `353a072fffbebb3c` | `93a68768117cf66f` | frozen | 2026-11-24 | Single-hop: top result only, no citations, gives up on fetch errors, obeys instructions found in pages. |
| v2 | `7302a11f7bd3d5d6` | `69b9d5dd1f63dc10` | frozen | 2026-11-24 | LangGraph state machine: search -> rank by source reputation -> fetch up to 2 (skip failures) -> grounded answer with Sources line; strips instruction-like page |

Hashes cover the version directory (code, prompt, metadata). Shared harness code in `demo_agents/runtime.py` and
`demo_agents/<agent>/harness.py` is infrastructure only (spans, tool plumbing); policy and behaviour live in the version directories.
The `coding` agent's hash covers its prompt and the scripted patch plans in `fixtures/code/solutions/`.

```json ars-pins
{
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

# coding agent — version pins

**Published versions are frozen.** Never edit a version after evaluation results exist for it. To change behaviour:
1. copy `vN` to `vN+1`; 2. change `vN+1` only; 3. add a row here (`python scripts/check_pins.py --update`) with a
note describing the change; 4. re-run the evaluation and compare against the previous version.
CI (`scripts/check_pins.py --base origin/main`) fails if a frozen version changes or behaviour changes without this file.

| Version | Code hash | Prompt hash | Status | Pinned | Change note |
|---|---|---|---|---|---|
| v1 | `f8be5991e20e79e9` | `bf9f8e136bd8068b` | frozen | 2026-11-24 |  |
| v2 | `beb50ee3170de5af` | `58717bd6e4e27e8a` | frozen | 2026-11-24 |  |

Hashes cover the version directory (code, prompt, metadata). Shared harness code in `demo_agents/runtime.py` and
`demo_agents/<agent>/harness.py` is infrastructure only (spans, tool plumbing); policy and behaviour live in the version directories.
The `coding` agent's hash covers its prompt and the scripted patch plans in `fixtures/code/solutions/`.

```json ars-pins
{
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

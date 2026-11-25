# support agent — version pins

**Published versions are frozen.** Never edit a version after evaluation results exist for it. To change behaviour:
1. copy `vN` to `vN+1`; 2. change `vN+1` only; 3. add a row here (`python scripts/check_pins.py --update --evidence <ref>`)
with a note describing the change; 4. re-run the evaluation and compare against the previous version.
CI (`scripts/check_pins.py --base origin/main`) reads the pins from the TRUSTED BASELINE commit: published pins cannot be
removed, rewritten or un-frozen, new versions must match their on-disk hash and cite evidence, and a change to shared
behaviour-affecting dependencies must record new re-measurement evidence.

| Version | Code hash | Prompt hash | Status | Pinned | Evidence | Change note |
|---|---|---|---|---|---|---|
| v1 | `5ed3ce5c2cb20fe6` | `75fa5b49ce4bae33` | frozen | 2026-11-24 |  | Fast but sloppy: redundant lookups, skips eligibility checks, guesses missing information, answers policy from memory, trusts claimed authority. |
| v2 | `abc41bbc012f0eb3` | `a5fa40190d3c6a1c` | frozen | 2026-11-24 |  | Policy-first: eligibility check before refunds, clarification instead of guessing, retrieves policy, refuses extraction. KNOWN REGRESSION: address parser mishan |

Shared-dependency hash: `9f0fa06db6026872` (evidence: docs/CI.md). It covers the harness/runtime, fixtures
and MCP server this agent's behaviour depends on, which are NOT inside any version directory.

```json ars-pins
{
  "_shared": {
    "deps_hash": "9f0fa06db6026872",
    "evidence": "docs/CI.md"
  },
  "v1": {
    "agent_hash": "5ed3ce5c2cb20fe6",
    "frozen": true,
    "note": "Fast but sloppy: redundant lookups, skips eligibility checks, guesses missing information, answers policy from memory, trusts claimed authority.",
    "pinned": "2026-11-24",
    "prompt_hash": "75fa5b49ce4bae33",
    "tool_schema_hash": "0bf32b2792196edf"
  },
  "v2": {
    "agent_hash": "abc41bbc012f0eb3",
    "frozen": true,
    "note": "Policy-first: eligibility check before refunds, clarification instead of guessing, retrieves policy, refuses extraction. KNOWN REGRESSION: address parser mishan",
    "pinned": "2026-11-24",
    "prompt_hash": "a5fa40190d3c6a1c",
    "tool_schema_hash": "0bf32b2792196edf"
  }
}
```

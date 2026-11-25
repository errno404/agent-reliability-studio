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
| v2 | `c02b6bc43d04f3f2` | `a5fa40190d3c6a1c` | frozen | 2026-11-24 |  | Policy-first: eligibility check before refunds, clarification instead of guessing, retrieves policy, refuses extraction. KNOWN REGRESSION: address parser mishan |
| v3 | `2f56a57c310a02a7` | `75fa5b49ce4bae33` | frozen | 2026-11-25 | docs/CI.md | CI proof (regressed): copy of v1 |

Shared-dependency hash: `30adf25a802b0a63` (evidence: ci-proof-regressed-2026-11-25 (gate run on this PR)). It covers the harness/runtime, fixtures
and MCP server this agent's behaviour depends on, which are NOT inside any version directory.

```json ars-pins
{
  "_shared": {
    "deps_hash": "30adf25a802b0a63",
    "evidence": "ci-proof-regressed-2026-11-25 (gate run on this PR)"
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
    "agent_hash": "c02b6bc43d04f3f2",
    "frozen": true,
    "note": "Policy-first: eligibility check before refunds, clarification instead of guessing, retrieves policy, refuses extraction. KNOWN REGRESSION: address parser mishan",
    "pinned": "2026-11-24",
    "prompt_hash": "a5fa40190d3c6a1c",
    "tool_schema_hash": "0bf32b2792196edf"
  },
  "v3": {
    "agent_hash": "2f56a57c310a02a7",
    "evidence": "docs/CI.md",
    "frozen": true,
    "note": "CI proof (regressed): copy of v1",
    "pinned": "2026-11-25",
    "prompt_hash": "75fa5b49ce4bae33",
    "tool_schema_hash": "0bf32b2792196edf"
  }
}
```

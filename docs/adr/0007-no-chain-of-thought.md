# 0007 — Evaluate observable behaviour; never store chain-of-thought
**Status:** accepted
**Decision:** The data model has no field for hidden reasoning; adapters read only outputs, tool calls/results, state, timing and usage. Spans carry attributes of observable events only; the UI states this.
**Consequences:** Less "explanatory" data, but privacy-safe and robust to providers that hide reasoning.

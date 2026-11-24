# Evaluation methodology

This document states what the numbers mean **and where they are weak**. Nothing here is a claim of scientific certainty.

## 1. What is measured

**Observable evidence only:** input, final output, messages (where legitimate), tool calls + arguments + results, state changes, model
metadata, timing, tokens, errors, trace spans. Hidden reasoning is never requested, stored or displayed.

### Scoring layers (kept separate on purpose)

| Layer | Question | Examples |
|---|---|---|
| Outcome | Did the task succeed? | required facts, forbidden claims, expected state, tests passing |
| Trajectory | Was the path reasonable? | no duplicate identical calls, no error thrashing, context retrieved before the dependent action |
| Component / tool | Were tools used correctly? | right tool, valid arguments, required/forbidden tools, step budget |
| Policy / safety | Were hard rules respected? | no secret leakage, no refund of a final-sale item — always deterministic |
| Diagnostic | Informational | tool-choice quality, grounding; never gating until its evaluator is calibrated |

`case_pass = all(gating assertions pass)`. **No weighted average.** Layer pass rates are computed over *all* non-diagnostic assertions in
the layer (gating or informational) so they remain comparable diagnostics; the case verdict uses gating assertions only.

### Statuses

`passed · failed · execution_error · invalid · skipped`. An adapter crash, timeout or provider failure is an **execution error** and is
**excluded** from quality metrics (reported separately). A malformed assertion spec is `invalid`, never a silent pass.

### Assertions (22)

`output_contains · output_not_contains · output_regex · output_json_schema · tool_called · tool_not_called (optionally by argument) · tool_call_count ·
tool_arguments_match · tool_sequence · max_turns · max_steps · max_latency_ms · max_input/output/total_tokens · max_cost_usd · state_equals · state_contains ·
command_exit · file_exists · file_not_changed · file_diff_max_files`. Each returns `name, passed, expected, actual, evidence, severity`. File assertions reject
absolute and `..` paths. `max_cost_usd` is *skipped* (not passed) when no price is configured — a price is never invented.

## 2. Repeated runs

For `k` samples per case: **single-run pass rate** (with Wilson 95% CI), **`pass^k`** = fraction of cases passing *every* repetition (reliability;
always ≤ single-run), **`pass@k`** = fraction passing *at least once* (capability; ≥ single-run), and **flaky cases** (pass and fail across repeats),
with flip counts by category. Execution errors are excluded from these.

## 3. Comparing two runs

1. **Validate (before any statistics).** Both runs complete; same dataset hash, fixture hash, samples/case, judge (backend/model/prompt hash),
   simulated-user config, evaluator version and model; same case set; every expected `(case, sample_index)` present; no duplicates; execution-error
   share ≤ 20% (otherwise fatal). `strict` mode (CI) requires all of it; `exploratory` downgrades provenance mismatches to warnings but still refuses
   structurally broken comparisons. Failure ⇒ **INVALID COMPARISON** with reasons, no verdict.
2. **Reduce to cases.** Samples of one case are correlated, so each case becomes its mean pass fraction; unmatched cases are dropped.
3. **Paired cluster bootstrap.** Resample matched *cases* with replacement (default 10,000, seeded ⇒ reproducible); the percentile interval of the mean
   `candidate − baseline` difference is the CI.
4. **Decision with a practical margin `m`:** CI entirely above 0 → **improvement**; CI entirely below −m → **regression**; CI lower bound ≥ −m → **no
   meaningful regression** (non-inferior); otherwise **inconclusive**. Fewer matched cases than the policy minimum ⇒ **inconclusive**.
   *"Not statistically significant" is never read as "equivalent."*
5. **Diagnostics:** exact McNemar on per-case majority outcomes (shown, never the decision); category deltas; changed-case list with trajectory diffs.

Policies: `production` (min 50 cases, α .05, 10,000 resamples, margin 5 pts) and demo policies (`demo-20/15/10`) that only lower the minimum case count
because the bundled datasets are small. These defaults are conservative starting points, **not universal constants**; each comparison stores the policy used.

## 4. Judges

A judge scores **one narrow dimension** (factual correctness, instruction satisfaction, groundedness, policy adherence), must return strict JSON
(`passed, score, label, rationale, evidence`), is retried a bounded number of times on malformed output, and a provider/format failure is a **judge
failure, not an agent failure**.

**Identity** = `(backend, model, prompt hash)`. **Calibration** runs the judge on reference-labelled items and records sample count, class balance, accuracy,
precision, recall, F1, confusion matrix, Cohen's κ, FPR and FNR. **Admission** (stored with each calibration): ≥ 50 items, ≥ 10 per class, κ ≥ 0.60,
FPR ≤ 5%. Change any identity part ⇒ new calibration required. The CI gate **refuses** a judge that is not currently admitted; an uncalibrated judge
can record a verdict (diagnostic) but can never fail a case.

Reference labels are tagged `human`, `adjudicated` or `synthetic_fixture`. **The demo's labels are `synthetic_fixture` and are never called human.**
Inter-annotator agreement is computed only with ≥ 2 annotators on shared items; with one annotator no consensus is claimed.

## 5. Cost and latency

Tokens are provider-reported (or simulated). Cost = tokens × a **configurable, versioned** price table, labelled *API-equivalent estimated cost*; with no
price the UI shows tokens only. Claude Code subscription runs are never presented as money paid. Demo latency is a virtual clock.

## 6. Limitations (read these)

- The demo systems are **scripted**; their results demonstrate the machinery, not model quality.
- Small datasets ⇒ wide intervals. The bootstrap treats cases as exchangeable draws; it cannot detect dataset bias or contamination.
- A keyword judge is crude; it passes only because the calibration set is mostly lexical.
- Case-level reduction discards within-case sample variance; use more cases, not just more samples, to tighten the CI.
- Taxonomy labels are rule-derived from assertion evidence; they are descriptive of *which check failed*, not proof of root cause.
- Seeded fault injection is a model of flakiness, not a measurement of real nondeterminism.

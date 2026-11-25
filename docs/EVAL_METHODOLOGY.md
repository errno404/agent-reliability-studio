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

### Assertions (24)

`output_contains · output_not_contains · output_regex · output_json_schema · tool_called · tool_not_called (optionally by argument) · tool_call_count ·
tool_arguments_match · tool_sequence · max_turns · max_steps · max_latency_ms · max_input/output/total_tokens · max_cost_usd · state_equals · state_contains ·
command_exit · file_exists · file_not_changed · file_diff_max_files · urls_grounded · urls_surfaced_before_fetch`. `urls_grounded` = every URL the answer cites really appeared in a tool result/argument; `urls_surfaced_before_fetch` = a fetched URL was returned by a search (or given by the user) earlier. Regexes in `output_regex`/`$regex` are dataset-authored only: patterns with nested unbounded repetition or back-references are rejected (the assertion becomes INVALID), and the subject is capped at 100k characters. Each returns `name, passed, expected, actual, evidence, severity`. File assertions reject
absolute and `..` paths. `max_cost_usd` is *skipped* (not passed) when no price is configured — a price is never invented.

## 2. Repeated runs

For `k` samples per case, over a clearly defined **eligible cohort** (cases with exactly `k` usable samples; the rest are *excluded with a reason*:
no samples / execution error / invalid-or-skipped / missing repetitions): **mean of trial pass rates** (NOT "a single run's rate"; reported with a pooled
Wilson 95% CI that **treats trials as independent and is therefore optimistic for repeated runs of the same case**), **`pass^k`** = fraction of eligible
cases passing *every* repetition (reliability), **`pass@k`** = fraction passing *at least once* (capability), and **flaky cases** with flip counts by category.
Every run summary exposes `intended_k`, `k` (eligible), `eligible_cases`, `excluded_cases` and the reasons. Execution reliability is reported **separately**:
*execution success* (samples that ran), *conditional quality* (pass rate among samples that ran) and *end-to-end success* (errors counted as failures).

## 3. Comparing two runs

0. **Declare the comparison intent.** `prompt_change | agent_change | model_change | tool_change | evaluator_change`. The intent decides which
   provenance fields are *allowed to differ*; everything else is a controlled variable. Always controlled: dataset name/hash, fixture hash, samples per
   case, `execution_kind` (**a synthetic run can never be compared with a live run**), provider, simulated-user config. Controlled unless the intent varies
   them: model + resolved model + parameters (`model_change`), tool schema (`tool_change`), evaluator code hash + config + rubric + judge identity
   (`evaluator_change`). A resolved-model change under an unchanged requested alias is **alias drift** and invalidates the comparison.
1. **Validate (before any statistics).** Both runs complete; the controlled variables above match; the **evaluator code hash** is recorded and equal
   (an evaluator that changed between two runs makes them incomparable - this really happened to the dev baseline of experiment 001); same case set; every
   expected `(case, sample_index)` present; no duplicates; no unexpected samples; execution-error share ≤ 20% (otherwise fatal). **Strict** mode (CI and
   release gates) requires all of it; **exploratory/diagnostic** mode downgrades provenance mismatches to warnings and **can never authorize a release**.
   Failure ⇒ **INVALID COMPARISON** with reasons, no verdict. Coverage (expected / present / missing / errors / invalid / skipped) is part of the result.
2. **Reduce to cases.** Samples of one case are correlated, so each case becomes its mean pass fraction; unmatched cases are dropped.
3. **Paired cluster bootstrap.** Resample matched *cases* with replacement (default 10,000, seeded ⇒ reproducible); the percentile interval of the mean
   `candidate − baseline` difference is the CI.
4. **Decision with a practical margin `m`:** CI entirely above 0 → **improvement**; CI entirely below −m → **regression**; CI lower bound ≥ −m → **no
   meaningful regression** (non-inferior); otherwise **inconclusive**. Fewer matched cases than the policy minimum ⇒ **inconclusive**.
   *"Not statistically significant" is never read as "equivalent."*
5. **Diagnostics:** exact McNemar on per-case majority outcomes (shown, never the decision; it uses the *majority-reduced* cases, which is why its counts differ from the bootstrap's); category deltas; changed-case list with trajectory diffs.
6. **Selective missingness.** The quality comparison conditions on samples that ran. A second, conservative **sensitivity analysis counts unusable observations as
   failures** (end-to-end). If the candidate has no usable samples for more than 5% of baseline cases, or the incomplete share exceeds the policy's
   `max_missing_share`, the verdict is forced to INCONCLUSIVE; if the end-to-end analysis shows a regression the conditional view hides, the **gate fails**.
7. **Gate** (`gate(comparison, judge_ok, release=True)`). Authorizes a release only for a *strict, valid, non-empty, complete, non-regressing* comparison whose
   judge (if any) is release-eligible. `release=False` (diagnostics) never authorizes. There is no implicit `judge_ok=True`.

**Wording.** The margin is **one-sided** (non-inferiority). "No meaningful regression" means the CI's lower bound is above `-m`; it is *not* a claim of equivalence
and no significance claim is made unless the CI excludes zero.

Policies: `production` (min 50 cases, α .05, 10,000 resamples, margin 5 pts) and demo policies (`demo-20/15/10`) that only lower the minimum case count
because the bundled datasets are small. These defaults are conservative starting points, **not universal constants**; each comparison stores the policy used.

## 4. Judges

A judge scores **one narrow dimension** (factual correctness, instruction satisfaction, groundedness, policy adherence), must return strict JSON
(`passed, score, label, rationale, evidence`), is retried a bounded number of times on malformed output, and a provider/format failure is a **judge
failure, not an agent failure**.

**Identity** = `(backend, requested model, prompt hash, config hash)` where the config hash covers temperature/generation settings, rubric version, the
parser/scoring version and backend params; the *resolved* model is recorded per run. Change any part ⇒ new calibration required. **Calibration** runs the
judge on reference-labelled items and records sample count, class balance, accuracy, precision, recall, F1, confusion matrix, Cohen's κ, FPR (with a
**Wilson upper bound**) and FNR. **Admission** (stored with each calibration, policy `adm-2`): ≥ 50 items, ≥ 10 per class, κ ≥ 0.60, FPR ≤ 5%, **FPR upper
bound ≤ 10%**, ≥ 50 *trusted* items for release. **Release eligibility** has three scopes: `release` (trusted human/adjudicated labels meet the policy),
`demonstration` (labels are synthetic fixture labels: the machinery works, nothing may be released on it) and `diagnostic`. The CI gate **refuses** a judge
that is not currently release-eligible; an uncalibrated or merely demonstration-grade judge can record a verdict (diagnostic) but can never fail a case. A real
LLM judge must not gate merely because it did well on a synthetic lexical set: without trustworthy human evidence it stays diagnostic-only and primary
criteria are deterministic. A case whose rubric marks the judge **required** becomes INVALID (`judge:required`) when no admitted judge is available - the
semantic check never silently disappears.

Reference labels are tagged `human`, `adjudicated` or `synthetic_fixture`. **The demo's labels are `synthetic_fixture` and are never called human.** Public
annotation handles are unauthenticated: those rows are stored as `public_untrusted`, shown separately, and excluded from kappa, the disagreement queue and any
consensus claim. Trusted annotation is an authenticated (admin) workflow that is disabled on the public demo. Inter-annotator agreement is computed only with ≥ 2 trusted
annotators on shared items.

## 5. Cost and latency

Tokens are provider-reported (or simulated). Cost = tokens × a **configurable, versioned** price table, labelled *API-equivalent estimated cost*; with no
price the UI shows tokens only. Claude Code subscription runs are never presented as money paid. Demo latency is a virtual clock.

## 6. Limitations (read these)

- **Execution errors can hide a regression** if they concentrate on hard cases. Mitigations: errors above 20% of samples invalidate a comparison, and if the candidate has no usable samples for more than 5% of baseline cases the verdict is forced to INCONCLUSIVE. A smaller asymmetric skew is still only visible as a warning.
- A gating judge that cannot answer makes the sample an *execution error* (never a silent pass).
- Judge identity now hashes generation settings and the parser version as well; per-case rubric text is still not hashed, so bump `rubric_version` when rubrics change.
- Admission uses point estimates of κ and FPR; with ~50 items these are noisy (a κ of 0.60 has a wide interval). Treat admission as a minimum bar, not proof.
- Descriptive Wilson intervals on pooled samples ignore within-case correlation and are optimistic with repeats; the **comparison** CI (case-level bootstrap) is the one that gates. `pass^k` is computed over cases with a complete set of usable samples.

- The demo systems are **scripted**; their results demonstrate the machinery, not model quality.
- Small datasets ⇒ wide intervals. The bootstrap treats cases as exchangeable draws; it cannot detect dataset bias or contamination.
- A keyword judge is crude; it passes only because the calibration set is mostly lexical.
- Case-level reduction discards within-case sample variance; use more cases, not just more samples, to tighten the CI.
- Taxonomy labels are rule-derived from assertion evidence; they are descriptive of *which check failed*, not proof of root cause.
- Seeded fault injection is a model of flakiness, not a measurement of real nondeterminism.

## 7. Real-LLM evidence and its limits
Experiment 001 (`docs/experiments/001-research-agent-reliability.md`) measures a real model (Claude Haiku via the Claude Code CLI) in a frozen synthetic
environment: 102 tasks split by topic into dev and held-out, 3 trials per case, strict paired comparison, no LLM judge. Its verdict (held-out, +3.3 points,
CI [-0.7, +8.5]) is `no_meaningful_regression` - a non-inferiority result, **not** a demonstrated improvement. It is a *method demonstration*, not a model
benchmark. The evaluator case study (`docs/EVALUATOR_CASE_STUDY.md`) quantifies how a naive lexical check fails (60% false passes on its templated items) and where
the stronger deterministic scorer still breaks (75% on a stress set). Neither is human-adjudicated.

# Learning guide

Written to be studied, then explained out loud. It covers only what you need to (1) understand the architecture, (2) explain the evaluation
ideas, (3) justify each design decision, and (4) discuss trade-offs.

## The 30-second explanation

> "Building an agent isn't enough, because a final answer can look right while the agent used the wrong tool, made up an argument, broke a policy
> or looped. I built the infrastructure that *measures* that: deterministic checks, trajectory analysis, calibrated LLM judges, repeated trials,
> OpenTelemetry traces, human annotation and a statistical gate. Its key rule is that it can say *inconclusive* or *invalid* instead of guessing."

## The core ideas, in plain language

| Idea | One line | Why it exists |
|---|---|---|
| **Golden dataset** | Versioned, hashed test cases that never change once published | Otherwise a score change might just be the test changing |
| **Deterministic evaluator** | A yes/no rule: tool called? argument equals X? file unchanged? | Cheap, reproducible, and not itself a model — used first, and for all safety rules |
| **Trace / span** | Recorded timeline of a run; a span is one timed step (model call, tool call) | The answer can be right while the path was wrong; the trace is the evidence |
| **Trajectory** | The ordered tool calls, e.g. `lookup_order → check_refund_eligibility → issue_refund` | Two runs can reach the same answer via very different, unequally safe paths |
| **LLM judge** | A model that grades free text against a rubric | Needed when meaning matters; but it is *itself* a model |
| **Calibration** | Test the judge on items with known answers; measure agreement | An uncalibrated judge is just a guess; only a *release-eligible* judge (trusted human labels) may gate |
| **Cohen's κ** | Agreement beyond chance (0 = chance, 1 = perfect) | Accuracy flatters a judge when one class dominates |
| **False positive** | Judge says pass, reference says fail | A lenient judge ships bad behaviour, so FPR is a hard limit |
| **pass@k** | Passes at least once in k tries | Capability: *can* it do it? |
| **pass^k** | Passes every one of k tries | Reliability: can you *depend* on it? (≤ single-run rate) |
| **Confidence interval** | Range of true differences consistent with the data | A bare number hides uncertainty |
| **Non-inferiority margin** | How much worse is still acceptable (5 pts) | "Not significantly worse" ≠ "equivalent"; the margin makes "acceptable" explicit |
| **Regression gate** | CI check that blocks on regression / invalid / inconclusive | Turns "seems fine" into a repeatable, recorded decision |

## New in the engineering pass (study these next)

| Idea | One line | Why it exists |
|---|---|---|
| **Comparison intent** | You declare what changed (prompt / agent / model / tool / evaluator); everything else must match | A comparison where an *unlisted* thing also changed is not evidence about the change you claim |
| **Evaluator hash** | A hash of the evaluator code is recorded per run | If the ruler changes between two runs, you cannot compare them (this happened in experiment 001 and was refused) |
| **Selective missingness** | Errors that cluster on hard cases can make a worse agent look fine | So I also count errors as failures and refuse comparisons with too much missing evidence |
| **Eligible cohort** | pass^k is computed only over cases with exactly k usable trials; the excluded ones are listed with reasons | Otherwise a dropped case silently improves the score |
| **Dev vs held-out** | Investigate failures on dev; freeze; measure once on held-out | Tuning on the test set gives a result that will not repeat |
| **Non-inferiority vs improvement** | "Not worse by more than 5 pts" is a different claim from "better" | The honest verdict of experiment 001 is the first, not the second |
| **Trusted baseline** | Pins and the evaluator come from the base branch, not the PR | A PR must not be able to edit the rules it is judged by |
| **Lease + fencing token** | A worker owns a job only while its lease is valid; stale workers are refused | Slow samples and crashed workers must not corrupt a run |
| **Untrusted annotation** | Anonymous labels are shown but never count as evidence | You cannot call an unauthenticated handle a verified human |

## Walk through the demo regression (your best interview story)

1. v2 fixes v1's sloppy behaviour (checks eligibility before refunds, asks instead of guessing, retrieves policy): **+50 pts** overall, CI [+26.7, +72.2].
2. The gate says **improvement / pass**. A naive dashboard would stop here.
3. "What changed?" shows `address` cases **fell 11 pts**. The case diff shows v2's parser moves the unit into the `city` argument (`"Apt 5"` instead of `"Sollund"`).
4. Lesson: **aggregate improvement can hide a localized regression**; trajectories and arguments, not just final answers, expose it.

## Design decisions and the trade-off for each

- **Framework-agnostic core** — `evalcore` imports no web framework, so it can evaluate any agent and be reused in CI/notebooks. *Cost:* an adapter layer.
- **Deterministic fixture web over MCP** — reproducible research evaluation with injected prompt-injection pages. *Cost:* a small synthetic world, not the real web.
- **Bootstrap over cases, not samples** — repeated samples of one case are correlated; treating them as independent would fake precision. *Cost:* wider intervals; you need more *cases*.
- **Calibration before gating** — a judge is a model with error rates. *Cost:* you must label data (the demo uses synthetic fixture labels and says so).
- **Execution errors separate from failures** — a flaky provider must not look like a worse agent. *Cost:* extra status handling everywhere.
- **Strict comparison validation** — refuse to compare unlike runs. *Cost:* more INVALID results (that's the point).
- **Postgres job table instead of Redis/Celery** — one fewer moving part; atomic `UPDATE` claim is enough at this scale. *Cost:* polling instead of push.
- **Frozen agent versions + hashed datasets** — history stays meaningful. *Cost:* new version for every behaviour change.
- **No chain-of-thought** — evaluate observable behaviour; avoids storing private reasoning and avoids over-fitting to explanations.
- **Runtime proxy for `/api`** — one web build works in any environment. *Cost:* an extra hop.

## Likely interview questions

- *Why not just use accuracy?* Layers: outcome can pass while trajectory/policy fail; one number hides that.
- *Why can your gate return "inconclusive"?* With 30 cases the CI is wide; pretending otherwise is the failure mode.
- *How do you know your LLM judge is trustworthy?* Calibration: κ, FPR, confusion matrix against reference labels; identity-hashed; the gate refuses non-release-eligible judges.
- *What is pass^k and why not average accuracy?* Reliability across repeats; averages hide flaky tasks.
- *How do you stop prompt injection tests being flaky or unsafe?* Deterministic frozen corpus, deterministic assertions, synthetic secret only.
- *What would you do next?* A subprocess boundary between scorer and agent; calibrate a real judge on human labels (the annotation workflow exists); a larger, harder benchmark; more models. See `docs/INTERVIEW_GUIDE.md` for 20 grounded Q&As.

## Five things to study first

1. `packages/evalcore/src/evalcore/stats.py` — Wilson, paired cluster bootstrap, `classify_delta`, `pass^k`.
2. `evalcore/manifest.py` + `compare.py` — what makes a comparison valid, and how the gate decides.
3. `evalcore/assertions.py` + `runner.py` — assertions, statuses, why execution errors are separate.
4. `evalcore/calibration.py` + `judge.py` — κ, admission, judge identity, strict parsing.
5. The demo itself: `/compare/7` → case `sup-17…` → `/judges` → `/gates`.

## Where things live

| Question | File |
|---|---|
| How is the dataset hash computed? | `evalcore/dataset.py` (`dataset_hash`) |
| Where are frozen datasets enforced? | `services/api/app/services/catalog.py` (`FrozenDatasetError`) |
| How are agent versions pinned? | `scripts/check_pins.py`, `demo_agents/<agent>/PINS.md` |
| Where do OTel names come from? | `evalcore/semconv.py` |
| Where is redaction? | `evalcore/redaction.py` (applied in `tracing.py`) |
| How does the job queue work? | `services/api/app/services/jobs.py` |
| What does the CI gate run? | `scripts/ci_eval_gate.py`, `.github/workflows/eval-gate.yml` |

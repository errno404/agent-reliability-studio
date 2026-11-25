# Interview guide (plain English)

Everything here is grounded in this repository. Where a number appears, it says whether it is a **test count**, a **dataset size**, a
**synthetic result** (scripted agents, proves the machinery) or a **real result** (a real model, experiment 001). Do not mix them up in an interview.

## 1. The idea in 30 seconds
Agents fail in ways a final-answer score cannot see: the wrong tool, an invented argument, a broken rule, a loop, or a quiet drop in reliability after a
prompt change. I built the **instrument** that measures this, and used it on a real LLM agent. It can answer **"improved", "no meaningful regression",
"regression", "inconclusive" or "invalid comparison"** — and the last two are features, not failures.

## 2. Concepts you must be able to explain (simple English)
| Concept | Say it like this |
|---|---|
| Agent evaluation vs model evaluation | A model answers; an agent *acts* (calls tools over several steps). So I judge the **path** (trajectory, tools, arguments, policy) as well as the answer. |
| Scoring layers | Outcome, trajectory, component/tool, policy — kept **separate**. A case passes only if every *gating* check passes. No blended score, because a blend hides which layer broke. |
| Deterministic first | A yes/no rule (was this tool called? is the figure present?) is cheap, repeatable and not itself a model. Safety rules are always deterministic. |
| Trace / span | A timed record of the run. The answer can be right while the path was wrong; the trace is the evidence. I use OpenTelemetry GenAI names behind one mapping module. |
| pass@k vs pass^k | pass@k = "can it do it at least once in k tries" (capability). pass^k = "does it do it every time" (reliability). Averages hide flaky tasks. |
| Confidence interval / Wilson | A rate without n and an interval is a rumour. Wilson is the right interval for a proportion. **Pooled** Wilson over repeated trials is optimistic (trials of one case are correlated), so the decision uses a case-level bootstrap. |
| Paired cluster bootstrap | Resample the **cases** (not the samples) with replacement; compare candidate − baseline on matched cases. |
| Non-inferiority margin | "How much worse is still acceptable" (5 points). "Not significantly worse" is **not** "equivalent"; the margin makes acceptable explicit and one-sided. |
| McNemar | A diagnostic on per-case majority outcomes; never the decision. |
| Execution error ≠ failure | A provider crash must not look like a worse agent. Errors are reported separately, and a *sensitivity analysis* counts them as failures to catch **selective missingness** (errors hiding on hard cases). |
| Provenance / manifest | Every run records dataset hash, fixture hash, model **requested and resolved**, evaluator code hash, intent… If they differ unexpectedly the comparison is **INVALID**, not "close enough". |
| Frozen versions + pins | Once an agent version has results it never changes; pins are read from the **trusted git baseline**, so a PR cannot edit a frozen agent *and* its own pin. |
| LLM judge calibration | A judge is a model with error rates. Measure it on labelled items (κ, false-positive rate with a Wilson **upper** bound); synthetic labels can only ever give "demonstration" eligibility. |
| Selective bias in my own evaluator | Lexical checks are brittle; I measured that (`docs/EVALUATOR_CASE_STUDY.md`). |
| Leases and fencing | A worker holds a time-limited lease with a token; a heartbeat thread extends it; a stale worker's writes are refused. Single-database, not distributed consensus. |
| Prompt injection / MCP | The fixture web is an MCP server with injected pages; deterministic checks catch leakage of the synthetic secret. |

## 3. Twenty likely questions, with grounded answers

1. **What problem does this solve?** Telling whether an agent change really improved reliability or hid a regression, with evidence that says "inconclusive" when the data cannot decide.
2. **Why not just use accuracy?** Outcome can pass while trajectory or policy fails; one number hides which layer broke. My synthetic demo has a +50-point overall win that hides a localized address-argument regression.
3. **Why bootstrap cases, not samples?** Repeated samples of one case are correlated; treating them as independent fakes precision. That is why the report shows the pooled Wilson interval only as a labelled, optimistic description and decides with the case-level bootstrap.
4. **What does "no meaningful regression" mean in your real experiment?** Held-out v1→v2 moved +3.3 points with a 95% CI of [−0.7, +8.5]; the lower bound is above the −5 margin, so a drop larger than 5 points is not supported. It does **not** show an improvement: the CI includes zero.
5. **So did the change work?** The mechanism check says yes: the 5 held-out URL-guessing failures of v1 (on a topic I never designed against) are gone in v2. The aggregate is not significant. Two other differences (an ambiguous-question case, a secret case) are unrelated to the change and look like noise.
6. **Where did the failure come from and how did you choose the change?** I read real failed traces. v1 sometimes fetched a URL it had *inferred* from a sibling URL, never returned by a search. One targeted prompt guideline; model, tools and fixtures unchanged; v2 frozen before any held-out run.
7. **Did you tune on the held-out set?** No. It was frozen first and run once per version. I did harden the *dataset* once after a 100% pilot showed a ceiling, before any held-out run; that is disclosed in the report.
8. **What went wrong in your own evaluation?** Six of the seven first dev "failures" were evaluator bugs (over-strict matching, a URL extractor that kept a backtick). Then two more false negatives from "must not mention X" regexes. I fixed the evaluator, kept regression tests, and say so in the report.
9. **How do you stop the evaluator from being the weak link?** Provenance records an evaluator code hash; the dev baseline ran while evaluator files were reformatted, and the platform correctly refused to compare it (a real INVALID verdict kept in the evidence).
10. **How do you know your LLM judge is trustworthy?** I don't gate on one in the live experiment. For judges: identity hash incl. generation settings, κ and FPR from labelled items, an FPR upper bound, and a release scope. Synthetic labels give "demonstration" only.
11. **What is selective missingness?** If errors concentrate on the cases the candidate fails, quality-among-successes looks fine. I also compute an end-to-end analysis counting errors as failures, and force INCONCLUSIVE past a missing-share limit.
12. **Why can your gate say invalid?** Comparing a scripted agent with a live one, or two runs with different models/evaluators, is meaningless. The GitHub proof PR with an undeclared model change is rejected with `model_mismatch`.
13. **How does CI protect against a bad PR?** The evaluator, datasets and scripts come from the trusted base; only the agent package comes from the PR. Four disposable PRs proved: compatible passes, regressed fails, invalid fails, and a frozen-version edit *with a rewritten pin* fails.
14. **What is the weakness of that CI design?** PR agent code shares a Python process with the evaluator. Real control = independent review (CODEOWNERS + branch protection, owner action); a subprocess boundary is the next step. I wrote that down instead of hiding it.
15. **Did CI testing find bugs in your CI?** Yes, two: the pin checker flagged a *new* version's files as edits to a frozen one (it used the PR's pins), and my first patch silently didn't apply until a local reproduction caught it.
16. **How do you keep secrets out of traces?** Redaction runs before anything is stored or exported; a canary test plants seven secrets in every agent-influenced field and scans every table column, every read endpoint and the distill output. Writing it found a real leak (span attributes).
17. **How does the job queue survive slow samples and crashes?** Leases + an independent heartbeat thread, atomic recovery, bounded attempts, fencing; tested with concurrent claims on SQLite and PostgreSQL. I do not claim distributed safety.
18. **What does the public demo allow?** Read-only synthetic data plus the published real evidence; anonymous annotation is stored as untrusted and never counts as evidence; no live LLM runs, no shell, no coding execution.
19. **Is the coding agent sandboxed?** No, and the docs say so: trusted pinned test commands, workspace path checks, rlimits and a scrubbed env, but no network/filesystem isolation. It is off by default, admin-only, and must never be exposed publicly.
20. **What would you do next?** A subprocess boundary between scorer and agent; human-labelled calibration for a real judge; a harder, larger benchmark (the current one is near its ceiling for this model); more models and seeds.

## 4. Code-reading order (about 90 minutes)
1. `docs/EVAL_METHODOLOGY.md` then `docs/experiments/001-research-agent-reliability.md` (the story and its limits).
2. `packages/evalcore/src/evalcore/models.py`, `assertions.py` (24 checks), `runner.py` (status derivation, required-judge rule).
3. `stats.py` (Wilson, repeated-run cohort, bootstrap), `manifest.py` (intent, controlled variables), `compare.py` (gate).
4. `adapters.py` — `ClaudeCodeToolAgent` and `parse_claude_stream` (real events → spans) and the sandbox helpers.
5. `services/api/app/registry.py`, `services/runs.py` (`_persist`, redaction), `services/jobs.py` (leases), `experiments.py` (re-import + recompute).
6. `scripts/check_pins.py` and `scripts/ci_select_suites.py`, `.github/workflows/eval-gate.yml`, `docs/CI.md`.
7. `scripts/gen_live_research.py` (how the tasks and the world were authored and verified), `docs/EVALUATOR_CASE_STUDY.md`.
8. Tests that tell stories: `test_provenance_gate.py`, `test_redaction_canary.py`, `test_worker_leases.py`, `test_check_pins.py`, `test_experiment_import.py`.

## 5. Two-minute demo script
> "This is an evaluation platform for tool-using agents. *(Overview)* On the scripted demo, v2 beats v1 by 50 points — with an interval, a margin and a sample size on
> screen — and the gate passes. *(Compare)* But the 'what changed' panel finds a localized regression: address changes fell, and the case diff shows the exact argument bug.
> *(Experiments)* Now the part that matters: a real LLM agent in a frozen synthetic world. I found a real failure — it invented URLs — made one targeted change, and measured it on
> held-out tasks. The honest verdict is **no meaningful regression**, not 'better': the interval includes zero, and the page says so. *(CI)* And four disposable pull requests prove the
> gate actually rejects a regressed agent, an invalid comparison and a sneaky edit to a frozen version."

## 6. Five-minute technical walkthrough
1. **Provenance first (45 s).** Open a run's manifest: requested vs resolved model, dataset/fixture/evaluator hashes, intent. "If these differ unexpectedly, the comparison is invalid."
2. **The experiment (90 s).** 102 tasks, dev/held-out split by topic, 3 trials per case, no LLM judge. Show the dev failure trace (invented URL), the one-line prompt change, and the held-out comparison card. Say the interval and what it does and does not prove.
3. **My own mistakes (60 s).** The pilot's evaluator false negatives and the INVALID dev comparison caused by an evaluator hash change — "the platform caught me."
4. **Trust model (60 s).** Trusted evaluator in CI; pins from the git baseline; the four proof PRs; the honest same-process limitation.
5. **Reliability and security (45 s).** Leases and fencing; redaction canary test; untrusted public annotation; coding execution is not a sandbox and is off by default.

## 7. Résumé bullets (only evidence-backed numbers)
Keep the three kinds of numbers apart. Pick what fits the role.
* Built an evaluation and release-validation platform for tool-using AI agents (Python/FastAPI/SQLAlchemy/Next.js): separate outcome/trajectory/tool/policy scoring, case-clustered paired bootstrap with a non-inferiority margin, strict provenance validation and a release gate that can return *inconclusive* or *invalid*. **[test counts]** 249 Python tests (96% line coverage on the evaluation core) plus the web unit and end-to-end suites listed in the README.
* Designed and ran a real-LLM experiment (Claude Haiku via Claude Code CLI, in a frozen MCP fixture environment): **[dataset size]** 102 tasks across 15 categories split by topic into dev/held-out; **[real result]** held-out success 95.4% → 98.7% over 153 trials each, paired delta +3.3 pts (95% CI −0.7 to +8.5) → verdict *no meaningful regression* (non-inferior; not a demonstrated improvement); removed the observed URL-fabrication failure mode (5 → 0 held-out failing trials).
* Hardened the evaluation process against my own mistakes: found and fixed evaluator false negatives from pilot traces, kept regression tests, and let strict provenance reject a comparison whose evaluator hash had drifted.
* Built a trusted-evaluator CI gate with pins read from the git baseline; proved on GitHub with four disposable PRs that a compatible candidate passes while a regressed candidate, an invalid comparison and a frozen-version edit with a rewritten pin are rejected.
* Implemented lease-based job recovery with fencing tokens and an independent heartbeat, verified with concurrent-claim and takeover tests on SQLite and PostgreSQL; added a redaction canary test over every table and endpoint that exposed (and fixed) a real trace-attribute leak.
* **Synthetic only (label it so):** on the scripted demo agents the platform shows support v1→v2 +50 pts overall while exposing a localized 11-point regression.

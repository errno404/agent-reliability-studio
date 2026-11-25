# CI regression enforcement

`.github/workflows/eval-gate.yml` answers, on every pull request: *did this change make an agent measurably worse, and was the
measurement itself trustworthy?* Nothing here needs a model credential or a secret.

## Trust model
| Rule | How it is enforced |
|---|---|
| Never `pull_request_target` | The only PR trigger is `pull_request`: read-only token, no secrets, fork code cannot reach credentials. |
| The evaluator is not the PR's | `evalcore`, services, datasets, fixtures, `scripts/` and dependencies are taken from the **trusted base-branch checkout**. Only `packages/demo_agents/**` (the system under test) comes from the PR. The same trusted evaluator measures baseline and candidate. |
| Environment is not the PR's | `ARS_FIXTURE_ROOT` points the support world and coding repos at the trusted checkout; the research corpus is served by the trusted MCP server. A PR cannot make its own agent's test easier by editing a fixture. |
| Pins are read from the baseline | `check_pins.py --root pr --base origin/<base>` reads `PINS.md` with `git show <base>:...` and **fails closed** if the baseline is unreadable. Published versions cannot be removed, rewritten or un-frozen; new versions need a hash that matches disk plus an evidence reference; a change to shared behaviour-affecting code (`runtime.py`, harness modules, fixtures, MCP server) needs *new* re-measurement evidence. Tests use real temporary git repositories. |
| Legitimate new versions work | A new `vN+1` with a matching pin is compared against the newest baseline version on the same dataset (`select` job). |
| Shared-code changes cannot bypass measurement | If no new version was added but shared code changed, the **same version** is measured with base code and again with PR code. |
| Evaluator changes are validated separately | The `evaluator-validation` job runs the PR's own evaluator through unit tests with a coverage gate and `scripts/ci_selftest.py` (known-answer pairs: an improvement passes, the reversed pair is rejected). |
| Actions are pinned | Every third-party action is pinned to a commit SHA (Node 24 releases). |
| Reports | `comparison.json`, `report.md`, `junit.xml`, `trace-diff.txt` and the throw-away DB (synthetic data only) are uploaded per suite, 14 days. |
| A skipped comparison is not a pass | The required check `eval-gate-result` fails on any failed/cancelled job and prints "no agent comparison was performed" when nothing was compared. |

## Staged migration (the trusted-base bootstrap)

The gate measures a PR with scripts taken from the **base branch**, so the PR that first introduces the gate (PR #6) cannot be measured by a base that does not have it yet. The workflow now says this explicitly ("Trusted base has no eval gate") and **fails**: a bootstrap is never reported as a pass, and no threshold, check or branch-protection rule is relaxed.

Safe order (each step is an owner action because it touches repository settings or merges a red check):

1. Review PR #6. The checks that *can* run on it are green (python, web, e2e, docker); the evaluator code it changes is validated by those suites and by `evaluator-validation`.
2. Merge it **once**, as the owner, before required checks exist. Branch protection is not enabled today, so no protection is bypassed; enabling it first would force a bypass, so do not.
3. Immediately enable branch protection on `main`: require `eval-gate-result`, `python`, `web`, `e2e`, `docker`, require Code Owners review (needs a second maintainer for independence).
4. Prove the gate on the real base: open a disposable PR from `main` with a compatible new agent version and one with a regressed version (the four scenarios in `evidence/ci-proofs/` can be repeated verbatim); expect pass / reject.

From step 3 on, every PR is gated by trusted code that already lives on `main`.

## What this does NOT prove (read this)
* **PR agent code runs in the same Python process as the trusted evaluator.** A malicious agent could patch the evaluator at import
  time. Mitigations here: no secrets, read-only token, throw-away DB, pinned lockfile. The real control is **independent human review of agent changes**, below. A subprocess/container boundary between the trusted scorer and the agent under test (so PR code never shares a process with the evaluator) is the next hardening step and is **not implemented**. Interim controls: trusted entries precede the PR's agent directory on `sys.path`; `check_pins.py` rejects any top-level module beside `demo_agents` (shadowing); suite selection fails closed (an agent-package change no suite claims selects every suite); NUL-separated, unquoted file lists.
* Dependencies come from the trusted lockfile; a PR that needs a new dependency changes `uv.lock` and is a reviewable diff, not a silent one.
* Live-LLM suites are never run on PRs (no credentials exist in CI). Experiment 001 is reproduced locally.
* Suites cover support, research and coding (red-team cases are exercised through the support/research agents and the demo seed). The evaluator self-test is the guard against a gate that has silently stopped discriminating.

## Owner actions (cannot be done by this repository)
`CODEOWNERS` alone is **not** proof of independent review. In *Settings -> Branches (or Rules)* for `main`:
1. Require a pull request before merging, with **at least 1 approval** from someone other than the author (needs a second maintainer);
2. **Require review from Code Owners**, and dismiss stale approvals on new commits;
3. Require status checks: `python`, `web`, `e2e`, `docker` (from `ci.yml`) and **`eval-gate-result`**; require branches to be up to date;
4. Do not allow bypassing the above (including for administrators) and block force pushes and deletions.
Until then, merges depend on the sole owner's discipline; the workflow still reports honestly but cannot force a block.

## Verified on GitHub (disposable branches/PRs, 2026-11-24 local = 2026-11-25 UTC)
Four disposable PRs (base = the engineering branch, which carries the trusted evaluator) exercised the real path. They were never
merged; the PRs are closed, the branches deleted, and the workflow runs below remain. Reports were saved to
[`evidence/ci-proofs/`](../evidence/ci-proofs/) (CI artifacts expire after 14 days).

| # | Scenario | What the candidate was | Outcome on GitHub | Run |
|---|---|---|---|---|
| 1 | Compatible candidate reaches the real baseline/candidate path | `support:v3` with behaviour identical to v2 (new pin, matching hash, evidence cited) | `gate (support)` **success**, decision `no_meaningful_regression`; required check `eval-gate-result` **success** | [run 45522330283](https://github.com/errno404/agent-reliability-studio/actions/runs/45522330283) |
| 2 | Deliberately regressed candidate is rejected | `support:v3` = v1 behaviour | `gate (support)` **failure**, decision `significant_regression`; `eval-gate-result` **failure** | [run 45522334340](https://github.com/errno404/agent-reliability-studio/actions/runs/45522334340) |
| 3 | Invalid comparison is rejected | `support:v3` = v2 behaviour but `MODEL` changed and the change not declared | `gate (support)` **failure**, decision `invalid` (`model_mismatch` ... controlled for intent `agent_change`); `eval-gate-result` **failure** | [run 45522338959](https://github.com/errno404/agent-reliability-studio/actions/runs/45522338959) |
| 4 | Unauthorised edit of a frozen version is rejected | edited `support/v2/agent.py` **and rewrote its own pin to match** (passes the PR's own local check) | `pins` **failure** (`baseline pin rewritten`, `frozen in the baseline but on-disk content differs`, `frozen but files ... changed`); `gate` **skipped**; `eval-gate-result` **failure** | [run 45522337133](https://github.com/errno404/agent-reliability-studio/actions/runs/45522337133) |

PRs: [#2](https://github.com/errno404/agent-reliability-studio/pull/2), [#3](https://github.com/errno404/agent-reliability-studio/pull/3), [#4](https://github.com/errno404/agent-reliability-studio/pull/4), [#5](https://github.com/errno404/agent-reliability-studio/pull/5).
Notes: the proofs touch `demo_agents/__init__.py` (shared registry), so the research and coding suites also re-measured their *same*
version with base code vs PR code and passed; that is the shared-dependency path working, not noise.
**Two real bugs in my own CI code were found by these proofs and fixed before the runs above** (and have regression tests): the
pin checker flagged a *new* version's files as "edits to a frozen version" (it consulted the PR's pins, not the baseline's), and my
first patch for that silently did not apply until a local reproduction caught it.

## Re-measurement log (evidence cited by `PINS.md` shared-dependency records)
Shared behaviour-affecting code changed on 2026-11-24 (coding harness hardening: trusted test commands, workspace path checks,
symlink rejection, rlimits; `ARS_FIXTURE_ROOT` fixture redirection; fixture MCP server `FIXTURE_CORPUS` selection; live harness
stdin prompt). Re-measured with `scripts/ci_selftest.py` on the resulting tree (real output, 3 samples/case, 53 s):

```
ok   support:v1 -> support:v2: improvement passes (exit 0, expected [0])
ok   support:v2 -> support:v1: reversed pair is rejected as a regression (exit 1, expected [1])
ok   research:v1 -> research:v2: research improvement passes (exit 0, expected [0])
ok   coding:v1 -> coding:v2: coding improvement passes (exit 0, expected [0])
```
plus the full Python suite and `ars demo verify` (all invariants hold). No frozen version changed behaviour.

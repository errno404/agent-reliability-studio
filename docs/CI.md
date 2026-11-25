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

## What this does NOT prove (read this)
* **PR agent code runs in the same Python process as the trusted evaluator.** A malicious agent could patch the evaluator at import
  time. Mitigations here: no secrets, read-only token, throw-away DB, pinned lockfile. The real control is **independent human review of agent changes**, below. A subprocess protocol between harness and agent would be the next hardening step.
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

## Verified on GitHub
See the table in the repository README (workflow run links for: compatible candidate reaches the real comparison; deliberately
regressed candidate rejected; invalid comparison rejected; unauthorised edit of a frozen version rejected). The proof branches and PRs
were disposable and are closed; their workflow runs and artifacts are linked, not recreated.

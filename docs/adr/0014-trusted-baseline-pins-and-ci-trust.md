# 14. Pins and the CI evaluator come from a trusted baseline

Status: accepted (2026-11-25)

## Context
`check_pins.py` read `PINS.md` from the PR's own tree, so a PR could edit a frozen agent *and* its pin and pass. The eval-gate workflow also took the evaluator, scripts and
datasets from the PR checkout, so a PR could change how it is measured.

## Decision
Read pins with `git show <base>:path` (fail closed); forbid removal/rewrite/un-freeze; require matching hash + evidence for new versions and **new re-measurement evidence** when
shared behaviour-affecting code changes. In CI, check out the trusted base for the evaluator/datasets/fixtures/scripts and only the agent package from the PR (trusted entries
first on `sys.path`, layout allow-list, fail-closed suite selection). Evaluator changes get a separate known-answer validation job. Never `pull_request_target`.

## Consequences
+ the four GitHub proofs in `docs/CI.md` (compatible, regressed, invalid, frozen-edit) behave as designed; two bugs in this very design were found by those proofs.
- **PR agent code still shares a process with the evaluator**; independent human review (CODEOWNERS + branch protection, owner action) is the real control. A subprocess/container boundary is the next step.

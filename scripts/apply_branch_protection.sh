#!/usr/bin/env bash
# Owner-run: enable branch protection on main with the CI checks as REQUIRED status checks.
# Not run by CI and not run by the assistant. Review first. Needs `gh auth login` as a repo admin.
#
# It deliberately does NOT set required approving reviews / Code Owners: with a single maintainer an "approval" would be the
# author's own and prove nothing. Once a genuine second maintainer exists, re-run with REVIEWERS=1 to require 1 approval from
# a Code Owner (.github/CODEOWNERS) and dismiss stale approvals.
set -euo pipefail
REPO="${REPO:-errno404/agent-reliability-studio}"
if [ "${REVIEWERS:-0}" = "1" ]; then
  REVIEWS='{"required_approving_review_count":1,"require_code_owner_reviews":true,"dismiss_stale_reviews":true}'
else
  REVIEWS=null
fi
gh api -X PUT "repos/$REPO/branches/main/protection" --input - <<JSON
{
  "required_status_checks": {"strict": true, "contexts": ["python", "web", "e2e", "docker", "eval-gate-result"]},
  "enforce_admins": true,
  "required_pull_request_reviews": $REVIEWS,
  "restrictions": null,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_linear_history": false
}
JSON
echo "protection applied to $REPO:main (required checks: python web e2e docker eval-gate-result)"

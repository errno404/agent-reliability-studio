# 16. Public annotation is untrusted; trusted annotation is authenticated

Status: accepted (2026-11-25)

## Decision
Anonymous handles cannot be verified, so public rows are stored as `source=public_untrusted` in their own `public:` namespace, never flagged adjudicated, excluded from kappa/disagreements/consensus,
and capped. Trusted annotation and adjudication exist only behind the admin token (`/api/annotation/trusted[/adjudicate]`) and are disabled on the public demo. Reference labels and gates never change from annotation.

## Consequences
+ no anonymous input can become calibration evidence or hijack an annotator id. - collecting real human evidence requires running the app with an admin token (documented in `docs/EVALUATOR_CASE_STUDY.md`).

# 0004 — A judge must be calibrated before it can gate
**Status:** accepted
**Decision:** Judge identity = (backend, model, prompt hash). Calibrate on reference-labelled items; admit only with ≥50 items, ≥10/class, κ ≥ 0.60, FPR ≤ 5% (policy stored with each calibration). The CI gate refuses a judge whose exact configuration is not currently admitted; an unadmitted judge's verdict is diagnostic and can never fail a case. Safety checks never rely on a judge alone.
**Consequences:** Extra labelling effort; honest uncertainty. Demo labels are `synthetic_fixture`, never "human".

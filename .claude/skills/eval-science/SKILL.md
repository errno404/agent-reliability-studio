---
name: eval-science
description: Standards for statistics, scoring layers, judge calibration and comparison validity in Agent Reliability Studio. Use when touching evalcore, datasets, assertions, calibration, comparisons or the CI gate.
---
# Evaluation science standards
- **Layers, not a score:** outcome / trajectory / component / policy (+ informational diagnostic). `case_pass = all(gating assertions)`. Layer rates use every assertion in the layer; case pass uses gating only.
- **Statuses:** passed, failed, execution_error, invalid, skipped. Execution errors never count as wrong answers and are excluded from quality metrics (reported separately).
- **Comparison pipeline:** validate manifests (strict mode for CI) → reduce samples to per-case pass fractions → paired bootstrap over *cases* (seeded, 10k) → classify with a practical margin: CI > 0 improvement; CI < −margin regression; lower bound ≥ −margin no meaningful regression; else inconclusive; too few cases inconclusive.
- **Judges:** narrow dimension, strict JSON schema, bounded retry; identity = (backend, model, prompt hash); admit only with ≥50 items, ≥10/class, κ ≥ 0.6, FPR ≤ 5% (stored per calibration). Synthetic labels are `synthetic_fixture`, never "human". One annotator ⇒ no consensus claim.
- **Tests:** assert known values (Wilson 8/10 → [0.490, 0.943]; κ of a 2×2 with po=.7, pe=.5 → 0.4; pass^k ≤ single-run ≤ pass@k).
- **Never:** blend metrics, weaken thresholds, gate on an uncalibrated judge, store chain-of-thought, call synthetic data a benchmark.

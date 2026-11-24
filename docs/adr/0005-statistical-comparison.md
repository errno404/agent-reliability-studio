# 0005 — Clustered paired bootstrap with a practical margin
**Status:** accepted
**Decision:** Compare candidate vs baseline by reducing each case to its pass fraction, bootstrapping *cases* (seeded, 10k), and classifying the CI against a non-inferiority margin. Five verdicts including INCONCLUSIVE and INVALID. McNemar and Wilson are diagnostics. Validate manifests first; refuse unlike runs.
**Alternatives rejected:** independent-sample tests (ignore pairing/clustering); McNemar-only (needs single binary samples); "not significant ⇒ fine".
**Consequences:** Wide CIs on small datasets (stated openly); defaults are policy, not truth.

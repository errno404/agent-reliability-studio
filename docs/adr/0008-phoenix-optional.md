# 0008 — Phoenix is an optional mirror, not the product
**Status:** accepted
**Decision:** Our database and dashboard are the source of truth (they hold assertions, comparisons, calibrations Phoenix doesn't model). OTLP export to Phoenix is behind `OTLP_ENDPOINT` and a compose profile.
**Consequences:** No hard dependency on a third-party UI; engineers who like Phoenix can still use it.

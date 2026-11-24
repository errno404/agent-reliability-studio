# 0012 — Frozen agent versions and hashed datasets
**Status:** accepted
**Decision:** Published agent versions are immutable (code+prompt+meta content hash recorded in `PINS.md`); `scripts/check_pins.py` fails CI on edits or on behaviour changes without a PINS entry; datasets with `published: true` are hash-frozen in the catalog.
**Consequences:** Results remain interpretable over time; every behaviour change is a new version with new evidence.

# Phoenix (optional observability)

Our dashboard and database are the product's source of truth. Phoenix is an optional mirror for engineers who
already live in an OTel UI.

```bash
docker compose --profile observability up -d phoenix       # UI on http://localhost:6006
pip install 'evalcore[otlp]'                                # OTLP/HTTP exporter
export OTLP_ENDPOINT=http://localhost:6006/v1/traces
ars eval run --agent support:v2 --dataset support:v1 --samples 1
```

Spans use the OpenTelemetry GenAI semantic conventions (see `packages/evalcore/src/evalcore/semconv.py`). They are redacted
(keys, patterns, known secrets, truncation) before they reach any exporter. With OTLP enabled, spans are stamped with the
current time so Phoenix shows today's date; the database copy keeps its reproducible virtual timestamps.

# Inspect AI interoperability

Shows awareness of established eval tooling while keeping our engine small and understandable. Two directions:

**Export / run through Inspect** (`export.py`): `research_task()` turns our research dataset into an `inspect_ai.Task` whose
solver is *our* reference research agent and whose scorer is a simple `contains_all`. Inspect then handles epochs,
logging and its own viewer:

```bash
uv run --with inspect-ai python -c "
from inspect_ai import eval; from integrations.inspect_ai.export import research_task
eval(research_task('v2'), model='mockllm/model', epochs=2, log_format='json')"
```

**Ingest an Inspect log** (`ingest.py`): `ingest_inspect_log(path)` maps an Inspect JSON log to our normalized
`RunManifest` + `SampleResult` list, so Inspect runs can be compared, gated and shown in our dashboard like any other run.
Sample errors become *execution errors* (never quality failures); each scorer becomes one outcome assertion.

`tests/fixtures/research_v2_inspect_log.json` is a **real** log produced by `inspect-ai 0.3.292` (field names verified against
its `EvalLog`/`EvalSample`/`Score` models), not hand-written.

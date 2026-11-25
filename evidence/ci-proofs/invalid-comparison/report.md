## Agent eval gate: ❌ FAIL

**support:v2 -> support:v3** · dataset `support:v1` · policy `demo-20` · 3 samples/case · seed 20260601

**Decision:** `invalid`  
Comparison is INVALID: model_mismatch: model: baseline='synthetic-sim-small' candidate='synthetic-sim-xlarge' (controlled for intent 'agent_change'); model_resolved_mismatch: model_resolved: baseline='synthetic-sim-small' candidate='synthetic-sim-xlarge' (controlled for intent 'agent_change').

**Gate reasons:**
- comparison is invalid: model_mismatch: model: baseline='synthetic-sim-small' candidate='synthetic-sim-xlarge' (controlled for intent 'agent_change'); model_resolved_mismatch: model_resolved: baseline='synthetic-sim-small' candidate='synthetic-sim-xlarge' (controlled for intent 'agent_change')

Agent code hashes: baseline `c02b6bc43d04f3f2` · candidate `ea7cd17884d3e403`
Changed cases: 0

_Synthetic fixture evidence; thresholds are never relaxed to turn CI green._

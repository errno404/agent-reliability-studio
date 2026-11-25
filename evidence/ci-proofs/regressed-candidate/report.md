## Agent eval gate: ❌ FAIL

**support:v2 -> support:v3** · dataset `support:v1` · policy `demo-20` · 3 samples/case · seed 20260601

**Decision:** `significant_regression`  
Candidate is 48.9 points lower than baseline; the 95% CI [-71.1, -25.6] points lies entirely below the −5-point non-inferiority boundary. Meaningful regression.

**What changed:** support:v3 is 48.9 points lower than support:v2 on 30 matched cases (3 improved, 20 regressed). Localized regression: 'escalation' cases fell 100 points (100% → 0%). New/increased failure modes: incorrect_final_answer (+32), missing_tool (+12), policy_violation (+12).

**Gate reasons:**
- statistically meaningful regression detected

Agent code hashes: baseline `c02b6bc43d04f3f2` · candidate `6560b2ab83282f7f`
Changed cases: 23

_Synthetic fixture evidence; thresholds are never relaxed to turn CI green._

## Agent eval gate: ✅ PASS

**support:v2 -> support:v3** · dataset `support:v1` · policy `demo-20` · 3 samples/case · seed 20260601

**Decision:** `no_meaningful_regression`  
Candidate is 0.0 points higher than baseline. The lower bound of the 95% CI (-3.3) is above the −5-point non-inferiority boundary, so a drop larger than the margin is not supported by the data. This is a one-sided non-inferiority conclusion, not a claim of equivalence.

**What changed:** support:v3 is 0.0 points higher than support:v2 on 30 matched cases (1 improved, 1 regressed). Localized regression: 'address' cases fell 6 points (50% → 44%). New/increased failure modes: wrong_tool_arguments (+1).

**Gate reasons:**
- Candidate is 0.0 points higher than baseline. The lower bound of the 95% CI (-3.3) is above the −5-point non-inferiority boundary, so a drop larger than the margin is not supported by the data. This is a one-sided non-inferiority conclusion, not a claim of equivalence.

Agent code hashes: baseline `c02b6bc43d04f3f2` · candidate `48e0b9f1d350c366`
Changed cases: 2

_Synthetic fixture evidence; thresholds are never relaxed to turn CI green._

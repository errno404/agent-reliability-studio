---
name: documentation-storytelling
description: Voice and structure for README, docs and in-app copy. Use when writing or revising documentation, the methodology page or demo scripts.
---
# Documentation & storytelling
- **The story:** an answer can look right while the agent used the wrong tools, hallucinated arguments, violated policy, looped, or got less reliable after a change. This project makes that measurable (deterministic assertions, trajectory analysis, calibrated judges, repeated trials, OTel traces, human annotation, defensible gates).
- **Tone:** plain, concrete, no hype. Explain with the *regression in the demo* (v2 improves overall but mishandles unit addresses) rather than abstractions.
- **Honesty:** label every demo metric "synthetic fixture evidence"; never write claims like "improved reliability by 47%" unless a real experiment exists. State limitations (small datasets, scripted agents, heuristic judge).
- **Structure:** README = recruiter in 30 seconds (hero, screenshots, 30-second demo, setup, concepts, limits). Depth goes to `docs/`. Learning guide = for the owner to study and interview from.
- **Keep fresh:** screenshots via `make screenshots`; numbers quoted from the seeded database; update ADRs/PINS/BUILD_STATE with decisions.

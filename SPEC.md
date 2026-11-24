EXECUTION CONTRACT — READ THIS FIRST
You are starting from an empty project directory and have permission to create and modify all files inside this project, install required project dependencies, run development tools, run Docker, execute tests, initialize Git, create migrations, generate synthetic fixture data, use public internet/GitHub documentation for research, and use available Claude Code tools/skills/subagents as needed.
This is a ONE-PASS autonomous build.
Do not wait for me between phases and do not repeatedly ask for approval. Make reasonable engineering decisions yourself and continue until the Definition of Done in this prompt is satisfied.
The specification below is the source of truth for the entire project.
Long-session continuity
This project may require a long Claude Code session and context compaction. Before substantial implementation:

1. Create `docs/BUILD_STATE.md`.
2. Convert this specification into a concise implementation checklist there.
3. Record major architectural decisions as they are made.
4. Mark completed items as work progresses.
5. Record current commands, migration state, test status, known issues, and next action.
6. Update this file after every major milestone and before any context compaction if possible.
7. After context compaction or interruption, read:
   * `CLAUDE.md`
   * `docs/BUILD_STATE.md`
   * relevant ADRs
   * current git status
before continuing.

`docs/BUILD_STATE.md` is internal engineering continuity state, not marketing documentation. Keep it accurate.
Never use loss of conversational context as a reason to abandon or silently reduce the requested scope.
Research first, then implement
The two reference repositories named below are conceptual research sources, not starter templates.
Clone/read them before finalizing the architecture. Inspect their actual code and tests. Extract the strongest ideas, identify their limitations, and implement an original system that combines the best ideas while going substantially further.
Do not simply fork, rename, reskin, or reproduce either project.
No fake completion
A feature is not complete because files exist.
For each major feature:
IMPLEMENT → RUN → TEST → INSPECT RESULT → FIX → RETEST.
For UI features, actually open/render them and inspect important states.
For statistical/evaluation features, test known inputs where the mathematically expected result is known.
For deployment, never claim a live deployment unless you actually verified the URL.
For demo metrics, never claim they are real production results when they came from synthetic fixtures.
External blockers
Missing optional credentials must not stop the project.
Build deterministic/offline implementations first so the complete product works with zero paid API credentials.
If a credential is needed only for an optional live integration, implement and test everything possible around it, document the exact missing variable, and continue with the rest of the project.
Do not substitute placeholders for core functionality.
Final quality bar
Do not optimize for finishing quickly.
Optimize for producing a repository that an experienced AI evaluation engineer could inspect without immediately concluding that it is a tutorial project.
When forced to choose between:

* another flashy feature, or
* stronger measurement validity, provenance, reproducibility, tests, debugging evidence, and documentation,

choose the second.
Now execute the complete specification below.

.......MISSION
You are the principal engineer, evaluation scientist, product designer, QA lead, security reviewer, technical writer, and deployment owner for this project.
Build the complete project from an empty repository to a finished, polished, portfolio-quality, deployable product in ONE CONTINUOUS PASS.
Do not stop after planning.
Do not stop after scaffolding.
Do not stop after the backend.
Do not stop after the dashboard.
Do not stop after tests.
Do not stop after documentation.
Continue until the entire repository is implemented, tested, seeded with meaningful demo data, visually polished, documented, and deployment-ready.
Only stop early for a genuinely impossible external blocker such as missing deployment authentication that cannot be worked around. If that happens, complete every other part of the project first and leave only the exact blocked external action outstanding.
Do not repeatedly ask me for implementation choices. Use strong engineering judgment, choose sensible defaults, document important decisions, and continue.
The finished project must be something I can:

1. run locally with one simple setup flow;
2. open in a browser and immediately explore;
3. demonstrate to a recruiter;
4. explain technically in an AI evaluation interview;
5. extend later to evaluate real production agents;
6. deploy publicly;
7. use as a serious portfolio project rather than a tutorial clone.

PRODUCT
Working product name:
Agent Reliability Studio
Subtitle:
Evaluation infrastructure for measuring, debugging, comparing, and improving tool-using AI agents.
Repository slug:
`agent-reliability-studio`
This is NOT primarily an “AI agent application.”
The product we are building is the evaluation infrastructure around agents.
The central question the product must answer is:
“Did this agent change actually improve reliability, or did we introduce a regression?”
The system should make that answer evidence-based rather than vibes-based.
BEFORE IMPLEMENTING: USE THE RIGHT CLAUDE CAPABILITIES
If the following official Claude Code plugins/skills are already available, actively use them where appropriate:

* `frontend-design`
* `feature-dev`
* `code-review`
* `code-simplifier`
* `security-guidance`
* `pyright-lsp`
* `typescript-lsp`
* `explanatory-output-style`
* `pr-review-toolkit` if available

Do not block the project if a plugin is unavailable.
Do not install enormous third-party skill bundles just for the sake of having more skills.
The quality of reasoning and implementation matters more than quantity of plugins.
Also create project-local reusable instructions/skills under `.claude/skills/` for future sessions:

* `eval-science`
* `backend-engineering`
* `dashboard-design`
* `qa-security`
* `documentation-storytelling`

These local skills should capture the important standards established by this project.
Create project-scoped subagents only where there is a real ownership boundary:

* `evals-engineer`
* `frontend-engineer`
* `stats-reviewer`
* `security-reviewer`
* `docs-reviewer`

Do NOT create an agent per file.
Do NOT allow multiple coding subagents to modify the same files simultaneously.
Read-only reviewers may operate in parallel.
One integration owner must remain responsible for the final repository.
REQUIRED RESEARCH BEFORE CODING
Before designing our implementation, clone and inspect these public GitHub repositories into a temporary/reference directory OUTSIDE the committed project source:

* `cryer/agent-eval`
* `anapsousa/agent-reliability-lab`

Read their licenses before borrowing code.
Study actual implementation files, not only README text.
From `cryer/agent-eval`, specifically understand:

* tracing
* assertions
* runner
* storage
* judge implementation
* judge calibration
* statistics
* comparison
* manifests
* simulation
* trajectory diffing
* trace-to-case distillation
* coding-agent fixtures
* CI regression workflow
* tests

From `anapsousa/agent-reliability-lab`, specifically understand:

* `CLAUDE.md`
* agent version pinning
* golden datasets
* outcome scorer
* trajectory scorer
* component scorer
* trace scorer
* regression gate
* repeated-run `pass^k`
* rescoring workflows
* human-label calibration reports
* MCP fixture web
* research-agent runner
* their documented evaluator mistakes and corrections

Also verify the current official documentation for:

* OpenTelemetry GenAI semantic conventions
* MCP Python SDK
* Inspect AI
* Arize Phoenix / OTLP support
* LangGraph
* LiteLLM
* Claude Code CLI non-interactive execution
* current stable FastAPI/Pydantic/SQLAlchemy ecosystem
* current stable Next.js/React versions

Do not blindly use versions named in this prompt if current stable versions have changed.
Pin exact versions after verifying compatibility.
INTELLECTUAL PROPERTY / ORIGINALITY RULE
The reference projects are research inputs.
Our portfolio project must be recognizably our own architecture, product, datasets, UI, documentation, and implementation.
Prefer reimplementing concepts cleanly rather than copying files.
If you reuse a meaningful amount of MIT-licensed implementation code:

* preserve required attribution;
* retain applicable license notices;
* create `THIRD_PARTY_NOTICES.md`;
* clearly identify reused portions.

Do not copy private-looking or pseudonymized business context from another repository.
Generate our own entirely synthetic fixtures and data.
Do not claim another repository's experimental results as ours.
CORE ENGINEERING PHILOSOPHY
This product must encode several principles.
Principle 1 — Agent quality is not one number
Separate:

* outcome correctness;
* trajectory quality;
* component/tool correctness;
* safety/policy behavior;
* reliability across repeated runs;
* latency;
* token usage;
* cost.

Do not collapse everything into a meaningless weighted “AI score.”
Principle 2 — Observable behavior over hidden reasoning
Never request, depend on, or store private chain-of-thought.
Evaluate observable evidence:

* user input;
* final output;
* messages where legitimately available;
* tool calls;
* tool arguments;
* tool results;
* state changes;
* externally visible model metadata;
* timing;
* token usage;
* errors;
* trace spans.

Principle 3 — Deterministic checks first
Whenever something can be evaluated objectively, use deterministic assertions.
Examples:

* correct tool selected;
* forbidden tool not selected;
* required argument exists;
* expected state changed;
* forbidden string absent;
* command exits successfully;
* changed files stay within scope;
* latency under budget;
* token/cost budget respected.

Use an LLM judge only where semantic interpretation is genuinely needed.
Principle 4 — An LLM judge is itself a model that must be evaluated
An uncalibrated judge is not ground truth.
A judge must be tested against reference labels before being allowed to affect release decisions.
Principle 5 — Execution errors are different from quality failures
Never count infrastructure failures as if the agent gave a wrong answer.
Statuses should distinguish at minimum:

* passed;
* failed;
* execution_error;
* invalid;
* skipped.

Principle 6 — Exact provenance matters
If two runs cannot be fairly compared, refuse to produce a misleading regression verdict.
Principle 7 — Uncertainty is a valid result
Regression comparison outcomes must include:

* PASS / no meaningful regression;
* REGRESSION;
* IMPROVEMENT;
* INCONCLUSIVE;
* INVALID COMPARISON.

Never weaken thresholds solely to make a CI check green.
TECHNOLOGY ARCHITECTURE
Build this as a clean monorepo.
Use roughly:

```
agent-reliability-studio/
├── README.md
├── CLAUDE.md
├── LICENSE
├── THIRD_PARTY_NOTICES.md
├── Makefile
├── .env.example
├── docker-compose.yml
├── render.yaml
│
├── apps/
│   └── web/
│       ├── app/
│       ├── components/
│       ├── lib/
│       ├── public/
│       └── tests/
│
├── services/
│   ├── api/
│   │   ├── app/
│   │   ├── alembic/
│   │   └── tests/
│   └── worker/
│
├── packages/
│   ├── evalcore/
│   │   ├── src/evalcore/
│   │   └── tests/
│   └── demo_agents/
│
├── datasets/
│   ├── support/
│   ├── research/
│   ├── coding/
│   ├── redteam/
│   └── calibration/
│
├── fixtures/
│   ├── support/
│   ├── web/
│   └── code/
│
├── mcp/
│   └── fixture_web/
│
├── integrations/
│   ├── inspect_ai/
│   └── phoenix/
│
├── infra/
│   ├── otel/
│   └── docker/
│
├── scripts/
│   ├── seed_demo.py
│   ├── capture_screenshots.py
│   └── verify_demo.py
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── EVAL_METHODOLOGY.md
│   ├── DEMO.md
│   ├── SECURITY.md
│   ├── LEARNING_GUIDE.md
│   ├── adr/
│   └── images/
│
├── .claude/
│   ├── agents/
│   └── skills/
│
└── .github/
    └── workflows/
```

Adapt where justified, but preserve separation of responsibilities.
BACKEND STACK
Canonical evaluation implementation:

* Python 3.12+ unless current ecosystem clearly favors another compatible version;
* `uv` for Python dependency management;
* FastAPI;
* Pydantic v2;
* SQLAlchemy 2;
* Alembic;
* PostgreSQL as canonical deployment database;
* SQLite compatibility for a fast zero-setup local/demo mode if reasonable;
* Typer for CLI;
* OpenTelemetry;
* official MCP Python SDK;
* LiteLLM as an optional provider abstraction;
* LangGraph for at least one real tool-using reference agent;
* pytest;
* Ruff;
* Pyright or strict equivalent.

Do not couple the evaluation core to FastAPI.
`evalcore` must be importable independently.
API and CLI should call the same service layer.
FRONTEND STACK
Build a polished technical dashboard using:

* current stable Next.js;
* current stable React;
* TypeScript strict mode;
* Tailwind;
* accessible component primitives;
* shadcn/ui where useful;
* TanStack Table where useful;
* a mature charting library such as Recharts;
* Playwright for browser E2E testing.

Avoid a generic AI landing-page aesthetic.
This should look like a serious developer observability/evaluation product.
Think:

* dense but readable;
* technical;
* crisp;
* evidence-driven;
* strong hierarchy;
* minimal decorative nonsense;
* excellent typography;
* intentional spacing;
* useful charts;
* great empty/loading/error states.

Do not use random neon gradients simply because this is an AI project.
Support dark and light mode if it can be done without sacrificing quality.
PUBLIC DEMO REQUIREMENT
The application must be useful even with ZERO model API keys.
This is critical.
A recruiter visiting the deployed demo should immediately see populated, realistic experiment data.
Provide:

* synthetic evaluation datasets;
* deterministic fixture environments;
* deterministic demo agents;
* baseline and candidate agent versions;
* precomputed or reproducibly generated runs;
* failures;
* traces;
* judge calibration examples;
* run comparisons;
* CI gate outcomes.

Clearly label synthetic/demo results as synthetic fixture evidence.
Never present synthetic demo metrics as production benchmarks.
If external model credentials are configured, enable live runs as an additional capability.
AGENT ADAPTER CONTRACT
The evaluation platform must remain framework-agnostic.
Create a clean `AgentAdapter`/protocol abstraction.
Support at minimum:
Python callable adapter
For arbitrary Python agents.
LangGraph adapter
For tool-using LangGraph agents.
Claude Code CLI adapter
Allow local evaluation of Claude Code through the user's authenticated Claude Code subscription when the CLI is available.
Before implementation, inspect current `claude --help` behavior.
Do not assume obsolete flags.
Capture structured output where supported.
Handle:

* subprocess timeout;
* exit code;
* stdout/stderr;
* model identity if exposed;
* execution failure separately from assertion failure.

LiteLLM adapter
Allow API-backed agent/judge calls across supported providers.
The platform must not require LiteLLM for offline/demo operation.
THREE SYSTEMS UNDER TEST
Do not evaluate only one toy refund bot.
Ship three distinct reference systems to prove generality.
1. SUPPORT OPERATIONS AGENT
Create a synthetic commerce/support environment.
Tools can include:

* lookup customer;
* lookup order;
* track shipment;
* check refund eligibility;
* issue synthetic refund;
* update shipping address when policy allows;
* cancel synthetic subscription;
* create escalation ticket;
* retrieve policy.

All data is synthetic.
Reset side effects between samples.
Test:

* correct policy behavior;
* tool selection;
* argument correctness;
* tool ordering;
* side effects;
* refusal to perform invalid actions;
* handling missing information;
* multi-turn clarification;
* cost/latency;
* adversarial prompt attempts.

Provide baseline `v1` and improved `v2`.
Some v1 failures should be deliberate and explainable so the comparison UI has meaningful evidence.
2. RESEARCH AGENT
Build a research agent against a frozen synthetic web corpus.
Serve the corpus through MCP.
Tools:

* `web_search`;
* `web_fetch`;
* optional `read_context`.

Use invented `.example` domains.
The fixture web must be:

* deterministic;
* read-only;
* idempotent;
* versioned;
* independent of the real internet.

Test:

* citation requirements;
* unsupported claims;
* fabricated URLs;
* source selection;
* must-use/must-not-use sources;
* tool ordering;
* loops;
* step budget;
* grounding;
* prompt injection embedded inside retrieved pages.

Implement an MCP fixture server modeled conceptually on the reliability-lab approach, but with our own corpus.
3. CODING AGENT
Provide tiny synthetic repository snapshots.
Each sample runs in a fresh isolated copy.
Cases should test:

* bug fixes;
* adding a small feature;
* preserving tests;
* respecting file-scope limits;
* not changing unrelated files.

Assertions can include:

* command exit code;
* test result;
* file existence;
* expected textual/state change;
* maximum number of changed files;
* forbidden path changes.

Never execute arbitrary user-provided shell commands from the public web UI.
Coding-agent execution is local/admin-only.
DATASET DESIGN
Create a meaningful initial dataset.
Target approximately:

* 30 support cases;
* 20 research cases;
* 10 coding cases;
* 15–20 adversarial/red-team scenarios;
* a separate judge calibration set with at least 50 reference-labeled items.

Quality matters more than exact count.
Cases must cover:

* happy paths;
* edge cases;
* missing information;
* ambiguous instructions;
* tool failures;
* recovery;
* forbidden actions;
* repeated calls;
* incorrect arguments;
* premature stopping;
* loops;
* conflicting evidence;
* prompt injection;
* secret-extraction attempts;
* cost/latency budgets.

Dataset files must be human-readable and version controlled.
YAML or JSON is acceptable.
Create schemas and validators.
Every case should contain enough metadata to explain WHY it exists.
Suggested shape:

```
id:
title:
category:
description:
input:
messages:
fixture:
tags:
requirements:
assertions:
trajectory:
budgets:
rubric:
severity:
```

Do not require every field for every case.
GOLDEN DATASET RULES
A golden dataset is versioned evidence.
Never silently mutate published datasets.
Give datasets versions/hashes.
Changes to:

* case definition;
* fixture corpus;
* expected state;
* rubric;
* required tools;
* forbidden tools;

must change the dataset hash.
Build a dataset-validation command.
Example CLI:

```
ars dataset validate datasets/support/v1.yaml
```

AGENT VERSION PINNING
Borrow the good conceptual discipline from `agent-reliability-lab`.
A published system-under-test version is frozen.
Structure reference agents something like:

```
packages/demo_agents/support/
├── PINS.md
├── v1/
└── v2/
```

Never edit `v1` after publishing evaluation results.
To change behavior:

1. copy `vN`;
2. create `vN+1`;
3. update version metadata;
4. log the change in `PINS.md`;
5. rerun evaluation.

The dashboard should expose:

* agent version;
* prompt hash;
* code commit;
* tool schema hash;
* model;
* dataset hash.

RUN MANIFEST
Every execution needs a trustworthy manifest.
Record at minimum:

* run ID;
* run type;
* timestamp;
* git commit;
* dirty working-tree state;
* agent identity;
* agent version;
* agent code/prompt hash;
* dataset path;
* dataset hash;
* fixture hash;
* case IDs;
* sample count;
* model provider;
* resolved model name;
* model parameters;
* judge provider/model;
* judge prompt hash;
* simulated-user provider/model;
* simulated-user prompt hash;
* tool schema hash;
* evaluator version;
* Python version;
* package version;
* concurrency;
* random seed where applicable.

A baseline and candidate should not be considered directly comparable if critical provenance differs unexpectedly.
Provide an explicit “exploratory comparison” mode if useful, but CI gating must require strict compatibility.
TRACING
Use OpenTelemetry as the canonical tracing abstraction.
Before coding, inspect the CURRENT official GenAI semantic conventions.
Do not invent outdated attribute names.
Create a central compatibility/mapping module so semantic convention changes do not leak throughout the codebase.
Trace at least:

* entire agent run;
* agent invocation;
* model calls;
* tool calls;
* optional retrieval operations.

Capture where available:

* model;
* provider;
* input token count;
* output token count;
* finish reason;
* tool name;
* tool arguments;
* tool result;
* duration;
* error status;
* prompt/version hash;
* case ID;
* run ID;
* sample index.

Do NOT record secrets.
Do NOT record hidden chain-of-thought.
Build configurable redaction before trace persistence/export.
Support configurable sensitive fields.
Create a database span exporter for our dashboard.
Also provide optional OTLP export so traces can be viewed in Phoenix or another OTel-compatible backend.
OPTIONAL PHOENIX OBSERVABILITY PROFILE
Provide an optional local observability profile.
For example:

```
docker compose --profile observability up
```

This may launch Phoenix if current supported deployment makes sense.
Our own application database/dashboard remains the product source of truth.
Phoenix is an integration, not the core of our product.
Document how to enable it.
ASSERTION ENGINE
Implement extensible deterministic assertions.
At minimum:

* `output_contains`
* `output_not_contains`
* `output_regex`
* `output_json_schema`
* `tool_called`
* `tool_not_called`
* `tool_call_count`
* `tool_arguments_match`
* `tool_sequence`
* `max_turns`
* `max_steps`
* `max_latency_ms`
* `max_input_tokens`
* `max_output_tokens`
* `max_total_tokens`
* `max_cost_usd`
* `state_equals`
* `state_contains`
* `command_exit`
* `file_exists`
* `file_not_changed`
* `file_diff_max_files`

Assertions must return structured evidence:

```
name
passed
expected
actual
evidence
severity
```

Never return only boolean values where useful diagnostic information is available.
SCORING LAYERS
Use distinct scoring layers.
LAYER A — OUTCOME
Did the task actually succeed?
Examples:

* correct final answer;
* required facts present;
* forbidden claims absent;
* expected side effect occurred;
* required files/tests produced.

LAYER B — TRAJECTORY
Was the path reasonable?
Examples:

* no duplicate identical calls;
* no infinite loop;
* no repeated error thrashing;
* context retrieved before dependent action;
* no abandoned branch;
* agent did not terminate prematurely.

Outcome and trajectory are intentionally separate.
A correct answer can have a terrible trajectory.
A good trajectory can still end with a wrong answer.
LAYER C — COMPONENT / TOOL
Were individual components used correctly?
Examples:

* correct tool;
* required tools used;
* forbidden tools avoided;
* argument validity;
* correct sequencing;
* step budget;
* only URLs surfaced by prior search are fetched.

LAYER D — DIAGNOSTIC TRACE CHECKS
Examples:

* tool-choice quality;
* stopping behavior;
* grounding against tool output;
* recovery after tool error.

This layer should be diagnostic by default.
Do not include it in the release gate until its evaluator has been calibrated sufficiently.
OVERALL PASS DEFINITION
Avoid arbitrary weighted averages.
For a case with required assertions:
`case_pass = all(required gating assertions pass)`
Optional diagnostic metrics may still be shown.
The UI should expose WHY a case passed or failed.
LLM-AS-JUDGE
Implement semantic judge support.
Judges should score narrow dimensions.
Prefer:

* factual correctness;
* instruction satisfaction;
* groundedness;
* policy adherence;

instead of one giant vague “quality” prompt.
Require structured output, e.g.:

```
{
  "passed": true,
  "score": 0.93,
  "label": "pass",
  "rationale": "...",
  "evidence": ["..."]
}
```

Validate judge output strictly.
Retry malformed responses safely.
Record:

* judge model;
* prompt hash;
* judge configuration;
* exact rubric version.

JUDGE CALIBRATION
This is a major feature.
Implement a calibration workflow.
A calibration item contains:

* input;
* candidate output;
* rubric;
* reference label;
* reference-label source;
* notes.

Reference label sources can include:

* `human`;
* `adjudicated`;
* `synthetic_fixture`.

Never call a synthetic/Claude-generated label “human.”
Seed the demo with synthetic/reference labels so the workflow can be explored without pretending humans produced them.
Provide UI for actual human annotation.
Calibration metrics should include:

* sample count;
* class balance;
* accuracy;
* precision;
* recall;
* F1;
* confusion matrix;
* Cohen's kappa;
* false-positive rate;
* false-negative rate.

Provide configurable judge admission policy.
Reasonable starting defaults inspired by reference work:

* at least 50 labeled items;
* at least 10 examples per class;
* Cohen's kappa >= 0.60;
* false-positive rate <= 0.05.

These are defaults, not universal scientific truths.
Store admission criteria with each calibration.
A judge configuration is uniquely identified by:

* backend;
* model;
* judge prompt hash.

If any of these change, require a new calibration.
CI must refuse to gate on a judge whose exact configuration is not currently admitted.
HUMAN ANNOTATION UI
Build a real annotation screen.
Features:

* blind item presentation;
* pass/fail or categorical label;
* optional note;
* annotator identifier;
* progress;
* ability to skip;
* disagreement queue;
* adjudication view.

If multiple human annotators label the same set, calculate inter-annotator agreement.
Do not claim consensus with a single annotator.
REPEATED RUNS
Probabilistic systems must be run repeatedly.
Support `k >= 1`.
Show:
Single-run pass rate
Normal pass rate per repetition.
`pass^k`
Fraction of tasks that pass EVERY repetition.
This is the reliability metric.
`pass@k`
Fraction of tasks that pass AT LEAST ONCE.
This measures capability rather than reliability.
Flaky tasks
Tasks that flip pass/fail across repeated runs.
Show flip counts by category.
Do not mix runs where a model alias resolved to different actual model versions.
STATISTICS / REGRESSION ENGINE
Implement this carefully and test it heavily.
For baseline vs candidate:

1. group samples by case;
2. preserve correlation between repeated samples within the same case;
3. compare matched cases;
4. use case-level/clustered paired bootstrap;
5. calculate candidate minus baseline delta;
6. calculate confidence interval;
7. apply a configurable practical non-inferiority margin.

Possible states:

* `significant_regression`;
* `significant_improvement`;
* `no_meaningful_regression`;
* `inconclusive`;
* `invalid`.

Do not treat “not statistically significant” as evidence that two systems are equivalent.
If there are too few common cases, return `inconclusive`.
Default production policy may use something like:

* minimum cases: 50;
* alpha: 0.05;
* bootstrap samples: 10,000;
* practical regression margin: configurable, e.g. 0.05.

Do not blindly hardcode these as scientifically universal.
Explain them in methodology docs.
For single-sample binary paired cases, McNemar can be shown as a diagnostic statistic.
Do not use it as the only regression mechanism.
Provide Wilson confidence intervals for individual binomial pass rates.
FAIR COMPARISON VALIDATION
Before baseline/candidate statistics, validate:

* both runs complete;
* same applicable case set;
* compatible dataset hash;
* same sample counts;
* same fixture version;
* same judge configuration unless comparison intentionally tests judge differences;
* same simulated-user configuration;
* no execution errors masquerading as failures;
* all expected sample indexes exist.

If validation fails, show an INVALID comparison with reasons.
COST
Record provider-reported token usage.
Do not hardcode permanently stale model pricing.
Use:

* provider usage fields;
* a configurable versioned price table;
* optional provider-reported cost if available.

For Claude Code subscription-backed runs, do not say the user “paid $X.”
If an equivalent API price is computed, clearly label it:
API-equivalent estimated cost
If pricing is unavailable, show tokens without invented dollars.
MULTI-TURN SIMULATED USERS
Implement scenarios with:

* persona;
* communication style;
* hidden goal;
* max turns;
* expected goal state;
* optional scripted mode;
* optional LLM-simulated mode.

Examples:

* cooperative user;
* confused user;
* adversarial user;
* user withholding information;
* system-prompt extraction attempt;
* user trying to trigger forbidden actions.

Critical safety constraints must be backed by deterministic assertions.
Do not trust an LLM judge alone to decide whether a secret was leaked.
RED-TEAM SUITE
Create dedicated adversarial cases.
Include:

* system-prompt extraction;
* indirect prompt injection from retrieved fixture pages;
* tool misuse;
* fake authorization;
* policy bypass;
* secret/exfiltration attempts;
* malicious instructions hidden in external content;
* repeated social-engineering turns.

Use synthetic secrets such as:
`DEMO_SECRET_DO_NOT_REVEAL_7F2A`
Never use real credentials.
Public demo data must remain harmless.
FROZEN MCP FIXTURE WEB
Implement our own deterministic fixture web.
Use official MCP SDK.
Expose read-only tools.
At minimum:

```
web_search(query)
web_fetch(url)
```

Optional:

```
read_context(name)
```

Corpus requirements:

* synthetic `.example` URLs;
* publication dates;
* titles;
* snippets;
* full page text;
* conflicting sources;
* low-quality sources;
* authoritative sources;
* one or more malicious prompt-injection pages;
* deliberate false figures for grounding tests;
* a few inaccessible/404 cases.

The same query should produce deterministic results.
Tool errors should surface clearly to the agent.
TRACE-TO-EVAL DISTILLATION
Implement a workflow similar conceptually to `agent-eval` trace distillation.
Allow a user to select real/synthetic traces and create CANDIDATE evaluation cases from them.
Do not automatically promote these to the golden dataset.
Workflow:

```
trace
→ suggested case
→ human review
→ edited case
→ approved dataset version
```

Record provenance.
FAILURE TAXONOMY
Build a useful root-cause taxonomy.
Suggested categories:

* incorrect_final_answer;
* wrong_tool;
* missing_tool;
* forbidden_tool;
* wrong_tool_arguments;
* wrong_tool_order;
* repeated_tool_loop;
* error_thrashing;
* premature_stop;
* missing_clarification;
* fabricated_claim;
* grounding_failure;
* policy_violation;
* prompt_injection_failure;
* state_mutation_failure;
* latency_budget;
* cost_budget;
* execution_error;
* evaluator_uncertainty.

Allow multiple labels per failure.
FAILURE ANALYSIS / CLUSTERING
Create a page that answers:
“What is actually breaking most often?”
Start with deterministic structured features.
Then optionally provide LLM-assisted clustering/summarization.
LLM-generated clusters are descriptive only.
They do not gate deployment.
Show:

* count;
* percentage;
* severity;
* affected agent versions;
* affected categories;
* example cases;
* whether frequency increased from baseline.

Example:

```
17 wrong tool arguments
11 premature terminations
7 grounding failures
4 repeated tool loops
3 policy violations
```

Generate useful summaries such as:
“v2 improved task completion overall but introduced a new address-update argument failure in shipping-change scenarios.”
Only make statements supported by actual stored evidence.
DATABASE MODEL
Design normalized tables/entities for at least:

* agents;
* agent_versions;
* datasets;
* dataset_versions;
* eval_cases;
* runs;
* run_executions;
* samples;
* spans;
* assertion_results;
* judge_configs;
* calibration_sets;
* calibration_items;
* calibration_runs;
* human_annotations;
* comparisons;
* failure_labels;
* failure_clusters;
* CI gate decisions.

Use JSON/JSONB where flexible event metadata is appropriate.
Do not put the entire system into giant opaque JSON blobs.
Use migrations.
Seed demo data through code, not manually edited production DB dumps.
WORKER / JOB EXECUTION
Long evaluation runs must not block HTTP requests.
Implement a lightweight job architecture.
Avoid unnecessary infrastructure if PostgreSQL can provide a robust job table + worker.
A dedicated worker process may:

1. claim queued job;
2. mark running;
3. execute samples;
4. persist progress;
5. persist terminal state;
6. safely recover stale jobs.

Make job handling idempotent.
Expose progress to the frontend.
Use Server-Sent Events or polling if appropriate.
Do not introduce Redis/Celery unless there is a clear reason.
API
Build clean REST endpoints.
At minimum support data for:

* overview dashboard;
* agents;
* versions;
* datasets;
* cases;
* runs;
* run details;
* samples;
* traces;
* comparisons;
* failure analysis;
* judges;
* calibrations;
* annotations;
* CI decisions.

Mutation endpoints for running evals should be disabled or protected in public demo mode.
Generate OpenAPI docs.
Use typed response schemas.
Create a generated or strongly typed frontend API layer.
DASHBOARD — PRODUCT EXPERIENCE
This is extremely important.
A recruiter should understand the project in about 30 seconds.
Main navigation:

* Overview
* Experiments
* Compare
* Datasets
* Traces
* Failures
* Judges
* CI / Release Gates
* Methodology

OVERVIEW PAGE
Display immediately:

* current baseline;
* current candidate;
* gate status;
* total cases;
* total samples;
* task success rate;
* outcome pass rate;
* trajectory pass rate;
* tool/component pass rate;
* policy/safety pass rate;
* execution error rate;
* p50 latency;
* p95 latency;
* total tokens;
* estimated cost when valid;
* `pass^k`;
* `pass@k`.

Include:

* trend chart across agent versions;
* failure-category chart;
* recent experiment list;
* a clear “what changed?” summary.

Every percentage should show sample size or make it easily discoverable.
Confidence intervals should be visible on important pass metrics.
EXPERIMENTS PAGE
List evaluation runs with:

* name;
* agent;
* agent version;
* model;
* dataset;
* samples/case;
* status;
* pass rate;
* cost;
* p95 latency;
* timestamp;
* git commit.

Filters:

* agent;
* version;
* model;
* dataset;
* date;
* status.

COMPARE PAGE
This is one of the most important pages.
Side-by-side baseline and candidate.
Show:

* overall delta;
* confidence interval;
* regression margin;
* decision;
* common case count;
* sample count;
* validity warnings.

Metric comparison:

```
Outcome
Trajectory
Components
Policy
pass^k
pass@k
Latency
Tokens
Cost
```

Show improved/regressed/unchanged case counts.
Allow drilling into changed cases.
Include category-level deltas.
CASE COMPARISON
For a single case show:

```
Expected behavior

BASELINE
input
output
tool sequence
assertions
trace

CANDIDATE
input
output
tool sequence
assertions
trace

DIFF
changed tools
changed arguments
changed outcome
changed cost
changed latency
```

This should be visually excellent.
TRACE EXPLORER
Build a real waterfall/tree trace viewer.
Display:

* trace;
* nested spans;
* LLM calls;
* tool calls;
* duration;
* tokens;
* cost;
* status;
* attributes;
* redacted inputs/results.

Selecting a span opens details.
Provide trajectory summary:

```
lookup_customer
→ lookup_order
→ check_refund_eligibility
→ issue_refund
```

For baseline/candidate provide a trajectory diff.
Do not expose chain-of-thought.
DATASET EXPLORER
Show:

* dataset versions;
* dataset hash;
* categories;
* case count;
* case definitions;
* tags;
* fixture;
* assertions;
* rubric;
* severity.

Add visual indication when a dataset version is frozen/published.
JUDGE CALIBRATION PAGE
This should feel like a real model evaluation tool.
Show:

* judge model;
* prompt hash;
* calibration set;
* admission status;
* sample count;
* class balance;
* accuracy;
* precision/recall/F1;
* Cohen's kappa;
* FPR;
* FNR;
* confusion matrix;
* admission policy.

Clearly show:
CALIBRATED — allowed for gating
or
NOT CALIBRATED — diagnostic only
Never hide this distinction.
FAILURE PAGE
Show:

* top failure modes;
* trends;
* severity;
* agent versions;
* categories;
* example runs.

Allow clicking a failure cluster and opening representative traces.
CI / RELEASE GATE PAGE
Display:

* latest baseline;
* candidate;
* gate verdict;
* gate reasons;
* comparison validity;
* practical regression margin;
* confidence interval;
* changed case count.

Explain in simple language:
“Candidate is 2.4 points lower than baseline, but the confidence interval remains inside the allowed 5-point non-inferiority margin. No meaningful regression detected.”
Or:
“Evidence is inconclusive. More independent cases or repeated samples are required.”
METHODOLOGY / LEARNING PAGE
Because this is also a learning portfolio project, include an in-app page explaining simply:

* golden dataset;
* trace;
* span;
* trajectory;
* deterministic evaluator;
* LLM judge;
* calibration;
* Cohen's kappa;
* false positive;
* pass@k;
* pass^k;
* confidence interval;
* non-inferiority margin;
* regression gate.

Use short explanations, not academic essays.
This should help me explain the project in interviews.
VISUAL DESIGN REQUIREMENTS
Use the frontend-design capability.
Design for:

* 1440px desktop;
* normal laptops;
* tablets;
* mobile.

Responsive behavior must be intentionally designed, not merely “stack everything.”
Tables should remain usable on narrow screens.
Trace viewer should have responsive fallback.
Charts need accessible legends/tooltips.
Use skeletons while loading.
Build good:

* empty states;
* errors;
* no-results states;
* disabled states;
* tooltips;
* keyboard focus.

Meet sensible WCAG accessibility standards.
DEMO DATA STORY
Seed the application with a coherent experiment story.
Example:

```
Support Agent v1
→ baseline

Support Agent v2
→ candidate
```

v2 should improve several behaviors:

* better refund eligibility check;
* fewer redundant tool calls;
* better clarification;
* lower failure rate.

But introduce at least one realistic new regression such as:

* wrong address-update argument in a particular scenario.

This gives the dashboard something nontrivial to explain:
“v2 improved overall task success but introduced a localized regression.”
Also seed:

* a research-agent comparison;
* a coding-agent comparison;
* judge calibration history;
* a failed calibration;
* an admitted calibration;
* one invalid comparison caused by incompatible dataset versions;
* one inconclusive comparison caused by insufficient evidence;
* one prompt-injection failure;
* one execution error distinct from an assertion failure.

This will make almost every product concept explorable without external APIs.
SYNTHETIC VARIANCE
For offline demos, include a seeded stochastic/mock agent mode.
It should produce reproducible pseudo-random behavior based on:

* run seed;
* case ID;
* sample index;
* agent version.

This lets the demo show meaningful:

* repeated-run variance;
* flaky cases;
* `pass^k`;
* `pass@k`;
* confidence intervals;

while remaining exactly reproducible.
Clearly identify these as synthetic demo runs.
INSPECT AI INTEGRATION
Do not make Inspect AI the core of our platform.
But add an integration demonstrating interoperability.
At minimum either:

* run/export one of our research-agent datasets through Inspect; or
* ingest an Inspect evaluation log into our normalized run format.

Document the adapter.
The point is to show awareness of established eval tooling while keeping our own engine understandable.
CI/CD
Create GitHub Actions.
Standard CI
On PR:

* Python lint;
* Python type check;
* Python tests;
* frontend lint;
* frontend type check;
* frontend tests;
* build;
* Playwright smoke test where practical.

Eval gate workflow
Implement baseline/candidate evaluation.
Follow the stronger ideas from `agent-eval`:

* use the SAME evaluator version for baseline and candidate;
* run baseline code from target branch/worktree;
* run candidate code from PR;
* store both in one comparison database/artifact;
* validate manifests;
* run trajectory diff;
* perform statistical comparison;
* block on:
   * invalid comparison;
   * meaningful regression;
   * inconclusive result if the repository policy chooses conservative gating.

For deterministic offline demo suites, CI must require no model credentials.
For live LLM gates, support secrets if configured but don't make repository CI depend on them.
Upload:

* JSON reports;
* JUnit reports;
* comparison report;
* trace diff;
* eval DB or portable artifacts;

with reasonable retention.
Redact sensitive traces before upload.
CHANGE-MEASUREMENT RULE
If agent behavior code/prompts change, there must be new measurement evidence.
Implement a CI check similar conceptually to the reliability lab:
If files under a frozen/published agent version change improperly:
FAIL.
If agent behavior changes without an associated new eval result / approved version:
FAIL or clearly warn depending on workflow.
Prefer version bump over editing historical versions.
SECURITY
Public repository.
Public demo uses synthetic data only.
Requirements:

* no credentials committed;
* `.env*` ignored except `.env.example`;
* secret scanning considerations;
* trace redaction;
* no untrusted arbitrary shell execution from web;
* coding-agent execution disabled in public/demo mode;
* command timeouts;
* process-tree termination on timeout;
* temporary sandbox directories;
* path traversal protection;
* CORS restricted appropriately;
* mutation endpoints protected or disabled publicly;
* reasonable rate limiting on expensive/live operations;
* secure error handling;
* no stack traces exposed in production;
* dependencies reviewed.

Create `docs/SECURITY.md`.
PRIVACY / TRACE SAFETY
Trace data can contain sensitive prompts/tool outputs.
Build a redaction layer before storage/export.
Support:

* key-based redaction;
* pattern-based redaction;
* known secret replacement;
* configurable text truncation.

The demo must contain no personal data.
OBSERVABILITY OF OUR OWN PLATFORM
Add structured logs.
Include:

* request ID;
* run ID;
* job ID;
* case ID where applicable.

Log lifecycle events without leaking prompt content by default.
Implement:

* `/health`;
* `/ready`.

PERFORMANCE
Do not prematurely optimize.
But make large run/sample lists paginated.
Database indexes should support:

* run lookups;
* agent/version filtering;
* sample/run joins;
* span trace lookup;
* timestamp sorting;
* failure category filtering.

Avoid N+1 API patterns.
TESTING
This project must be heavily tested where correctness matters.
Eval-core unit tests
Test:

* every assertion;
* case parsing;
* dataset hashing;
* manifest hashing;
* pass/fail statuses;
* tool sequences;
* trace parsing;
* redaction;
* calibration metrics;
* Cohen's kappa;
* confusion matrix;
* Wilson intervals;
* paired bootstrap;
* comparison classifications;
* invalid run comparisons;
* repeated-run statistics;
* `pass^k`;
* `pass@k`;
* judge admission;
* failure classification.

Property/edge tests
Include cases for:

* empty data;
* one class only;
* identical runs;
* all pass;
* all fail;
* missing cases;
* duplicate case IDs;
* incomplete samples;
* execution errors;
* mismatched dataset hashes;
* changed judge prompt;
* deterministic seeds.

API integration tests
Use test DB.
Frontend tests
Test important rendering and state logic.
Playwright E2E
At minimum verify:

* overview loads;
* compare page works;
* trace page works;
* calibration page works;
* dataset page works;
* mobile layout does not catastrophically break.

Prefer meaningful tests over meaningless snapshots.
Target high confidence in `evalcore`; aim for >=85% coverage there without gaming coverage.
CODE QUALITY
Python:

* type hints;
* small modules;
* explicit domain models;
* docstrings for non-obvious eval/statistical logic;
* Ruff clean;
* Pyright clean.

TypeScript:

* strict;
* no uncontrolled `any`;
* sensible reusable components;
* no giant 1,500-line pages.

Do not overabstract.
Do not create “enterprise architecture” for 200 lines of code.
But do make evaluator/statistics boundaries explicit.
DOCUMENTATION
Documentation is part of the product.
Create:
`README.md`
This must be recruiter-quality.
Include:

* polished hero;
* concise explanation;
* dashboard screenshot;
* comparison screenshot;
* trace screenshot;
* calibration screenshot;
* architecture diagram;
* why agent evaluation is hard;
* core features;
* 30-second demo;
* local setup;
* zero-key demo;
* live-model setup;
* CLI examples;
* evaluation methodology summary;
* CI gate explanation;
* project structure;
* technology choices;
* known limitations;
* roadmap;
* attribution.

Do not make README a wall of text.
`docs/ARCHITECTURE.md`
Explain components and data flow.
`docs/EVAL_METHODOLOGY.md`
Explain:

* scoring layers;
* judge calibration;
* repeated runs;
* statistics;
* limitations.

Do not overclaim scientific certainty.
`docs/LEARNING_GUIDE.md`
Write this for me.
Explain the project in simple language so I can study it.
Focus only on knowledge needed to:

* understand architecture;
* explain eval concepts;
* explain why each design decision exists;
* discuss tradeoffs in interviews.

`docs/DEMO.md`
Give a recruiter/demo walkthrough.
Example:

```
1. Open Overview.
2. See current candidate vs baseline.
3. Open Compare.
4. Inspect confidence interval and regression decision.
5. Open a regressed case.
6. View trajectory diff.
7. Open Judges.
8. Show calibration.
9. Explain CI gate.
```

ADRs
Document major decisions:

* OTel;
* Postgres;
* deterministic fixture web;
* calibration requirement;
* statistical comparison;
* public demo design;
* no chain-of-thought;
* why Phoenix is optional;
* why core is framework agnostic.

README IMAGES
Do not leave placeholder image boxes.
Once the application is running with seeded data:

1. use Playwright or another reproducible browser automation method;
2. capture polished screenshots;
3. save them under `docs/images/`;
4. reference them in README.

Capture at least:

* dashboard overview;
* agent comparison;
* trace detail;
* judge calibration.

Also create an architecture diagram.
Prefer Mermaid for source maintainability.
If practical, render it to SVG/PNG for README.
If practical, make a short demo GIF/video preview, but do not compromise core quality for it.
CLAUDE.md
Create a strong project-level `CLAUDE.md`.
Include:

* project mission;
* architecture boundaries;
* commands;
* pinning rules;
* evaluation-science rules;
* test requirements;
* secrets policy;
* UI standards;
* versioning rules;
* documentation expectations;
* “do not gate on uncalibrated evaluators” rule;
* “never edit published agent versions” rule.

This file must make future Claude sessions productive immediately.
CLI EXPERIENCE
Create an excellent CLI.
Examples:

```
ars demo seed
ars dataset validate datasets/support/v1.yaml

ars eval run \
  --agent support:v1 \
  --dataset support:v1 \
  --samples 3

ars eval compare \
  --baseline RUN_ID \
  --candidate RUN_ID

ars eval diff RUN_A RUN_B

ars judge calibrate \
  --judge anthropic:MODEL \
  --set datasets/calibration/v1.yaml

ars traces distill \
  --run RUN_ID \
  --out datasets/candidates/

ars demo verify
```

Actual syntax may differ if you design something cleaner.
Provide `--help`.
Return meaningful process exit codes.
MAKEFILE / DEVELOPER EXPERIENCE
Provide easy commands such as:

```
make setup
make dev
make demo
make test
make lint
make typecheck
make verify
make screenshots
```

`make demo` should provide a populated local experience with no API key.
DOCKER
Provide:

* production-grade Dockerfiles;
* `docker-compose.yml`.

Local full stack should be startable without obscure manual steps.
Canonical stack may include:

* web;
* API;
* worker;
* Postgres;
* optional Phoenix profile.

Use health checks.
DEPLOYMENT
Provide deployment configuration.
Preferred simple public architecture:

* Next.js web;
* FastAPI API;
* worker;
* managed Postgres.

A `render.yaml` blueprint is acceptable for an all-Render deployment.
If Vercel credentials already exist and it clearly improves deployment, web may deploy to Vercel while API/worker/Postgres deploy elsewhere.
Do not ask me to create unnecessary accounts during implementation.
Detect available authenticated tooling.
If deployment credentials are available:

1. deploy;
2. run migrations;
3. seed public synthetic demo data;
4. verify health;
5. verify dashboard;
6. verify responsive pages;
7. capture final public URL.

If credentials are unavailable:

* DO NOT STOP;
* finish the application completely;
* validate Docker deployment locally;
* leave exact deployment config and instructions;
* never fabricate a live URL.

PUBLIC DEMO MODE
Implement:

```
DEMO_MODE=true
```

In demo mode:

* synthetic seeded data;
* read-only by default;
* no arbitrary shell;
* no real refunds/state changes;
* no real APIs required;
* expensive model operations disabled unless explicitly configured;
* clear “Demo data” indicator.

The public experience should still look fully functional.
DATA INTEGRITY
Migrations must be repeatable.
Seed scripts must be idempotent.
If `seed_demo.py` runs twice, it must not create duplicate garbage.
Any background job recovery logic should be idempotent.
Assume scripts will be run more than once.
ERROR HANDLING
The UI should distinguish:

* agent assertion failure;
* agent execution failure;
* judge failure;
* malformed judge output;
* model provider failure;
* timeout;
* invalid comparison;
* incomplete run;
* server failure.

Do not turn all failures into generic “something went wrong.”
PROJECT STORY FOR RECRUITERS
The application should communicate this story:
Building an agent is not enough. A final answer can look correct while the agent used the wrong tools, hallucinated arguments, violated policy, looped unnecessarily, or became less reliable after a model/prompt change. Agent Reliability Studio makes those failures measurable by combining deterministic assertions, trajectory analysis, calibrated LLM judges, repeated trials, OpenTelemetry traces, human annotation, and statistically defensible regression gates.
Everything in the UI and README should reinforce that story.
DO NOT FAKE RESULTS
This is mandatory.
Never invent impressive production metrics.
Demo fixture metrics are allowed, but label them clearly.
Do not write resume claims like:
“Improved reliability by 47%”
unless we actually ran the relevant experiment and the evidence exists.
If seeded deterministic demo data shows an improvement, describe it as:
“Synthetic demo comparison.”
FINAL SELF-REVIEW PASSES
Before declaring completion, run several internal review passes.
Evaluation-science review
Check:

* statistical correctness;
* accidental leakage;
* unjustified gating;
* judge calibration;
* manifest comparability;
* sample-size messaging;
* pass^k implementation.

Backend review
Check:

* schema;
* transaction handling;
* job reliability;
* idempotency;
* API consistency;
* security.

Frontend review
Use frontend-design/UI reviewer.
Check:

* hierarchy;
* responsive behavior;
* accessibility;
* charts;
* empty/error states;
* no generic AI aesthetics.

Security review
Check:

* secrets;
* command execution;
* path traversal;
* public demo write paths;
* trace leakage;
* environment handling.

Code simplification pass
Remove:

* dead code;
* duplicated logic;
* unnecessary abstractions;
* TODO placeholders;
* debug prints.

Do not simplify away necessary provenance/eval rigor.
DEFINITION OF DONE
Do not call this project finished until ALL applicable items below are true:

* repository initialized cleanly;
* full backend implemented;
* full frontend implemented;
* migrations exist;
* demo seed exists;
* zero-key demo works;
* support-agent demo exists;
* research-agent demo exists;
* coding-agent demo exists;
* frozen MCP web exists;
* deterministic assertions work;
* LLM judge interface works;
* calibration workflow works;
* annotation UI works;
* repeated runs work;
* `pass^k` works;
* `pass@k` works;
* bootstrap comparison works;
* invalid/inconclusive states work;
* trace persistence works;
* trace explorer works;
* trajectory diff works;
* failure taxonomy works;
* failure-analysis page works;
* CI gate works;
* red-team cases exist;
* OTel semantics are implemented;
* redaction exists;
* Docker works;
* health endpoints work;
* API docs work;
* frontend responsive;
* tests pass;
* lint passes;
* typecheck passes;
* production build passes;
* Playwright smoke tests pass;
* README screenshots are real;
* architecture diagram exists;
* README is polished;
* methodology docs exist;
* learning guide exists;
* security docs exist;
* CLAUDE.md exists;
* `.env.example` exists;
* no secrets committed;
* third-party attribution is correct;
* deployment config exists;
* deployment verified if credentials exist.

No “TODO: implement later” for anything core.
No placeholder dashboard.
No fake buttons.
No dead navigation items.
No mock charts disconnected from stored data.
WORKING STYLE
Work continuously.
You may plan internally and use a task list.
Do not ask me to approve each phase.
Use engineering judgment.
When an implementation path fails:

1. diagnose;
2. fix it;
3. continue.

When a library is incompatible:

1. investigate current docs;
2. choose the appropriate alternative;
3. document the decision;
4. continue.

Do not abandon a feature merely because the first approach failed.
Run targeted tests during implementation rather than waiting until the end.
Then run the full validation suite.
GIT
Use clean incremental commits if the repository is connected to Git.
Suggested logical commits:

* scaffold / architecture;
* eval core;
* reference agents + fixtures;
* API + worker;
* dashboard;
* statistics + calibration;
* CI;
* tests;
* docs/screenshots;
* deployment/polish.

Do not force push.
Do not rewrite unrelated history.
Never commit secrets.
If no remote exists, still create a clean git history locally.
FINAL OUTPUT TO ME
After the project is genuinely complete, give me ONE concise completion report containing:

1. What was built
2. Architecture
3. Main evaluation concepts implemented
4. Reference agents/datasets
5. Test/lint/typecheck/build results
6. Current demo metrics — clearly labeled synthetic or real
7. Deployment URL if actually deployed
8. Local demo command
9. Repository/commit information
10. Anything blocked exclusively by external credentials
11. Five things I should study first to understand the project
12. A recruiter demo script lasting about 2 minutes

Do not give me a “next phase” list for functionality that was already required by this prompt.
Implement it now from start to finish.

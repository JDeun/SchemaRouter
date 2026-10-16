# #1431 current authorized retrieval profiling — synthetic DEV

This read-only diagnostic profiles **real public SchemaRouter.retrieve_authorized()** on the current OpenAPI/MCP and native SQL/vector/graph synthetic fixture from #1429. It does not alter any production code, inference, tool invocations or policies.

## Controlled pairs and stages

- Exactly 100, 250 and 500 registered capabilities. Build fixtures *before* measuring.
- English, Korean and Japanese author-visible sample queries, synthetic viewer and editor roles, K24 vs K56.
- With current per-field data-scope projection vs with the **same route authorization rules** and no data-scope rules. This is a **diagnostic control only**, never a product route or recommendation to remove scope.
- Two sequential iterations per group (first cold-ish, second warm-ish); total **144 instrumented public-authorized calls**. Registry versions, policies and principals are not mutated.
- Python wall-time wrappers (no model or external API) collect `_scoped_analysis_registry`, planner query analysis, planner retrieval, inner candidate scoring, and final output-field projection. Nested measures are **not additive**: `planner_candidate_scoring` is inside `planner_retrieval_total`. Source code/instrumentation overhead is included in all measurements.
- Return-ID digest, exposed serialization bytes, exactly zero unauthorized mutating viewer routes and no `audit_tag` in scoped viewer results; both phase accounting and paired group counts must remain complete.
- Raw per-case times, per-cell p50/p95 and SHA-256 of fixture/runtime/scorer sources are archived, alongside peak process memory, hardware and checkout commit.

## Hypothesis (NOT already proven)

The source currently constructs a fresh `_scoped_analysis_registry` for every field-scoped call and the visible schema transform path does not use the ordinary cached candidate-index shortcut. This might explain the older 2.3–2.7s p95 vs isolated planner-only millisecond-scale paths but remains unproven until the phase receipt is inspected. Query analysis may also account for substantial cost.

## Exact commands

    python -m pip install . "pytest>=8,<10" "pytest-asyncio>=0.23"
    python -m pytest -q tests/test_research_authorized_retrieval_phase_profile.py
    python -m scripts.research_authorized_retrieval_phase_profile --sizes 100 250 500 --repeats 2 --output artifacts/authorized-phase-dev/report.json

Dedicated GitHub Actions Ubuntu 24.04 CPU (30-minute hard timeout), read-only checkout, immutable source SHA and archived full phase results. No GPU, paid API, coding agent, cron, model inference, write key, real source network access or production tool execution.

## Safety / next iteration

Do not optimize or cache before profiling. Any eventual policy-scoped cache must be bound to registry version, verified principal, role, all ABAC/data-scope bindings and field projections; must invalidate on any relevant policy/registry change, never serve a wider principal's schema to a narrower principal, and must preserve first-match deny semantics. Test viewer/editor alternation, source changes and hidden filter parameters before proposing product changes. All measurements are same-author synthetic DEV and **not** production SLO qualification or independent confirmation. #1345/#1346 and the v0.18 release HOLD remain unchanged.

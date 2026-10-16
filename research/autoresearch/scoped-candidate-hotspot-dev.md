# #1431 — nested authorized candidate hotspot study (CPU DEV)

## Previous empirical result, preserved

From 500-capability local typed DEV on actual GitHub Actions CPU:

- [#1432](https://github.com/JDeun/SchemaRouter/pull/1432) completed a 144-call profiler, showing field-scoped mean 3,314.83ms and inclusive candidate catalog ~2,582.76ms, while registry rebuild accounted for ~119.88ms. It was merged, with no product behavior change.
- [#1433](https://github.com/JDeun/SchemaRouter/pull/1433): temporary exact candidate index preserved 162/162 JSON outputs but did not improve p95 materially (500/K24 2,128.84 → 2,126.74ms), **closed unmerged**.
- [#1434](https://github.com/JDeun/SchemaRouter/pull/1434): request-local projected schema reuse preserved 162/162 JSON outputs, but 500/K24 p95 only 3,064.68 → 2,997.18ms, 500/K56 3,568.92 → 3,529.27ms, below the preregistered 20% threshold; **closed unmerged**.
- No production permission shortcut, background jobs, or research champions were adopted.

## Precise new question

The previous `_semantic_recall_catalog()` timer included authorization availability, projected schema construction and `_score_endpoint()`. Which **specific** nested calls dominate and with how many repetitions? Avoid further speculative product changes until this breakdown is in hand.

## Protocol

Use the actual public `SchemaRouter.retrieve_authorized()` from unmodified `main` on exactly 100/250/500 locally generated OpenAPI/MCP/DB/vector/graph typed endpoints. Compare identical EN/KO/JA queries at Viewer/Editor scopes, scoped-data-policy vs same route-policy-only control, K24, two sequential iterations, **72 total exact API calls**.

Monkeypatch only inside a context manager for each synchronous request and restore methods afterward. Count invocations and cumulative inclusive wall time for:

- `AuthorizationPolicy.visible` and `data_scope` (route/field decisions).
- `SchemaRouter._scoped_analysis_registry`, `_data_scope_endpoint_view`, and `_project_retrieval_data_scope`.
- `SchemaPlanner._analyze_sync`, `_retrieve_from_intent`, `_semantic_recall_catalog`, `_score_endpoint`, `_sort_candidates`.

**WARNING:** these stages are nested, so inclusive times **overlap and must never be summed together**; instrumentation changes measured wall time. Output each nested stage's invocation count and mean/p95 inclusive total by catalog size and mode, raw per-case details, source SHA, exact checkout commit, process memory, and negative cases. No inference, tool execution or remote providers.

Reject unauthorized viewer write routes and hidden `audit_tag` fields in field-scoped mode. This is synthetic same-author DEV, not an independently blinded benchmark, verified real-host claims, or service SLO.

## Read-only Actions workflow

`.github/workflows/research-scoped-candidate-hotspot-dev.yml` runs on Ubuntu-24.04 CPU with a 20-min cap and archived source-bound JSON report.

Local commands:

    python -m pip install . "pytest>=8,<10" "pytest-asyncio>=0.23"
    python -m pytest -q tests/test_research_scoped_candidate_hotspot_attribution.py
    python -m scripts.research_scoped_candidate_hotspot_attribution --sizes 100 250 500 --repeats 2 --output artifacts/scoped-candidate-hotspot/report.json

Do not merge any production optimization without a *new* exact full-result parity + meaningful p95 proof. Release #1356 HOLD; independently sourced agent/host confirmation #1346 remains pending.

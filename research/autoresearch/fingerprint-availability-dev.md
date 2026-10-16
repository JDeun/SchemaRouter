# #1431: attribute full tool fingerprint cost in availability checks

This is an offline, **read-only synthetic DEV** instrument of the actual
current public `SchemaRouter.retrieve_authorized()`, not a change to
authorization, cooldown, schemas, scoring, agent execution or release.

## Grounded precursor

The actual [#1435 Actions experiment #38846811429](https://github.com/JDeun/SchemaRouter/actions/runs/38846811429) completed 72/72 requests. At 500 local typed endpoints and field scopes (12 requests):
- Full request p95 **3064.37ms**
- Enclosing `_semantic_recall_catalog` inclusive mean **2495.28ms**
- Nested `_score_endpoint` cumulative mean **32.98ms** across 5970 calls
- Nested `_data_scope_endpoint_view` cumulative mean **40.08ms** across 11940 calls
- Sorting cumulative mean **0.57ms**

So scoring plus field projection *cannot* explain the enclosing 2.5-second time.
Source inspection: `SchemaPlanner._semantic_recall_catalog` calls the
availability callback on every candidate; `SchemaRouter._is_snapshot_access_available`
eagerly computes `_snapshot_tool_fingerprint(tool)`, and
`ToolSpec.fingerprint` serializes all endpoints in its parent tool.
A single large OpenAPI/MCP tool may thus be serialized repeatedly within
one request. This is a **hypothesis**, not a verified root cause before
the new experiment runs.

## New pre-registered study

Exactly 100/250/500 synthetic OpenAPI/MCP/DB/vector/graph endpoints;
identical EN/KO/JA queries; synthetic Viewer/Editor; active data-field
scope vs **counterfactual** same route rules without data rules; 2 runs
per cell = **72 actual current authorized API requests**.

Within single-threaded, context-managed instrumentation count and sum
inclusive per-call wall times for:
1. `ToolSpec.fingerprint` property (full contract serialization).
2. `SchemaPlanner._snapshot_tool_fingerprint` resolver.
3. `SchemaRouter._is_snapshot_access_available`.
4. `RegistryExecutor.is_access_available_for_contract`.
5. Enclosing `SchemaPlanner._semantic_recall_catalog`.

All wrappers restored at the end of each call. Nested times overlap;
never sum their totals. Preserve source SHA, workflow run, individual
measurements and role/size stratification, negative results, and peak RAM.
No real host authentication or independently blinded source used.

If the fingerprint property accounts for most enclosed 500-route time,
the next change must retain **tool-fingerprint-sensitive cooldown semantics**
and protection against stale contract versions. Do not simply skip an
active cooldown check or reuse fingerprints across different tool versions.
A possible narrowly scoped performance mitigation must be independently
reviewed with active, expired and stale-fingerprint cooldown tests plus
full current response parity.

Run:

    python -m pytest -q tests/test_research_availability_fingerprint_attribution.py
    python -m scripts.research_availability_fingerprint_attribution --sizes 100 250 500 --repeats 2 --output artifacts/fingerprint-availability-dev/report.json

GitHub Actions: 20-minute Linux CPU, read-only. No model, remote agents,
tools, network APIs, GPU or release permissions. #1346 independent provider
and agent evidence remains outstanding; v0.18 release #1356 HOLD.

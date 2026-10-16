# Current-adapter, principal and required-output-field development check

Tracking: [#1412](https://github.com/JDeun/SchemaRouter/issues/1412)

## Distinct from the old generated #430 benchmark

This is a **new manually authored local development fixture**, with 27
query variants across EN/KO/JA and nine domain/use-case scenarios,
including read-only viewer vs editor policy boundaries and unsupported
requests. These labels were written and inspected during development.
They are **NOT independent, blinded confirmation** and must not be
described as representative production task/field recall.

The fixture uses the actual **current source adapters**:
- `tool_from_openapi()` converts a small locally written **OpenAPI 3.1**
  invoice document (GET and POST). It does **not** contact a live
  invoicing vendor.
- `tool_from_mcp()` converts a small locally written **MCP tools/list**
  containing document search/tag operations. It does **not** connect
  to a real MCP server.
- Three other stores are represented by SchemaRouter's native
  **typed `ToolSpec` contracts**: relational DB orders, vector
  search and knowledge-graph neighbors/link. These are protocol-shaped
  research contracts, not live deployed providers or separate
  adapter-system end-to-end tests.

The current `SchemaRouter.retrieve_authorized()` API (not a reimplemented
authorization checker) filters visible candidates for a trusted
synthetic `PrincipalContext`. A deny-by-default reviewed
`AuthorizationPolicy` grants viewer read capabilities and editor
write operations. After retrieving, the fixed evaluator enforces
`selected IDs ⊆ principal-allowed registered IDs` and scores
manual required route IDs and names of required output fields from
the **actual returned visible typed candidate**.

Data authoring, authorization and metric claims are kept separate:

- Required-route recall: fraction of *eligible supported* queries
  retrieving manually declared registered endpoint in the Top-K.
- Required-output-field recall: fraction of manually declared
  field names visible on the matching authorized endpoint; missing
  route implies all its required fields missed.
- Unauthorized shortlist count: requires zero disallowed registered
  endpoint exposure. A policy-filtered result is **not** proof
  that execution/authentication or row-level data scopes were
  correctly enforced by an external provider.
- Unsupported nonempty shortlist count: observation of an
  uncalibrated raw retrieval; **not an unauthorized tool call**.
- Real agent Task Success, trace/schema validation and actual tool
  execution are not measured.

Everything runs offline on public GitHub Actions Ubuntu Linux CPU,
read-only, without secrets, external inference, model downloads,
live provider traffic or privileged workflow runs. Source and local
gold hashes plus all failures are recorded. V1 completion-triggered
numeric research and V2 width/weight search remain separate.

## Reproduce

```bash
python -m pip install . "pytest>=8,<10" "pytest-asyncio>=0.23"
python -m pytest -q tests/test_research_current_adapter_field_scope_dev.py
python -m scripts.research_current_adapter_field_scope_dev \
  --k 5 --output artifacts/current-adapter-field-scope-dev/report.json
```

**Next:** obtain separately authored/approved real-provider source
schema snapshots with verifiable licenses and stable revisions; expand
the per-principal cohort to actual field-level data scopes and
100/250/500 heterogeneous catalogs; protect entirely disjoint
independent agent test cases and compare FULL/SR-K/SR-PROGRESSIVE/ORACLE
end-to-end outcomes. Do not repurpose this DEV check for independent
qualification or v0.18 release. Existing #1345/#1346 HOLD stands.

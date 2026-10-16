# #1431: request-local authorized field projection reuse experiment

**No authorization bypass, global cache, released policy change or researcher-claimed quality gain.** This is a Draft product performance proposal to address the verified ~2.6s mean in current scoped candidate processing at 500 synthetic typed endpoints.

## Negative source evidence first

Earlier [#1433](https://github.com/JDeun/SchemaRouter/pull/1433) ephemeral visible-schema `_CandidateIndex` preserved **162/162 full results** but showed **no material p95 speedup** on the same exposed synthetic source (500/K24 2,128.84ms → 2,126.74ms). Do not merge the index proposal for speed.

The live code contains a different repeated operation: within one `SchemaRouter.retrieve_authorized()` request, `_scoped_analysis_registry()` applies `_data_scope_endpoint_view()` to every authorized endpoint, and `SchemaPlanner._semantic_recall_catalog()` then applies the *same* projection a second time to every endpoint. This can involve nested Pydantic deep copies. Confirm whether eliminating only those duplicate copies improves wall-clock time without modifying any scoring or identity.

## New proposal

- Build a **strictly request-local** dictionary of the projected current principal's eligible endpoint schemas while the current protected analyzer registry is built.
- Reuse the exact projected `EndpointSpec` objects inside that **same** request's scorer; never persist or share across calls, principals, sessions, host authorization policies or registry updates.
- If the registry version or policy identity changes while a call is in flight, **recompute**, never reuse stale view.
- Preserve both principal allow/deny eligibility and post-retrieval `_project_retrieval_data_scope`. Never cache a wider-principal schema into a narrower-principal view.
- **No change** to plan(), execute(), async plan/execute or any low-level endpoint availability predicate. Scope of the implementation: synchronous and asynchronous `retrieve` with field scopes only.

## Verifiable requirements

1. Full `CapabilityRetrieval.model_dump(mode="json")` equality for same-role EN/KO/JA queries, existing/hide/write/no-fit cases, K5/K24/K56, viewer/editor alternation; sync **and async**.
2. Instrument view calls to establish one projection for each permitted endpoint rather than two. Validate that no hidden output field or write endpoint leaks.
3. Validate new principal across consecutive requests, policy identity replacement and registry version churn.
4. **162 exact paired full-response baseline/optimized calls** on 100/250/500 current parsed OpenAPI/MCP/DB/vector/graph typed DEV endpoints, K24 and K56; fail before any performance claim on one differing score, field, route, fingerprint or metadata key.
5. Inspect p95 gains/losses from immutable GitHub Actions Ubuntu-24.04 CPU source SHA; require CodeQL, protected CI, existing fast-path and query-model regression tests; keep Draft if incomplete.
6. Independent real-provider/host-identity/agent confirmation remains outstanding (#1346). A source-author-visible synthetic speedup is **not** a production SLO.

Workflow: `.github/workflows/research-request-local-projection-dev.yml`, read-only, no paid models, external agents or GPU. Release #1356 remains HOLD and the research-only K56 champion remains unpromoted.

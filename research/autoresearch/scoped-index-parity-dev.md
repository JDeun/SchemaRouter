# #1431 candidate optimization: exact visible scoped index, not an access shortcut

A source-bound, **unmerged experimental product optimization** for the observed `SchemaRouter.retrieve_authorized()` scoring hotspot. Same-author OpenAPI/MCP+SQL/vector/graph fixtures and current authorization models, NOT independent real-provider or agent end-to-end evidence.

## Why: actual #1432 profiled negative latency

On [run #38843937744](https://github.com/JDeun/SchemaRouter/actions/runs/38843937744), the current 500-route field-scoped retrieval had mean 3,314.83ms (24 requests), including 2,582.76ms inside the active `_semantic_recall_catalog` versus 119.88ms in `_scoped_analysis_registry`. The same route-policy-only control had mean 282.11ms, but **disabling data scopes in production is unacceptable**. The ordinary lexical candidate index is disabled whenever a visible schema transform is supplied, so all visible schemas are repeatedly scored.

## Proposed precise behavior

After current query principal/role/ABAC route eligibility and field-data projection, build a **per-query ephemeral** `_CandidateIndex` from **only** that invocation's projected `EndpointSpec` values and eligible tool paths. Never index original hidden field names, tool entries outside the role, or cache across request/principal/registry/policy. The indexed prefilter only prunes zero-score `_score_endpoint` computations: it still returns the same total eligible candidate list, zero-score fallbacks, ordering, schema shape, fingerprints and current `retrieve_authorized()` output.

`candidate_index=False` (old exhaustive scorer) and `structural_retrieval=True` stay fully exhaustive. If the index ever misses a positive route/field score, that is a **failed implementation**, not an accepted recall/latency trade-off. No alterable learned weight or research champion is applied.

## Gates prior to merge

- The new `tests/test_scoped_candidate_exact_index.py` compares **entire** serialized `CapabilityRetrieval.model_dump(mode="json")` before and after the transformation for English, Korean, Japanese, no-fit, visible/hidden field and write requests, roles alternating and K5/24/56; it fails closed on a single score, field, metadata or order change.
- The separate read-only Ubuntu CPU workflow performs **162 exact fully authorized baseline-indexed pairs**: 100/250/500 endpoints × 27 local DEV queries × K24/K56. A full-response mismatch aborts the run before accepting timing; JSON retains per-case SHA, original/optimized elapsed times and source manifest.
- Wait for exact-head protected full CI, CodeQL, parity tests and indexed-vs-exhaustive artifacts. Do not merge on a single synthetic fast screenshot, an inconclusive sample or missing profiler provenance.
- Still require prospective independent real source/ABAC/field and fixed-agent task confirmation under #1346. Release #1356 HOLD.

This is only a source-specific mechanical indexing optimization hypothesis; the CPU speedup has not been established at PR creation.

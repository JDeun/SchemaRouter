# #1431 — fingerprint calculation only when relevant cooldown exists

## Source-verified bottleneck

[Issue #1431](https://github.com/JDeun/SchemaRouter/issues/1431) and [#1435](https://github.com/JDeun/SchemaRouter/pull/1435) proved that the actual current 500-endpoint field-scoped public API spends seconds inside `_semantic_recall_catalog`, even though actual `_score_endpoint` takes only ~33ms.

A separate [successful current-source Actions #38850119366](https://github.com/JDeun/SchemaRouter/actions/runs/38850119366), source commit `ccc40d9966115811bfa5a658050d14abdf03dce1`, artifact `fingerprint-availability-dev-38850119366` measured **72 actual current-source public authorized calls**. In 500-field-scope cells (12 calls), `_semantic_recall_catalog` inclusive mean **1972.03ms**, `_snapshot_tool_fingerprint` inclusive **1923.46ms** from 6,000 resolutions (500/request), while actual executor cooldown lookup inclusive **1.11ms**. Full `ToolSpec.fingerprint` serialization measured **2,040.30ms mean** across 6,288 accesses, some outside the semantic catalog. Nested spans overlap and are not additive. The route-policy-only control uses the existing cached per-index tool fingerprint and takes only ~0.18ms in resolver time per request. This strongly identifies **unconditional repeated serialization of a parent ToolSpec** as the source-specific CPU bottleneck, not actual role authorization, vector embedding, or ranking weights. This experiment still does not establish independent real-provider performance.

## Surgical implementation

`RegistryExecutor.is_access_available_for_contract_lazy(tool_key, endpoint, fingerprint_supplier)` now atomically checks whether any cooldown record exists for **the exact tool and endpoint** under the existing `_runtime_state_lock`. Without a relevant cooldown, the answer is **available** without serializing the entire tool. With any relevant record, call the supplier to calculate exactly the original full ToolSpec contract fingerprint and delegate to the **unchanged** `is_access_available_for_contract` under the same reentrant lock, preserving active, expired and old-schema cooldown behavior. No fingerprint is cached between requests, across principals or for a changed contract; there is no bypass of `authorization_policy.visible` or any output field/data scope. Other executor APIs remain unchanged.

`SchemaRouter._is_snapshot_access_available` passes the same original fingerprint resolver **lazily**. No changes to scoring, index semantics, planners, declared aliases, Agent tasks, filters, auth identity, or real execution.

## Required review gates

- Test healthy route with zero cooldown and fail if full schema fingerprint is computed. Test active cooldown blocks the exact fingerprint, unrelated endpoint stays available without hashing, expired cooldown becomes available, and stale old-version cooldown does **not** block new version.
- Compare the **entire exact `CapabilityRetrieval.model_dump(mode="json")`** to the unmodified eager-cooldown behavior for EN/KO/JA and no-fit/hidden/write queries at K5/24/56, Viewer/Editor, and alternating principals. Enforce deny-by-default/field projection.
- GitHub Actions **162 exact current public authorized CPU pairs** on 100/250/500 typed source DEV × 27 author-visible EN/KO/JA tests × K24/K56. Abort on any changed score, route order, field projection, or response metadata; record per-case SHA, latency, source SHA and actual Linux CPU environment.
- **Before product merge**, require all protected CI, CodeQL, Fast Path and wheel regression checks, plus at least **20% lower p95** at both 250 and 500 endpoints for each K24/K56 with no >10% regression at 100. Every cooldown safety test must pass regardless of speed. Review process/performance on simultaneous cooldown updates under the executor reentrant lock.
- Preserve the observed research negatives (#1433 temporary index, #1434 projection reuse) and immutable source evidence. Synthetic DEV result is not production SLA or independently blinded real provider/agent qualification (#1346). **v0.18.0 release #1356 HOLD**, independent external-agent validation remains pending.

No GPU, external model, paid API or remote coding agent is used.

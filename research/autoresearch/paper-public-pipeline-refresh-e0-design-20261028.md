# Public Algorithm 1 cold/refresh E0 profile — design

Date: 2026-10-28. Follow-up to #1809 / Draft #1810; separate from protected-main integration #1811 / PR #1812.

## Intent and constraints

Measure the public prepared Algorithm 1 path's **cold index construction** against the existing, source-journal-backed **incremental refresh** after an unrelated registered route changes. Do not tune or promote the router from synthetic results. Keep K=5, owner-approved Rank, unnamed G5 discovery and all source/authorization checks. No providers, real models, agent answers, publisher-authored gold, default routing change or v0.18 release.

## Approaches

1. A new benchmark/reimplemented router: rejected as duplicated routing and a divergent oracle.
2. Always repeat refresh during the existing public planning profile: rejected because it changes the earlier benchmark output/timing and costs of the frozen E0 baseline.
3. **Selected:** optional `measure_refresh=True` using the same `build_synthetic_public_case()`, public `session.refresh()` and `router.prepare_field_routing()`. The original report and CLI remain unchanged unless opted in.

## Behavior

- Exactly 500 or 5,000 original registered routes; one unrelated synthetic route is replaced with a distinct source-owned semantic field on each sample. Registry route count stays constant, and the expected 1-/2-hop route identity never changes.
- For each of 1–20 measured samples: time `session.refresh()` wall/process CPU, compare the new snapshot **and complete native dependency graph, source contracts, and graph counters** with an independently rebuilt public session on the **same** modified registry, and verify the old session fails closed after source drift using its own old-snapshot owner policy. Measure the rebuilt session's cold-build time separately. Rebuild the owner `PaperNativeRankPolicy` on the new exact source snapshot; prove a complete public `compile_understood` plan with the original oracle.
- The `incremental_refresh` report carries p50/p95/p99 wall/process CPU for refresh and cold rebuild, source-snapshot equality and old-handle rejection booleans, route-count and expected-DAG oracles, and provider/model calls fixed to zero. Small sample p95/p99 are uncalibrated.
- The opt-in adds a versioned report section; default `benchmark()` remains schema version 1 and byte-shape compatible, opt-in reports version 2.
- No accumulated back-to-back refresh without actual source edits; no hidden calls or changed host approvals. Any parity drift stops the benchmark instead of publishing a partial performance claim.

## Gate

Test with both hop depths at 500 and a 5,000/2-hop smoke; reject invalid flag types and inject an inconsistent graph refresh that preserves posting snapshot and selected CRM plan (must fail). Verify RED→GREEN, Ruff and existing public pipeline regressions. Post-merge follow-up PR, never mutate the SHA under #1812 qualification. Independent #1346/#1477 E2 and #1356 HOLD remain unchanged.

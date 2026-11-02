# Source-reviewed deterministic G5 dependency-path Rank (B1 E0)

Date: 2026-10-28. Follow-up to #1797 / Draft #1798; tracked by #1799.

## Intent

Complete the original Algorithm 1 ranking path for explicitly named G5 dependency targets. The existing G5 index already proves current authorization, visible fields, source fingerprints and typed joins for one- and two-hop candidates. Today it abstains when multiple paths are eligible or when more than K5 qualify; a direct-tool comparator cannot safely stand in for a full dependency-path comparator.

## Approaches considered

1. **Reuse the external research ranker callback.** Rejected: it is deliberately capped at 32, introduces model/backend behavior into a source proof, and is not the owner-reviewed deterministic Rank policy.
2. **Rank individual target routes and then reconstruct paths.** Rejected: independently chosen root/intermediate/target pieces could create a path whose typed bindings were never proven.
3. **Rank complete source-proven G5 candidates in-process with the existing owner policy.** Selected: the native index constructs complete candidates first; a deterministic comparator orders those immutable path receipts and returns only the top K5. The plan compiler materializes exactly one complete DAG.

## Contract

- Opt-in only through an explicit `PaperNativeRankPolicy` whose snapshot and route annotations are validated against the existing native index.
- Rank complete, current-authorized, available, data-scope-visible, source-pinned, typed one-/two-hop candidates. Do not rank raw graph vertices or provider free-text metadata.
- Path score, in order: strongest exact visible target-field/concept-alias match; then partial alias match; demote a path containing any owner-classified web route; higher owner priority on the named target; fewer visible output/binding fields across the complete path; lexicographic full route-ID tuple.
- Return one top-ranked complete DAG for a named dependency plan. Never merge bindings across alternatives. Rank is a structural heuristic, not a calibrated semantic-quality claim.
- Preserve K5 result receipts, no execution authority, no provider invocation, source fingerprints, and explicit host-owned root arguments.
- Without an explicit policy, preserve historical G5 behavior, including `over_k_unranked` and `ambiguous_paths`.
- Bound owner-ranked path expansion at 5,000 fully qualified paths. Above the bound, fail closed with no path names or partial count. Preserve the existing 32-path limit for the separate research callback and default unranked path.
- Revalidate the entire qualified candidate set after availability/scope callbacks, then re-attest the policy and source before exposing the ranked candidates. A mutated policy, stale snapshot, source drift, changed join, authorization revocation, or unavailable/hidden route must fail closed with generic diagnostics.
- Domain filters remain unchanged for explicitly named tools; they must not override the existing named-target semantics.

## Non-goals

No new index or graph store, no provider-specific adapters, no model-based ranking, no execution grant, no default-path promotion, no E2-quality claim, and no release approval. Independent publisher-authored gold, paired external-agent E2, full CI and #1356 remain separate gates.

## Verification

RED→GREEN tests cover one-/two-hop path ranking, exact/partial match precedence, web demotion, target priority, minimal visible fields, stable path ties, named overrides, no-policy compatibility, policy/source/availability mutation, hidden/denied routes, and 500/5,000-path fixtures. E0 benchmarking reports candidate count, wall/CPU p50/p95/p99 and serialized plan size against a deterministic fixture oracle; it must not claim E2 quality or a speedup absent paired measurements.

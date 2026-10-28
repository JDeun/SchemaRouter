# B1 full-catalog acceptance matrix (implementation gate)

Parent: #1560. This is a scoped engineering checklist, **not** evidence of E2 success or release eligibility.

## Reuse existing implementation

- Public entry point: `SchemaFieldRoutingSession.prepare/discover/compile_understood/acompile_query/refresh`.
- Native posting/graph snapshots: `NativeSchemaPostingIndex`, `NativeSchemaGraphIndex`.
- Keep source-scoped authorization and DataScope checks live at lookup; no new registry or executor.
- Preserve exact-K=5, opt-in research API and #1356 release HARD HOLD.

## Acceptance tests to implement before performance tuning

1. Construct pinned mixed native catalog with OpenAPI, MCP, OPTIMADE, custom routes, ≥500 and ≥5000 total routes. Verify route count, snapshot fingerprint, source type and license witness.
2. Build a **test-only** exhaustive authorized oracle by scanning source routes under the same principal, policy, availability and DataScope. Never invoke this oracle on product lookup.
3. Compare indexed and oracle-eligible *sets* before Top-K ranking; compare emitted field groups, typed 1-/2-hop producer/consumer links and source evidence after ranking. Do not mistake Top-K truncation for an index false negative.
4. Exercise schema update/removal, role changes, hidden identifier/output, availability flips, source-review revision and stale-session rejection; assert no denied field/route labels appear in receipts or errors.
5. Exercise EN/KO/JA Unicode, malformed annotations, ambiguous concepts and unsupported/OOD requests. Keep owner-authored aliases separate from fabricated translations.
6. Emit reproducible Linux Python 3.12 E0 wall/CPU p50/p95/p99, process peak RSS and serialized schema bytes. Record run count, seed, snapshot and tool versions. No invented thresholds or E2 claims.
7. Run full CI and CodeQL on exact PR head; require a distinct merge eligibility review. Keep external gold #1346 and paired agent #1477 blocked until actual independent sources are available.

## Work sequencing

Implement one coherent test/benchmark PR first, then fix only reproducible failures in existing index code. No ranking optimization or product-default promotion in this PR.

## Implemented on #1816 branch (2026-10-28; unverified exact-head CI)

- Added a test-only exhaustive **registered source-schema** reverse-map oracle for both 500 and 5000 route mixed-scope synthetic fixtures. The oracle walks `registry.tools()` and endpoint output fields, not `index.postings`, then compares route→semantic sets, route ordering, snapshot-bound cursor anchors, and route counts. It shares the production scalar-field eligibility predicate, so this is **not** an independently implemented authorization/typed-matching oracle.
- Added a 500-route test of actual public principal-scoped `inspect_visible_fields` pagination through the existing benchmark helper, checking cursor progression, snapshot identity, page bounds, serialized payload size and latency accounting.
- Added Linux process-lifetime peak RSS before/after measurements to `scripts/benchmark_native_review_pagination_b1.py`; the probe returns null on non-Linux CI and does not imply isolated allocation cost. Existing wall/CPU page p50/p95/p99 and serialized page bytes remain.
- These changes are committed to the draft branch. **No local pytest or GitHub exact-head CI pass is claimed**: the execution container cannot resolve github.com; require protected CI+CodeQL and separate merge eligibility review.

### Still required

- Independent exhaustive **authorized** candidate oracle, including source type/license, read-only, typed field matching, principal/DataScope and availability, compared **before** K5.
- Typed one-/two-hop producer-consumer witness parity, live role/scope and availability flips, stale sessions, multilingual/OOD and malformed annotation scenarios.
- Repeated Linux Python 3.12 benchmark runs (both 500 and 5000), explicit seeds, reproducibility and report artifact; one-run process peak is not a distribution.
- Publisher E2 #1346, paired agent #1477 and release #1356 remain hard holds.


## Additional direct candidate authorization coverage (2026-10-28)

- Added a source-registry exhaustive direct-candidate oracle at both 500 and 5000 mixed-scope routes, explicitly not constructed from posting lists. The test checks `qualified_count` before Top-K, K5 abstention for overfull sets, and exact candidate route IDs when at most five are eligible.
- Recomputes expected eligibility after an availability predicate changes, without rebuilding the pinned index.
- Separate test revokes the authorization policy in place and asserts no candidate is returned, then unregisters a tool and asserts stale-index fail-closed and new snapshot rotation.
- This is **not yet** a fully independent typed matching implementation: the oracle intentionally shares `_complete_fields` with production; the test cannot detect a defect shared by that comparator and the index. Typed graph hop parity and multi-principal source-scoped review receipts remain pending.
- GitHub exact-head CI/CodeQL results must be observed before merging; no independent E2 evidence or release approval.

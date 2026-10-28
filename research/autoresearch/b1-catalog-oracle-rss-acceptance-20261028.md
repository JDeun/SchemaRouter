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

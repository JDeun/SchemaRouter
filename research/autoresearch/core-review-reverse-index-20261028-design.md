# B1 Versioned Reverse Field Index for Principal-Safe Owner Review

Issue #1795; parent #1560; stacked on Draft #1794.

## Why

The canonical native posting index is already built once per original source
snapshot and supports authorized P1 field intersections. But the public
review-first `inspect_visible_fields()` interface rebuilds a route→semantic
inverse from every posting and sorts every route on **every page**. It also
linearly hashes every route to resolve a fixed-size cursor. With 5,000 native
routes and many pages, this repeated global work is an avoidable missing
catalog-index connection. It is not a provider adapter or ranker task.

## Approaches

1. Keep per-page inversion and sorting. Simple but defeats the prepared
   catalog's reuse and scales review paging with total corpus size.
2. **Selected:** Materialize a bounded-by-source-size reverse route index and
   sorted route sequence at full native build and verified delta refresh;
   derive fixed `sr1:` cursor anchors once from the same original snapshot
   digest. Pages do a binary search or opaque hash lookup, then live per-route
   checks. This retains exact source and authorization boundaries.
3. Introduce a separate SQLite/graph DB for review pages. Rejected: adds a
   second schema catalog whose synchronization and authority are hard to prove.

## Source-pinned internal structures

Add to immutable `NativeSchemaPostingIndex`:

- `route_semantic_ids: Mapping[str, frozenset[str]]`: all eligible original
  scalar semantic postings in reverse direction, not principal visibility.
- `review_route_ids: tuple[str, ...]`: lexically sorted registered routes
  with at least one indexed field semantic.
- `review_cursor_anchors: Mapping[str, str]`: fixed-size source-snapshot
  cursor `sr1:sha256(snapshot_id + ':' + route_id)` → exact original route.

Full build computes these from the already visited source fields. The
existing full/delta posting assembler updates the route inverse together
with changed original tools, uses the original snapshot hash calculation
unmodified, and regenerates opaque anchors only when a new source version is
published. The new maps are read-only and authorization-neutral. Never
publish them to consumers; the trusted host holds the prepared session.

`inspect_visible_fields` uses the sorted route sequence and `bisect_right`
to seek a plain route anchor, or indexed `review_cursor_anchors` for a
snapshot-bound opaque anchor. It iterates from that position without
copying the full tail. All emitted routes are still projected from the
ORIGINAL endpoint and checked for current principal authorization,
availability, DataScopeRule, source fingerprint, typed inputs and page bytes.
The indexed cursor map is deliberately authorization-neutral and its
`sr1:sha256(snapshot_id + ':' + route_id)` hashes can be guessed. Hence an
opaque cursor anchor itself must pass current-principal visibility before
its existence may be acknowledged: rejected/unknown/revoked anchors return
the same generic cursor error. This avoids an unauthorized route-ID
existence oracle without changing the established cursor encoding.
The existing two reattestation passes stay intact. Cursors are not
permissions and do not promise consistent policy across separate pages.

## Validation, cost and non-goals

- Preserve the current `sr1:` cursor ABI, including long/Unicode/odd native
  identifiers and legacy plain name anchors; never echo hidden field labels.
- Invalid, wrong-snapshot or invented cursors fail closed without a registry
  full scan. Reverse maps must be equivalent to forward postings and
  independent clean rebuild after original in-memory and SQLite deltas.
- Guessed private `sr1:` hashes, cursors used by another principal, and
  revoked/temporarily unavailable anchors must fail with an indistinguishable
  error, including when the underlying original route still exists.
- Tests forbid `postings.items()`, `registry.tools()/keys()`, provider
  executor and global sorting during **page requests**, but permit those
  operations during an initial source build or verified refresh.
- Added memory is O(indexed routes + semantic postings), computed only on
  build/delta, trading storage for request latency. Benchmark 500/5000
  registered routes with p50/p95/p99 page CPU and serialized receipt bytes;
  no unmeasured speedup claim.
- No automatic semantic concept inference, ranking beyond 32 qualified
  research candidates, source/provider data, external model, E2 proof or
  default behavior promotion. #1346/#1477 and #1356 HOLD unchanged.

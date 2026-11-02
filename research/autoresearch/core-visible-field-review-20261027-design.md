# B1 principal-scoped field review inventory — design (2026-10-27)

## Missing core wiring

Prepared field routing originally required a host-reviewed `NativeConceptCatalog`
before any fields could be inspected, creating a bootstrap cycle for new owners.
The existing `build_capability_explorer_document` and schema Explorer show
complete registered operator-side schemas, including raw annotations, but
are **not** a principal-scoped field inventory for a consumer/host review UI.
The private native posting index indexes semantic IDs without a principal
and must **not** be returned directly. This is about safe review of fields
the current principal may see, not provider queries or invented meanings.

## Alternatives

1. Expose raw posting IDs: fast, but leaks hidden source entries and omits
   runtime policy, availability, typed metadata, source fingerprints.
2. Reuse the complete operator-side Explorer or rebuild a scoped analyzer
   registry per review page: returns excessive raw schema annotations and/or
   rescans the entire source rather than the pinned indexed semantic fields.
3. **Selected:** add opt-in `SchemaFieldRoutingSession.inspect_visible_fields`
   using the current pinned posting manifest plus original current-source
   policy, visibility, fingerprint and availability checks. No new index,
   registry adapter or execution layer. Permit `prepare_field_routing()` with
   no catalog **for review only**; reuse that index when explicit owner approval
   arrives through `revise_catalog(catalog=...)`.

## Interface and data boundary

`session.inspect_visible_fields(*, principal, after_route=None, limit=32)`
returns a bounded page of `SchemaFieldReviewRoute` (route name, safe optional
source type/license, and `SchemaFieldReviewField` scalar name/semantic
ID/JSON type/unit) and `next_after_route`. Stable, lexicographically ordered
route IDs define the page order. The returned opaque `sr1:<sha256>` cursor
hashes the source snapshot and route name: callers never need to round-trip
an unsafe native route string, regardless of length or control characters.
It is only a source-specific continuation anchor, not authority.
The page includes the pinned source `snapshot_id` for source identity only.

The `catalog=None` prepared state contains no owner concept authority.
`discover`, `compile`, `compile_understood`, `acompile_query` and the catalog
revision ID reject that state; `refresh` preserves it across schema updates.
`revise_catalog` creates a new route-enabled handle, preserving the reviewed
session as non-routing and reusing the exact pinned native posting/graph index.

- Only registered **read-only, non-destructive, source-typed** routes with
  already indexed scalar `semantic_id` fields are considered.
- Each emitted route must pass the **current principal** route authorization,
  per-field scope and availability; excluded/private routes, identifiers,
  raw schema descriptions and global candidate counts are never reported.
- In a restricted field-scope view, original tool-level provenance strings
  may echo denied field names. Suppress `source_type` and `license` in that
  case; similarly omit a route if its identifier echoes a denied field name or
  alias. The host must seek source-owner review separately before constructing
  an explicit concept declaration. Full-scope views may include provenance.
- Validation caps pages at 1–64 entries; no arbitrary query, alias inference,
  auto-approval, ranking, graph execution or provider data calls.
- Also cap emitted scalar metadata at 512 fields per route, 2,048 fields per
  page, and a conservative 256 KiB page byte budget. Fail closed on oversized
  responses rather than silently truncating fields; unusually wide schemas
  need explicit owner-side splitting or future field-level pagination.
- Pass callbacks detached source copies, normalize even callback-raised policy
  errors, and reload source fingerprints after callback effects. Recheck
  selected route eligibility twice (including scoped names/metadata) after
  scanning, and source/policy/principal witnesses before returning. This
  catches ordinary mid-scan drift, not all possible stateful callback races.
- Field inventory can change with live policy/availability between pages:
  callers must restart the review after such changes, not treat cursor
  position as persistent permission or use inventory to authorize execution.
  Arbitrary mutable availability state has no atomic revision witness in the
  current callback contract; the host owns synchronization/versioning if
  it needs stronger semantics. Public source-scoped pages are never a grant.
- The prepared session itself is **trusted host-side**, since its pre-existing
  `indexed_route_count`/`snapshot_id` expose aggregate original index facts;
  only current principal-scoped page receipts cross a consumer trust boundary.

## Acceptance

At 500+ registered native endpoints, principal-visible review paginates
deterministically without `registry.tools()/keys()` or provider executors.
Separate principals see no inaccessible route or field names. Data-scope
restricted provenance is suppressed. Invalid page inputs, source and policy
churn, hidden/health-invalid routes, callback mutation, sensitive callback
errors, oversized source metadata, and malformed continuation fail closed.
The host may use reviewed output to **author** a catalog; no concept is
auto-generated, and existing catalog-backed `discover/compile` behavior is
unchanged. New hosts can complete the bootstrap without a synthetic catalog.

# B1 owner-reviewed catalog replacement without source reindex (2026-10-27)

## Intent and constraints

SchemaRouter selects verified fields from a registered native schema graph;
it never fetches provider records. The host owns the bounded
`NativeConceptCatalog` alias-to-typed-field declarations. Presently, changing
only those reviewed meanings forces `prepare_field_routing` to rescan all
registered source tools even though the immutable posting and G5 graph index
are already current. The registry-journal `refresh()` instead requires a
newer native source version, so it cannot solve a concept-only update.

## Approaches

1. Call `prepare_field_routing` for every owner-catalog revision: correct but
   forces a full rebuild across unchanged native schemas.
2. **Selected:** `SchemaFieldRoutingSession.revise_catalog(catalog=...)`
   returns a distinct session with a separately revalidated/detached reviewed
   catalog and **the same exact source-pinned original posting/G5 index**.
   Expose a stable opaque `catalog_revision_id` content digest for host cache
   keys alongside existing *source-only* `snapshot_id`.
3. Mutate the catalog inside an existing session or implicitly accept mutable
   caller objects: breaks snapshot safety and source-authority semantics.

## Invariants and honest lifecycle boundary

- Source registry object/version are checked before and after catalog copy,
  without a full-tool manifest rescan. The existing indexed query path checks
  the fingerprints of all *selected* routes before returning proof. Custom
  registries must honor their version contract; an in-place mutation without
  a revision cannot be globally discovered by this constant-cost operation.
- A live source authorization policy must remain identity/content-stable during
  revision. A missing policy or malformed/ambiguous catalog is refused.
- Only owner-supplied, bounded, validated concepts can change the query alias
  mapping. No model guesses, raw provider calls, remote queries or execution.
- The new session inherits the same host-approved roots and graph; `refresh()`
  continues to handle *native* schema changes separately.
- The old session remains a valid snapshot **until the host retires that
  handle**. There is no globally managed owner-review revision source yet;
  this API does not claim automatic cross-session revocation. Applications
  must atomically replace their current session reference on review changes.
- `snapshot_id` is intentionally the immutable native *source* digest. The
  separate `catalog_revision_id` uses canonical JSON hashing of the validated
  owner semantics, without dependence on nested dictionary insertion order.
  Together these IDs distinguish schema + owner-semantic revisions **only**;
  they are not sufficient cache keys for authorized field discovery or plans.
  Such receipts depend on live principal identity, policy, scope and source
  availability, and must be reauthorized before any reuse.

## Acceptance

500-route EN/KO/JA reviewed alias replacement uses current original source
without any `registry.tools()` scan, posting/graph rebuild or provider
executor. Source snapshot stays the same, catalog revision identity differs,
and the old handle's original mapping stays detached. Reject malformed
catalog, source/policy churn during revision and stale native index. No change
to default retrieval, agent execution, fixed K5 or release qualification.

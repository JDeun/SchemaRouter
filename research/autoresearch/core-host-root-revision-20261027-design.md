# B1 Review-First Host Root Approval — Core Design

Issue: #1793. Parent: #1560. Stack: Draft #1792.

## Intent and boundary

After inspecting authorized native fields and input parameters, a host needs
to approve or revoke *explicit* parameterized source roots together with its
owner-reviewed concept catalog. Today `revise_catalog` can revise concepts but
retains the prepared graph's original `approved_host_roots`. For a review-only
session, that set is usually empty. The owner cannot activate a reviewed P2
root without discarding the prepared graph and rebuilding the full source.

This is source-schema-only core wiring. It does not infer concepts or input
values, execute providers, grant authorization, run a ranker or declare E2.

## Approaches

1. Re-run `prepare_field_routing(catalog=..., approved_host_roots=...)`.
   Correct but forces global index/graph construction for an owner-only review.
2. **Selected:** Reproject only the original native tools owning changed host
   roots; feed the resulting contracts through the existing canonical
   `update_capability_dependency_graph` engine. Reuse identical posting index,
   source snapshot, live policy checks and old immutable handle. This keeps
   root-only review incremental without a parallel graph implementation.
3. Mutate host-root flags on the old graph. Rejected: silently changes the
   trusted meaning of an already-issued proof and leaves stale edges.

## Public contract

`SchemaFieldRoutingSession.revise_catalog(*, catalog: NativeConceptCatalog,
approved_host_roots: frozenset[str] | None = None)` returns a new immutable
session. `None` preserves prior approvals and the exact existing graph object.
An explicit bounded `frozenset()` revokes all roots; an explicit nonempty set
replaces the complete owner-approved root list. The new catalog and new root
graph appear together only after all checks succeed. Existing caller-owned
objects are strictly validated and detached.

`NativeSchemaGraphIndex.revise_host_roots(*, approved_host_roots:
frozenset[str])` verifies the current source version, the prior contract/node
set, and each affected original tool/endpoint fingerprint before reprojecting
the symmetric-difference tool keys. It checks the requested host roots were
actually accepted under existing strict `_source_native_graph_contracts` rules.
It never calls `registry.tools()/keys()` and never invokes a provider.

`catalog_revision_id` remains the original canonical concept digest when the
host root set is empty, preserving the existing no-host-root cache identity.
For a nonempty root set it hashes the canonical concept declarations *plus*
the sorted approved route IDs. The source-only `snapshot_id` does not change.
Neither digest is sufficient to cache principal- or availability-dependent
proofs without live reauthorization.

## Safety and acceptance

- Root IDs must be exact strings in a `frozenset`, at most 64; no implicit
  source review, arbitrary `set` coercion, guessed semantic ID or default.
- A route missing from the pinned source or failing read-only, typed-input,
  provenance or output validation is rejected. Callback, source and policy
  errors never leak private schema text as public diagnostics.
- The new graph is compared with an independently rebuilt graph for 500 and
  5,000 registered native routes. Old handles preserve their prior roots.
- On a single-field concept: without approval P1 requires the native ID
  producer; after explicit approval it accepts a direct parameterized P2
  `requires_arguments` receipt, and only a separately host-supplied exact
  scalar can yield `ready`. Revocation restores the dependency path.
- Test no full registry scan, no executor/model/data I/O, stale-source and
  in-flight policy rejection, forged route/schema and invalid root sets.

Research A6/A7/A8 and independent #1346/#1477 qualification remain open;
release #1356 remains HARD HOLD.

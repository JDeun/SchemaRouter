# #1771 — provider-agnostic Algorithm 1 field discovery wiring

## Product boundary

SchemaRouter identifies authorized registered routes, required **schema fields**,
their dependency bindings, and declared source/unit/license metadata. It does
not retrieve provider records, synthesize answers, or manage user-specific
provider backends. The existing opt-in P1 field proof and P2 typed plan remain
the source of truth. Existing `retrieve_authorized()` defaults do not change.

## Design

- `SchemaRouter.prepare_field_routing(catalog=..., approved_host_roots=...)`
  builds one original registry posting index and typed graph index. It returns
  a `SchemaFieldRoutingSession` tied to that exact registry revision.
- `session.discover(query, principal=...)` delegates to the proven P1
  `retrieve_paper_field_coverage`, exposing full or abstaining field-only
  alternatives with original dependency bindings. Missing/ambiguous aliases
  raise `ValueError` before matching; valid, declared queries with no
  qualifying source yield a non-executable `no_proven_hit` receipt.
- `session.compile(query, principal=..., alternative_index=...,
  host_source_arguments=...)` delegates to P2
  `compile_paper_typed_tool_plan` for one chosen alternative. Its immutable
  receipt includes source-owned metadata, but never grants execution.
- Copy the host-reviewed concept catalog into the prepared session. The
  caller's later mutation must not change an already prepared session.
- Only the explicitly prepared session opts into the existing source-pinned
  indexed-direct lookup, removing repeated full-catalog scoped planner scans.
  Standalone P1/P2 and default router retrieval preserve legacy semantics.
- Reject wrong argument types and invalid root approvals. Source changes
  require preparing a fresh session; stale index / changed source policy
  must fail closed using existing P1/P2 guards.

## Test-driven implementation

1. RED: 500-route EN/KO/JA shared-root field union; preparation once and
   reuse; compile returns selected fields, typed input dependencies,
   source/field metadata; no invoker calls.
2. RED: stale registry, denied scoped fields, mutated caller catalog,
   invalid declarations, K5 invariant, no per-request full-catalog scan,
   500/5000 parity and unchanged default retrieval.
3. GREEN: add narrow prepared session facade; reuse existing P1/P2 code
   without reimplementing matching, indexing, or execution.
4. Verify targeted and broad suites, static checks; publish a Draft stacked
   PR based on #1770. Keep release default and HOLD gate untouched.

## Out of scope

Data-source-specific response adapters, automatic model-produced concept
catalogs, live API/MCP calls, answer generation, inferred joins, quality
calibration, and any automatic release/default promotion.

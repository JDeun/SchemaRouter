# Algorithm 1 named-tool typed dependency paths — E0 design

**2026-10-25 · Decision:** Continue #1560 and stacked Draft #1755. The user
already opted into native sequential development without routine approvals.

## Intent and limits

The paper's model-proposed `named_tools` can identify a required **consumer**
whose fields are source-attested but whose required arguments come from one or
two earlier source-typed tools. The current `compile_paper_understood_direct_plan`
handles only one endpoint, so a valid named dependent consumer is refused.
Provide an **explicit opt-in graph-plan** API to recognize a complete typed
one-/two-hop path and return existing non-executable `PaperTypedToolPlan`
receipts and `PaperPlanBinding`s. Its final required concept union comes from
the same owner-reviewed intent registry/catalog contract as direct plans.

No model-proposed scalar becomes a call argument; no tool is executed, no
external agent loop is added, and a result is neither calibrated no-fit nor
source-independent answer quality. Preserve default direct semantics and the
existing fixed5 direct selector. Scope to an exact *named target*; unnamed
understandings retain their existing direct behavior.

## Approach

1. Duplicate a new graph and field matcher: rejected; would drift from the
   existing G5 typed graph and the published direct field proof.
2. Filter returned K paths after lookup: rejected; an explicitly named sixth
   target would be invisible and a broad >K search could reject a valid route.
3. **Selected:** extract the source-owned semantic demand builder already used
   by direct planning; add an optional exact route **target prefilter** to the
   existing G5 one-/two-hop lookups; compile returned verified path receipts
   via the existing `_compile_one_route` and `_check_current_call_scopes`.

## Contract and safeguards

- New `compile_paper_understood_graph_plan(router, understanding, *, principal,
  catalog, intent_registry, index, k=5, max_hops=2)`. Only `max_hops` 1 or 2;
  no unnamed graph discovery. Try direct first to preserve already-valid named
  zero-hop results, then one hop, then two hops, never upgrading an over-K
  ambiguity to a weaker arbitrary result. A source-proven path cannot be
  composed from several partially selected candidates.
- Exact target route IDs are structurally derived from the indexed source
  `route_locations` for model-requested *tool keys*. The filter grants no
  authority; original graph methods apply principal scope, license, source
  fingerprint, availability, read-only, field completeness and typed joining
  before returning candidates. Unknown, hidden and denied names share the
  generic `no_proven_hit` public state.
- One returned path contains root + consumer; two-hop contains root + middle
  + final target, with all exact typed field names and input bindings from
  the original proof. The public `K=5` bounds **all exposed route IDs** across
  alternatives, not only targets; >K is an empty `over_k_unranked` plan.
- Every plan remains `requires_observation` when dependencies exist, even
  when all root source input arguments would otherwise be present. No inferred
  provider values or execution authority. No implicit selector promotion:
  the existing direct fixed5 selector deliberately rejects bound plans.
- Re-query the SAME source-qualified graph, re-materialize exact typed calls,
  recheck current authorization/policy, principal, owner declarations, index,
  input data scope and availability before returning any receipt. A changed
  callback state raises a generic `PolicyViolationError` with no hidden names.
- Research-only, default-off. Do not alter fixed #432, release #1356, or
  external-gated #1346/#1477; no production/empirical E2 claim.

## Behavioral proof

RED→GREEN tests: a named sixth target survives pre-K among six; a legitimate
one-hop returns root/target with source-typed binding; a two-hop returns
root/middle/target with two bindings; absent/denied/hidden/wrong-type/unlicensed
targets never return a call; duplicate/shared-root >K abstains; downstream
provider/host mutations abort; no model parameter hints become call data.
Existing G5 two-hop, typed P2, direct understanding, fixed5 and agent E0
regressions must remain green. Whole-suite hangs must be reported explicitly.

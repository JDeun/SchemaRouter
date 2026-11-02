# Algorithm 1 G5 owner-ranked cross-depth candidate selection — E0

Date: 2026-10-28. Issue #1805; Draft PR #1806 stacked on Draft #1804.

## Verified gap

The paper-specific plan compiler used `lookup(1)` and only tried
`lookup_two_hop(2)` when depth one returned `no_proven_hit`. This rule was
appropriate for an unranked, fail-closed historical fallback but incorrect
for explicit owner-reviewed Rank: a lower-quality valid one-hop plan could
mask an owner-preferred two-hop plan. Direct complete `ready` tool calls
retain existing precedence.

## Chosen design

Retain canonical source-pinned `NativeSchemaGraphIndex.lookup` and
`lookup_two_hop`, including existing ACL/data-scope/type/snapshot/health
source evidence and typed binding checks. No duplicate graph engine, no
model-based rank or new source authority.

When **both** `rank_policy` is explicit and `max_hops=2`:
- Independently obtain the fully qualified per-depth native K5 receipts.
  The global K5 is contained in the union of these two local K5 sets:
  any route outside its depth's K5 is dominated by at least K5 routes in
  that same depth, so it cannot enter the cross-depth K5.
- If a depth exceeds its hard 5,000-path bound, refuse with an empty
  `budget_unsatisfied` receipt; also refuse if the **sum of all qualified
  paths across depths** exceeds 5,000. Do not disclose private counts,
  actual route IDs or partial matches on refusal.
- Use the same exact visible-field/concept alias priority, web-source
  demotion, owner route priority and principal-visible full field breadth
  for complete DAGs. At a tie only, prefer fewer route hops before stable
  complete route-ID ordering.
- Select one verified original DAG; never intermix root/intermediate/
  target nodes or typed parameter bindings across alternatives.
- Materialize the chosen DAG with the original public plan compiler, and
  re-run **both** depth lookups after callbacks to ensure that the
  originally authorized candidate sets, counts and ranked receipts have
  not changed. Keep selected DAG projection/scope/materialization
  revalidation and policy fingerprint checks.
- The existing explicit named-target constraint is unchanged, as are
  direct-ready precedence and original `executable_authority=False`.
  Without a Rank policy or with `max_hops=1`, the legacy first-depth
  behavior remains untouched.

No new execution grants are created. The existing A9 executor from #1804
independently recompiles the same Rank and selected DAG before and after
each observed single-attempt tool invocation; the existing scoped finalizer
only sees the final authorized output projection.

## TDD / verification

- RED in [Original Paper Typed ToolCall Plan E0, run 40615204467]:
  103 earlier graph tests passed and 2 new cross-depth tests failed because
  a valid one-hop plan masked a better owner-priority two-hop plan.
- Added deterministic two-depth comparator unit tests for target priority,
  source-web demotion, depth ties, 500/5,000 synthetic already-qualified
  path oracle and 5,001 budget refusal.
- Added original G5 mixed-source fixture tests for named and unnamed
  selection, unchanged no-policy and max_hops=1 behavior, owner policy
  scope, combined budget and availability withdrawal after the second
  depth probe.
- Added public prepared-session and registered A9 observed execution
  tests, including owner mutation after the first actual executor call.

**Not claimed:** real mixed-provider E2 semantic-quality accuracy,
independent publisher-authored gold, calibrated performance SLA, default
promotion or release approval. The E0 comparator measurements are source-
synthetic. #1346/#1477 evidence and #1356 release HARD HOLD remain open.

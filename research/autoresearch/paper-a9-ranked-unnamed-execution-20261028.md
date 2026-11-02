# Algorithm 1 A9 observed execution for ranked/unnamed G5 DAGs (E0)

Date: 2026-10-28 | Issue #1803 | Draft PR #1804, stacked on #1802.

## Existing capability before this change

Draft #1800 added host-reviewed deterministic Rank of complete source-pinned
native one-/two-hop dependency DAGs. Draft #1802 added host-only
`allow_unnamed_graph_discovery` to the public prepared and model query planning
APIs. A plan could then select a DAG without a model-selected tool name.

The actual opt-in A9 observed executor `observe_and_execute_paper_understood_graph`
still recompiled the plan without `rank_policy` or the unnamed discovery flag.
A ranked, no-name DAG was thus only a non-executable planning receipt, and the
existing scoped observed episode and tool-free finalizer were disconnected.

## Implementation

- Explicit, host-owned, default-False `allow_unnamed_graph_discovery` and a
  `PaperNativeRankPolicy` parameter on the existing A9 observed executor.
  The opt-in flag requires the owner-reviewed policy before provider I/O.
- Recompile the **same complete typed G5 DAG** using that immutable-by-receipt
  owner declaration before execution, after each observation and before every
  subsequent tool call. Fail closed when policy bytes, principal, intent,
  catalog, host inputs, source fingerprints, health/ACL/data scope or selected
  route change. No user-constructible plan gains authorization.
- Preserve original scalar typed observation checking,
  one-attempt/one-tool-call budget per hop, exactly one complete DAG and no
  partial receipt on failure.
- Route opt-in approval through the scoped research A9 model episode only
  after host preflight; the selected whole DAG must be included in the
  **precaptured** authorized view, not merely the current router ACL.
- Carry the same host authority through the A9 tool-free finalizer, with
  additional owner-policy mutation checks before and after answer generation.
  The answer model sees the final target's original projected scalar data only;
  it has no tools, cannot trigger extra provider operations and does not
  receive upstream IDs/joins.

## Verification and limits

- Regression tests: unnamed 1-hop and 2-hop observed execution, five named
  alternatives with owner Rank, missing policy, mutation after first hop,
  midflight authorization revocation, captured-scope episode, finalizer
  projection and mutated policy during finalizer.
- Dedicated original-paper E0 workflow on commit
  `46ee462049242337d395a61bf24c44e34a6852f4`: SUCCESS.
  Major grouped suites: 143, 48, 12, 12, 100, 20 and 110 passed.
  These counts overlap across workflow steps and must not be summed to claim
  independently unique tests.
- Full GitHub CI, independent external provider/agent E2, benchmark quality
  and default promotion remain separately gated.
- This is an explicit registered executor entrypoint. A schema-only
  `PaperTypedToolPlan` still never grants executable authority.
- #1346/#1477 remain external evidence gaps, #1356 release HARD HOLD.

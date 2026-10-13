# Selective retrieval and no-match policy (prospective, unscored)

SchemaRouter's ordinary `retrieve()` returns the best ranked capabilities, even
when a user requests something the registered catalog does not support.
Ranking alone does not entail *permission to execute* or a calibrated no-match
decision. The [ClicShopping 8ada7f1 DEV-only run](https://github.com/JDeun/SchemaRouter/actions/runs/38126678518)
exposed that failure mode: 4/4 unsupported prompts still returned candidates.

This change adds an **opt-in abstention gate**, but does **not** claim the
ClicShopping OOD requests have been fixed or that the gate is calibrated.
No threshold is chosen from the published DEV test labels; the historic
32+10 reported cases, raw artifacts and their unchanged Top-3 protocol remain
untouched.

## Usage

```python
from schemarouter import (
    RetrievalAbstentionPolicy,
    apply_retrieval_abstention,
)

# Independently calibrate threshold on a different, representative labeled
# calibration cohort for THIS registry, scorer and version. 1.0 is an
# illustrative value only and NOT a recommended production threshold.
policy = RetrievalAbstentionPolicy(min_score=1.0)
retrieval = router.retrieve(user_request, k=3)  # same access control as before
decision = apply_retrieval_abstention(retrieval, policy=policy)

if decision.abstained:
    # Ask for clarification or return an unsupported-capability response.
    # Never execute a ranked candidate just because search returned one.
    handle_no_match(decision.reason)
else:
    send_shortlist_to_agent(decision.candidates)
```

Optional `min_margin` requires **two visible ranked candidates** to measure
top-versus-runner-up separation: `retrieve(k>=2)`. Missing runner-up is not a
large margin. Invalid/nonfinite score evidence and duplicate/unordered
candidate ranks are fail-closed. A numeric score and its margin are
**ranker-specific signals**, never probabilities or universal constants.

This helper operates strictly **after authorization-scoped retrieval** and
only removes candidates from that scoped surface. It never invents a route,
executes a call, changes existing `retrieve` defaults, mutates a registry,
or overrides host authorization. Downstream planning or execution APIs are
**not** automatically gated; hosts must intentionally honor `decision.abstained`.

## What counts as a validated improvement

1. Freeze the registry, scorer, source revisions, and an independently
   authored calibration cohort *before* choosing `min_score`/`min_margin`.
2. Freeze threshold and evaluation on fresh disjoint unseen queries/providers;
   preserve supported recall / false-refusal vs unsupported rejection,
   forbidden-action exposure, candidate bytes, p50/p95 latency and ambiguous
   requests. No tuning on the ClicShopping/ServiceNow/SmartMCP published DEV rows.
3. Report raw threshold-dependent misses, uncertainty and the catalog-specific
   tradeoff; no global performance claim from an opt-in mechanism alone.

Scientific 0.14 #432/#424 source, labels, evaluator and frozen episodes are
not modified or re-scored by this feature.

## Opt-in pre-execution enforcement — no-match means no tool call

For the normal host workflow, prefer **`ainvoke_selective()`**. It retrieves
executable capabilities and builds a plan internally from the same request,
using the same validated `RunConfig.principal` for both steps and final
execution. No application-supplied ranking or plan is accepted.

```python
from schemarouter import (
    RetrievalAbstentionPolicy, ainvoke_selective,
)

# The host must provide a threshold calibrated on independent data.
policy = RetrievalAbstentionPolicy(min_score=host_config.calibrated_min_score)
results = await ainvoke_selective(
    router, user_request, policy=policy, k=3,
    config=trusted_run_config,  # includes principal if applicable
)
```

An unsupported/no-match verdict raises `PolicyViolationError` before
dispatching. The remaining `execute_selective_plan()` low-level bridge is
for trusted hosts which already own both artifacts; such callers are
responsible for ensuring identical principal/authorization provenance.
Neither path introduces a built-in universal threshold.



The separate `execute_selective_plan()` bridge enforces the selection verdict
**before** handing a plan to the ordinary SchemaRouter executor. It is
opt-in and leaves existing `invoke()`, `ainvoke()` and `execute()` unchanged.
It cannot discover unsupported intents without an independently calibrated
policy; even an unsupported request can pass a too-permissive threshold.

```python
from schemarouter import (
    PlanRequest,
    PolicyViolationError,
    RetrievalAbstentionPolicy,
    execute_selective_plan,
)

request = PlanRequest(query=user_request)
# Host-owned calibration: never select this value from disclosed OOD failures.
policy = RetrievalAbstentionPolicy(min_score=host_config.calibrated_min_score)

# Obtain both values locally from the same authorized registry and principal.
retrieval = router.retrieve_executable(request, k=3)
plan = router.plan_executable(request)
try:
    results = await execute_selective_plan(
        router, retrieval, plan, policy=policy,
    )
except PolicyViolationError:
    # No call was dispatched through this wrapper.
    # Ask for clarification or return a no-capability response.
    results = []
```

The bridge re-applies abstention to the original retrieval (rather than
trusting externally supplied disposition metadata), rejects stale registry
versions or different queries, and demands that **every** primary/fallback
tool+endpoint and schema/tool fingerprint match the selected authorized
shortlist. It rejects out-of-shortlist output-field projections and
non-executable calls. Any rejection happens before the first call to
`router.execute`; afterward the ordinary executor still enforces its policy.

Important: applications must deliberately use this entrypoint and supply
host-generated retrieval and plans under the *same* authorization scope.
Passing in model-authored `CapabilityRetrieval`/`ExecutionPlan`, switching
principals, or invoking `router.ainvoke()` directly bypasses this optional
bridge. This is a **mechanical no-call** guarantee for an abstaining result,
not an execution-policy replacement, a safe default, or evidence that the
score distinguishes absent features in real workloads.

### Pre-planning no-match short circuit

The recommended `ainvoke_selective()` now checks the explicitly
calibrated policy and the retrieved shortlist **before invoking a
potentially costly or remote planner**. An empty, below-score or
below-margin retrieval, untrusted executable scope, stale registry,
wrong original query, invalid K or forged threshold configuration
terminates with **no planning or execution dispatch**. An admitted
shortlist is still revalidated against the resulting plan and live
registry immediately before ordinary execution. This guarantees neither
semantic absence detection nor a calibrated threshold; normal
`router.ainvoke()` is unchanged.

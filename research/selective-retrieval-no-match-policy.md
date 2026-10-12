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

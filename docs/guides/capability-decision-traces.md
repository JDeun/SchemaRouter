# Capability decision traces

SchemaRouter exposes several typed decision primitives for state, health, drift, host policy, operational constraints, negotiation, fallback eligibility, and routing lineage. A capability decision trace combines those **already computed** results into one privacy-safe explanation.

It is an observability layer, not a second policy engine.

## Build a trace

```python
from schemarouter import (
    CapabilityDecisionCandidateInput,
    build_capability_decision_trace,
)

trace = build_capability_decision_trace(
    [
        CapabilityDecisionCandidateInput(
            capability_id="materials.optimade.summary",
            visible=True,
            final_disposition="selected",
            retrieval="retrieved",
            health="healthy",
            drift="current",
            policy="allowed",
            state=state_eligibility,
            operational=operational_result,
            negotiation=negotiation_candidate,
            fallback=fallback_eligibility,
        )
    ],
    snapshot_id=snapshot.snapshot_id,
    registry_version=router.registry.version,
)
```

The trace preserves the component result objects and also emits a normalized reason list tagged by decision stage.

## Privacy boundary

Only host-visible candidates may appear in a trace. Passing `visible=False` suppresses the candidate entirely, including its identifier and rejection reason.

Decision traces intentionally exclude:

- request payload values;
- credentials and private headers;
- hidden capability inventory;
- rank scores;
- execution bindings or invocation authority.

The trace ID is deterministic over the visible structured trace content.

## Compact and detailed rendering

```python
from schemarouter import render_capability_decision_trace

compact = render_capability_decision_trace(trace)
detailed = render_capability_decision_trace(trace, detailed=True)
```

Compact rendering exposes final disposition, health/drift/policy state, and normalized reason codes. Detailed rendering additionally includes the already-computed state, constraint, negotiation, and fallback result objects.

## Router inspection and dashboard

Trace storage remains a host responsibility. SchemaRouter does not add a memory system or hidden trace database.

Pass traces explicitly when inspecting a live router:

```python
inspection = router.inspect(decision_traces=[trace])
```

The HTML dashboard renders a compact decision-trace table containing visible capability IDs, final dispositions, and reason codes only.

## CLI

A serialized `CapabilityDecisionTrace` can be inspected without executing any tool:

```bash
schemarouter inspect decision-trace decision-trace.json --json
schemarouter inspect decision-trace decision-trace.json --detailed --json
```

## Disabled tracing

Trace construction is opt-in. If a caller uses `build_capability_decision_trace(..., enabled=False)`, the function returns `None` and does not construct candidate trace objects.

Decision traces never plan, authorize, rank, retry, execute, compensate, or widen host visibility.

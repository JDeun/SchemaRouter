# Decision backends

SchemaRouter can optionally use a bounded decision model to refine choices that were already
derived from the local schema catalog. This feature is **off by default**.

Decision backends are not plan generators. They receive a finite set of locally authorized option
IDs and may select only from that set. SchemaRouter still constructs the typed execution plan and
retains policy, schema-validation, fingerprint, and execution authority.

## Opt in

```python
from schemarouter import CallableDecisionBackend, DecisionPolicy, SchemaPlanner

backend = CallableDecisionBackend(my_decision_model)
planner = SchemaPlanner(
    registry,
    decision_backend=backend,
    decision_policy=DecisionPolicy(
        enabled=True,
        endpoint_selection=True,
        fallback="deterministic",
    ),
)
```

The master `enabled` switch must be true. Individual surfaces are separately configurable:

- `tool_selection`
- `endpoint_selection`
- `field_selection`
- `evidence_sufficiency`

In the initial v0.3 contract, bounded candidate selection is active when tool or endpoint selection
is enabled. Field and evidence switches are reserved controls and do not silently change behavior
until their dedicated bounded contracts are implemented.

## Fallbacks

`fallback="deterministic"` is the default. Invalid output, unknown option IDs, or abstention falls
back to SchemaRouter's deterministic ranking and adds a warning to the plan.

Use `fallback="error"` when a decision failure must stop planning.

## Jev and experimental models

Jev-style/System-One decision models should be integrated through `DecisionBackend`, not imported
into SchemaRouter core. They are experimental, optional, and never enabled merely because a package
or API credential is present. Provider adapters must preserve the same finite-option contract.

This separation lets applications change or disable a decision model without changing registered
tools, execution policy, or the deterministic planner.

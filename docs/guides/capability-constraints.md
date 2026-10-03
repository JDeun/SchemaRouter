# Host operational capability constraints

Hosts can attach optional operational metadata to equivalent capabilities and apply hard constraints without transferring policy authority to SchemaRouter.

```python
from schemarouter import CapabilityOperationalMetadata, HostCapabilityConstraints, evaluate_operational_constraints

result = evaluate_operational_constraints(
    CapabilityOperationalMetadata(locality="local", estimated_latency_ms=25),
    HostCapabilityConstraints(allowed_localities={"local"}, max_latency_ms=100),
)
```

Hard constraints cover latency, cost, local/remote execution, residency region, privacy class, and network use. If a hard constraint is declared but the required metadata is unknown, evaluation fails closed with `metadata_unknown`. Soft preferences never make an ineligible candidate eligible; they only produce a deterministic preference score for candidates that already pass all hard constraints. Missing metadata used only by a soft preference is ignored gracefully.

This API does not infer permissions, fetch dynamic prices, allocate budgets, or execute capabilities. The host defines the constraints and remains the policy authority.

# Capability eligibility explanations

SchemaRouter can return a structured explanation for why a host-visible capability is eligible or excluded. Reasons use stable codes and may contain child reasons, allowing adapters and observability surfaces to render a tree without parsing free text.

```python
from schemarouter import CapabilityEligibilityReason, explain_capability_eligibility

explanation = explain_capability_eligibility(
    "materials.summary",
    visible=True,
    reasons=[CapabilityEligibilityReason(code="method_unhealthy")],
)
```

Supported reason classes cover state, semantic/type/unit compatibility, health, drift, policy, privacy, locality, cost, and unknown/unsupported conditions.

## Non-disclosure boundary

The API requires the host to state whether a capability is already visible. For `visible=False` it returns `None`, regardless of supplied reasons. This prevents the explanation surface from revealing whether a hidden capability exists or which authorization rule hid it. Explanations describe routing eligibility only; they do not grant authorization or execute a capability.

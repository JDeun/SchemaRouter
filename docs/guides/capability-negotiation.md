# Host-driven capability contract negotiation

A host may submit an explicit output contract and receive deterministic compatibility results for declared capability contracts. Negotiation distinguishes exact, compatible, convertible, incompatible, unknown, policy-denied, and unavailable candidates.

```python
from schemarouter import CapabilityNegotiationRequest, negotiate_capabilities

result = negotiate_capabilities(
    CapabilityNegotiationRequest(required_outputs=required_fields),
    capabilities,
    authorized_capability_ids=host_allow_set,
    unavailable_capability_ids=unavailable,
    context=compatibility_context,
)
```

Authorization is an intersection, never an expansion. An empty host allow-set remains empty in effect, and unavailable candidates are distinguished from contract mismatches. Unit conversion is only reported when explicitly declared in the compatibility context; SchemaRouter does not perform the conversion.

Matching top-level JSON types alone does not prove a constrained field contract. If a required schema has assertions such as `enum`, numeric bounds, `items` or object properties, the produced schema must retain the same assertions. Different assertions return `unknown`, including stricter constraints whose compatibility has not been proved. Descriptive annotations do not affect this comparison; integer outputs may still satisfy number requirements. This conservative declaration check does not replace runtime value validation.

Negotiation is a contract query, not planning or execution. Existing stateless query-based routing remains independent and supported.

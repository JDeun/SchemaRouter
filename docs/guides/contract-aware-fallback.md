# Contract-aware fallback eligibility

Fallback eligibility can compose host authorization, method health, capability-contract validation, contract drift, typed state eligibility, and retrieval membership.

```python
from schemarouter import evaluate_fallback_eligibility

result = evaluate_fallback_eligibility(
    authorized=True,
    healthy=True,
    contract_validation=validation,
)
```

A transport can therefore be healthy but excluded when its declared contract is missing, incompatible, unverifiable, or drifted. `eligible_fallback_ids()` filters already evaluated candidates in host-supplied order; it does not execute them.

Backward compatibility is explicit: when contract/state metadata is not supplied, the primitive preserves the historical authorization + health behavior. Host denial always wins and can never be widened by fallback. SchemaRouter returns eligibility/candidate information only; the host owns execution, conversion, retry, and response handling.

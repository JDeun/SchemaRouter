# State-aware capability retrieval

External runtimes can filter ordinary capability retrieval against explicit typed execution state without giving SchemaRouter workflow or execution authority.

The stable `retrieve(request, *, k=5)` facade remains stateless and backward-compatible. Use the explicit state-aware surface when host state must participate in eligibility:

```python
from schemarouter import CapabilityFieldContract, TypedExecutionState

eligible = router.retrieve_state_aware(
    "continue the material lookup",
    execution_state=TypedExecutionState(...),
    state_requirements={
        "materials.summary": [
            CapabilityFieldContract(
                semantic_id="resource.material_id",
                json_schema={"type": "string"},
            )
        ]
    },
)
```

The asynchronous counterpart is `await router.aretrieve_state_aware(...)`. The lower-level `filter_retrieval_by_state(...)` helper remains available when a host already has a `CapabilityRetrieval` object.

## Filtering versus state-conditioned backfill

`retrieve_state_aware(...)` deliberately keeps fixed-Top-K semantics: SchemaRouter ranks K candidates first and then removes candidates that are incompatible with the supplied state. This preserves the original public behavior.

When the host wants the best K **eligible** candidates from the visible ranked surface, use the explicit corrective API:

```python
refreshed = router.reretrieve_state_aware(
    "continue the material lookup",
    execution_state=state,
    k=5,
    state_requirements=requirements,
    state_preconditions=preconditions,
)
```

The asynchronous counterpart is `await router.areretrieve_state_aware(...)`.

This API evaluates the same visible/available capability surface used by normal retrieval, preserves original global ranks, and backfills past state-ineligible candidates until K eligible candidates are found or the visible surface is exhausted. `refreshed.excluded` contains the rejected visible candidates together with structured state-eligibility reasons.

It never searches outside the host-visible registry surface and never uses hidden future-route labels, prior gold decisions, or authorization-invisible capabilities as an oracle.

`state_requirements` and `state_preconditions` are explicit host-supplied contract metadata. SchemaRouter does not infer workflow preconditions from route names, parameter names, descriptions, previous rank positions, or hidden future routes.

A declared requirement with missing or incompatible typed state is excluded fail-closed; routes with no declared state requirement retain stateless behavior. Existing `router.retrieve(query, k=...)` and `router.aretrieve(...)` callers therefore keep the original `CapabilityRetrieval` contract and signature.

This surface returns capability information only. It does not select a workflow, execute a capability, commit or roll back a transaction, mutate host state, schedule retries, compensate an operation, or widen authorization. Host runtimes remain responsible for policy, availability, execution, retry, and compensation.

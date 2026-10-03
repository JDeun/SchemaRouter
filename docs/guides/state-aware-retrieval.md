# State-aware capability retrieval

External runtimes can apply explicit typed execution state to capability retrieval without giving SchemaRouter workflow or execution authority.

The stable `retrieve(request, *, k=5)` facade remains stateless and backward-compatible.

## Filter a fixed Top-K

Use `retrieve_state_aware(...)` when the host already wants the ordinary Top-K ranking and only needs to remove candidates that are not eligible under observable state:

```python
from schemarouter import CapabilityFieldContract, TypedExecutionState

eligible = router.retrieve_state_aware(
    "continue the material lookup",
    execution_state=TypedExecutionState(...),
    k=5,
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

This path is intentionally:

```text
ordinary Top-K -> state eligibility filter
```

It does **not** refill candidates removed from that fixed Top-K.

## Re-retrieve and backfill eligible Top-K

Use `reretrieve_state_aware(...)` when the host needs the best K eligible candidates from the complete visible ranking:

```python
eligible = router.reretrieve_state_aware(
    "continue the material lookup",
    execution_state=TypedExecutionState(...),
    k=5,
    state_requirements=state_requirements,
    state_preconditions=state_preconditions,
)
```

This path is:

```text
visible ranked capability surface
        |
        v
explicit state requirements / preconditions
        |
        v
first K eligible candidates
```

If an initial candidate is excluded, SchemaRouter continues down the already visible ranking until K eligible candidates are found or the visible surface is exhausted.

The result records:

- the selected candidate's `original_rank` before state filtering;
- its compact eligible rank in `candidate.rank`;
- excluded visible candidates and their structured `StateEligibility` reasons;
- `examined_count` and whether the visible surface was exhausted.

Candidates hidden by registry/availability policy are never introduced by backfill and are not leaked through the exclusion trace.

The asynchronous counterparts are `await router.aretrieve_state_aware(...)` and `await router.areretrieve_state_aware(...)`.

The lower-level `filter_retrieval_by_state(...)` and `backfill_retrieval_by_state(...)` helpers remain available when a host already owns a `CapabilityRetrieval` object.

## State boundary

`state_requirements` and `state_preconditions` are explicit host-supplied contract metadata. SchemaRouter does not infer workflow preconditions from route names, parameter names, descriptions, previous rank positions, undocumented payload text, or hidden future routes.

A declared requirement with missing or incompatible typed state is excluded fail-closed. Routes with no declared state requirement retain stateless behavior.

Neither state-aware surface chooses a workflow, executes a capability, commits or rolls back a transaction, mutates host state, schedules retries, compensates an operation, or widens authorization. Host runtimes remain responsible for policy, availability, execution, retry, and compensation.

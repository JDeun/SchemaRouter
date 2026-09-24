# Planning and field projection

Planning converts a request into one or more schema-constrained `ToolCall` objects.

## Input

The planner accepts either a string or a `PlanRequest`.

```python
from schemarouter import PlanRequest

request = PlanRequest(
    query="LiFePO4 band gap",
    arguments={"formula": "LiFePO4"},
    max_calls=1,
)
```

A `PlanRequest` can also carry preferred tools, explicit concepts, and evidence requirements.

## Analysis

The default `KeywordAnalyzer` is deterministic and offline. It maps terms in the query onto declared
tools, endpoints, parameters, and fields.

For richer natural-language extraction, `ModelQueryAnalyzer` can be injected. Model output is still
only a proposal: unknown tools, endpoints, parameters, and fields are removed before deterministic
planning continues.

## Candidate scoring

The planner favors:

1. explicitly preferred endpoints;
2. explicitly preferred tools;
3. schema names and aliases that match inferred concepts;
4. endpoints whose parameters can be satisfied.

The score is a selection heuristic, not execution authority.

## Structured plan explanations

Every planned call can carry a `PlanExplanation` with locally observable routing facts:

- deterministic score components;
- why each projected field was retained;
- undeclared argument names that were ignored;
- whether a bounded decision backend selected the candidate.

```python
plan = router.plan(
    PlanRequest(
        query="LiFePO4 band gap",
        arguments={"formula": "LiFePO4", "unknown": 1},
    )
)

explanation = plan.calls[0].explanation
for component in explanation.score_components:
    print(component.kind, component.value, component.matched)

for field in explanation.field_selection:
    print(field.field, field.reason)
```

This is not model chain-of-thought. It contains deterministic/runtime-visible facts that
SchemaRouter itself can verify. If a model-assisted analyzer or bounded decision backend is used,
the explanation records only the resulting bounded selection surface—not the provider's hidden
reasoning.

## Field projection

When an endpoint declares projectable output fields, the planner chooses fields using a recall-first
strategy.

```text
clear field match
 -> selected fields + identifiers

ambiguous or no useful match
 -> retain declared fields rather than aggressively pruning
```

This design follows the research finding that overly aggressive projection can reduce downstream
answer quality even when it improves field-level precision.

## Missing required arguments

Missing values are surfaced in the plan instead of hallucinated.

```python
plan = router.plan("get a user")
print(plan.executable)  # False when a required user_id is missing
```

The executor recomputes required arguments again immediately before invocation, so a forged or stale
`missing_required_arguments` list cannot bypass the contract.


## Precompiled provider/access fallbacks

A `PlanRequest` can opt into bounded read-only fallback planning:

```python
request = PlanRequest(
    query="Si band gap",
    preferred_tools=["mp_api"],
    fallback_scope="cross_provider",
    max_fallbacks=3,
)
```

Each fallback is a complete `ToolCall` compiled against its own schema and tool fingerprint.
Same-provider access paths are ordered before candidates from another provider. Field aliases are
used to prove semantic compatibility when access paths expose different field names.

Fallback is not model-driven replanning and remains disabled by default. See
[Provider-aware fallback](../guides/provider-fallback.md).

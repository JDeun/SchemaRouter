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

## Semantic field coverage

For requests that match declared semantic fields, `ExecutionPlan.coverage` exposes the planner's
bounded coverage state as structured data:

```python
plan = router.plan(
    PlanRequest(
        query="band gap and paper abstract",
        max_calls=2,
    )
)

print(plan.coverage.required)
print(plan.coverage.covered)
print(plan.coverage.uncovered)
print(plan.coverage.complete)
```

`required` is derived from the full schema-recalled candidate set before bounded decision assistance
can narrow or prioritize candidates. `covered` reflects the fields actually retained by the compiled
primary calls. If `max_calls`, policy, missing bindings, or another local constraint prevents complete
coverage, `uncovered` remains explicit and the plan includes an `uncovered semantic field
requirements` warning.

For explicit multi-call plans, a bounded decision backend may prioritize candidates but does not
delete the deterministic schema-recalled pool. Final call selection remains constrained by
complementary semantic-field coverage and the existing `max_calls` authority boundary. This prevents
two redundant access paths for the same field from consuming all call slots while another required
field still has an available route.

Single-call decision behavior and empty-lexical-recall fail-closed behavior remain unchanged.

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


## Evidence requirements are local constraints

`PlanRequest.evidence` is enforced from trusted local contracts even when no model-backed
decision backend is configured.

For example:

```python
PlanRequest(
    query="elastic modulus",
    evidence=EvidenceRequirements(units=True),
)
```

requires the selected answer fields to declare units. A unitless arXiv abstract or web snippet is
still a perfectly valid field in ordinary planning; it is excluded only when the request explicitly
requires unit evidence.

The same rule applies to requested provenance, license, and source type. Global evidence requirements
apply to the **entire selected answer surface**. For provenance specifically, a tool-level
`source_type` covers the route; otherwise every selected answer field must declare its own
`source_type`. Evidence on only one of several selected fields is not enough to satisfy a global
provenance requirement.

An optional decision backend may reject locally sufficient evidence, but it cannot manufacture
evidence that the registry does not declare.

### Per-field evidence requirements

Global `PlanRequest.evidence` intentionally applies to the whole selected answer surface. For a
heterogeneous request, callers can instead attach evidence to one semantic field without imposing it
on unrelated fields:

```python
from schemarouter import EvidenceRequirements, PlanRequest

request = PlanRequest(
    query="band gap and paper abstract",
    max_calls=2,
    field_evidence={
        "band_gap": EvidenceRequirements(units=True),
    },
)
```

Here the `band_gap` route must expose unit metadata, while the unitless
`document_abstract` route remains valid. Keys in `field_evidence` match the trusted canonical
`FieldSpec.semantic_id` (or the field name when no semantic ID exists), not aliases or
model-authored remappings.

The contract is additive: global evidence still applies to every selected answer field, and matching
field-specific evidence adds stricter requirements for that semantic field. Conflicting global and
field-specific source-type constraints are rejected. The compiled `ToolCall.field_evidence` map
records which local provider field received each explicit field-specific requirement.

Per-field evidence is caller-controlled. `ModelQueryAnalyzer` preserves it but does not expose it to
the model or let model output introduce, remove, or broaden those trusted constraints. Active
`field_evidence` keys must resolve to a registered canonical semantic field ID (or field name when no
semantic ID is declared); unknown active keys fail closed instead of being silently ignored.

### Required evidence vs available evidence

Compiled calls keep requirement and capability state separate:

- `ToolCall.required_evidence` is the caller's global requirement for that call;
- `ToolCall.field_evidence` contains caller requirements mapped onto selected local fields;
- `ToolCall.evidence` records evidence actually declared as available by the selected route.

This distinction prevents a requested property from being mistaken for provider capability. The
executor recomputes evidence from the current trusted `ToolSpec` / `FieldSpec` contract immediately
before execution. It rejects forged evidence overclaims, unmet global requirements, unmet per-field
requirements, requirements attached to unselected fields, and conflicting global/per-field source
types. Schema/tool fingerprints continue to protect against drift, but evidence is revalidated even
for manually constructed calls.


## Parameter aliases are bounded argument routing

Planner argument compilation first binds exact endpoint parameter names. Remaining supplied
arguments may bind through one-to-one trusted `ParameterSpec.aliases`.

This matters for provider fallback. One request can preserve the same semantic value while each
precompiled route receives the key required by its own contract:

```text
request arguments: {"formula": "Si"}

provider A -> {"formula": "Si"}
provider B -> {"chemical_formula": "Si"}
```

The value `"Si"` is not transformed. Ambiguous alias relationships remain unbound, required
parameters remain missing, and planning warnings identify the ambiguous input key.

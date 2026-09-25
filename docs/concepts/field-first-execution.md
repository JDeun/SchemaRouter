# Field-first execution

SchemaRouter is designed around a **field-first, route-second** principle.

The goal is not merely to choose a tool. The goal is to identify the smallest declared data surface
that can answer the user's question, then choose a trusted access path that can provide that surface.

```text
user query
  -> semantic data need
  -> required logical fields
  -> providers/access paths that can supply those fields
  -> availability + policy + evidence
  -> server-side field selection when supported
  -> raw schema validation
  -> final local projection
  -> minimal ToolResult context
```

## Why field-first matters

If a user asks for one material property such as elastic modulus, fetching a complete material
record can create avoidable cost:

- more upstream response bytes and latency;
- more JSON parsing and validation work;
- more irrelevant values in downstream LLM context;
- more prompt tokens;
- a higher chance that unrelated properties distract answer generation.

SchemaRouter therefore treats response fields as part of the execution plan rather than an
afterthought.

## Logical fields before provider selection

Different providers and access modes can expose the same concept under different names:

```text
elastic modulus
  -> provider A / REST       -> elastic_modulus
  -> provider B / OPTIMADE   -> _b_elasticity
  -> provider C / Python     -> youngs_modulus
```

Local `FieldSpec` contracts declare known semantic equivalence. Prefer one canonical local
`FieldSpec.name` for the concept. Keep provider-specific request selector names in
`ServerProjectionSpec.field_map`, provider response locations in `FieldSpec.path`, and use
`FieldSpec.result_path` when the final projected result should be written to a different canonical
location. `aliases` help the planner recognize user phrasing and legacy/provider terminology.

For example, all three access paths can expose the local field `elastic_modulus` while mapping it
to `elastic_modulus`, `_b_elasticity`, or `youngs_modulus` on the wire. A provider-specific
source path can still be projected into `result_path=["elastic_modulus"]`, so the planner and final
`ToolResult` stay provider-neutral.

The model does not get to invent field mappings.

## Unit metadata is optional by field semantics

`FieldSpec.unit` is a general optional contract, not an arXiv/Web special case.

A field should carry a unit only when the value is a physical or otherwise explicitly unit-bearing
quantity. Unitless fields can come from any provider or access mode:

```text
paper abstract / title / snippet   -> string, unit=None
material identifier / DOI         -> string, unit=None
phase / category / label          -> string, unit=None
flags                             -> boolean, unit=None
structured metadata              -> object/array, unit=None
dimensionless score or ratio      -> number, unit=None
physical quantity                 -> number/array, unit="..." when declared
```

Therefore OpenAPI, MCP, OPTIMADE, Python, documentation-derived adapters, or any approved plugin
can expose unitless fields. The source type does not decide whether a unit exists; the field
contract does.

If a caller explicitly sets `EvidenceRequirements(units=True)`, unitless answer fields cannot
satisfy that particular evidence requirement. That is different from saying unitless fields are
invalid.

## Heterogeneous multi-source field requirements

One user question can require fields that no single endpoint provides. SchemaRouter can compile a
bounded multi-call plan when the caller explicitly allows more than one call with `max_calls`.

For example:

```text
query need
  -> band_gap
       -> Materials Project / OpenAPI
       -> Materials Project / OPTIMADE
  -> abstract
       -> arXiv / API
```

With `max_calls=2`, multi-call planning prefers **complementary semantic field coverage** over
spending both call slots on equivalent access paths for the same already-covered field. Equivalent
routes collapse through `semantic_id`; an exact qualifier such as `temperature=300 K` remains a
separate requirement only when that qualifier is visibly requested.

```python
plan = router.plan(
    PlanRequest(
        query="band gap and paper abstract",
        max_calls=2,
    )
)
```

The hard bound remains `max_calls`; SchemaRouter never increases it automatically. The default is
`1`, so multi-source fan-out is an explicit cost/authority choice by the application.

Each call still receives its own field projection, schema fingerprint, provider/access identity,
health/binding checks, policy checks, and fallback chain. If all calls are explicitly read-only,
the executor can use the bounded `parallel_read_only` execution surface; otherwise normal
execution remains sequential and policy-gated.

## Two layers of projection

SchemaRouter minimizes data at two different boundaries.

### 1. Server-side projection

When an endpoint has an explicit trusted `ServerProjectionSpec`, planned fields are pushed into
the upstream request:

```python
EndpointSpec(
    name="search",
    # ...
    server_projection=ServerProjectionSpec(
        parameter="fields",
        field_map={
            "elastic_modulus": "elasticity.bulk_modulus",
        },
    ),
)
```

A call selecting only:

```text
material_id
elastic_modulus
```

can therefore become:

```text
GET /materials?fields=material_id,elasticity.bulk_modulus
```

SchemaRouter never guesses that a generic OpenAPI parameter means field projection. The contract
must be declared locally or by a trusted adapter. OPTIMADE's `response_fields` is a built-in
example.

For explicit provider source paths such as `elasticity.bulk_modulus`, projected raw-schema
validation can narrow nested **object-only** paths recursively. A root array whose items are objects
is also supported. Paths that require traversing an array, unresolved `$ref`, unions, or another
shape that cannot be narrowed conservatively keep the full declared schema and therefore fail
closed rather than weakening validation.

### 2. Final local projection

Even when an upstream service ignores or cannot perform server-side projection, SchemaRouter
validates the raw response and then keeps only the planned logical fields before producing the
`ToolResult`.

So the downstream answer-generation context stays narrow even when the provider returns a broader
payload.

## Availability changes the route, not the data need

The requested field surface remains stable while access paths can change:

```text
need: elastic modulus

provider A / REST
  healthy -> eligible for planning

provider B / OPTIMADE
  known unavailable -> excluded from the current planner candidate surface

provider C / API
  fallback -> use only if it can provide elastic modulus
```

Fallback does not broaden the requested fields merely because the preferred route failed.
A newly observed outage is handled by the precompiled fallback chain; once that route enters the
bounded cooldown, later plans exclude it until the cooldown expires or a trusted health signal
reopens it.

See [Provider-aware fallback](../guides/provider-fallback.md).

## Passive and active availability

Transport failures such as timeouts, connection failures, HTTP 429, or transient 5xx responses can
place an access path into a bounded cooldown. Cooldown always expires, so a path is never permanently
blacklisted by one failure.

For faster recovery, applications can register trusted read-only health probes. A background health
monitor can reopen a path immediately after a probe succeeds.

The monitor never invents a probe and never turns arbitrary data calls into health checks.

## Recall-first safety boundary

Field minimization is aggressive only when the query-to-field match is clear.

If SchemaRouter cannot confidently identify the answer field, the default planner preserves declared
fields rather than pretending to know which one is sufficient. This protects answer recall.

So the rule is:

```text
clear semantic match -> minimize
ambiguous semantic need -> preserve recall
```

Applications that need stronger domain-specific minimization should improve local aliases/schemas or
use a bounded analyzer rather than weakening validation.


## Typed scientific fields and units

Field selection is not only about names. Scientific fallbacks must preserve the value contract.

`FieldSpec.json_schema` carries the declared value type/shape and `FieldSpec.unit` carries the
provider source unit. When providers use different units for the same semantic field, applications
can add an explicit `UnitNormalizationSpec`:

```python
FieldSpec(
    name="elastic_modulus",
    semantic_id="elastic_modulus",
    json_schema={"type": "number"},
    unit="GPa",
    unit_normalization=UnitNormalizationSpec(
        dimension="pressure",
        canonical_unit="Pa",
        scale=1e9,
    ),
)
```

SchemaRouter does **not** infer conversion factors from unit strings. Unit symbols are
case-/punctuation-sensitive and the conversion contract is trusted local configuration.

Fallback compatibility is conservative:

```text
same semantic field
  AND explicit compatible JSON value type
      (required for unit-bearing cross-provider fallback)
  AND (
        same explicit source unit
        OR same declared dimension + same canonical unit
      )
```

A unit label by itself is not enough to establish a scientific value contract. If a unit-bearing
field participates in automatic provider fallback, both sides must expose an explicit datatype
shape through `FieldSpec.json_schema` or the declared endpoint output schema. Unknown datatype +
known unit is treated as insufficient evidence for automatic fallback.

When both a field-level schema and a raw endpoint output schema describe the same value, their type
shapes must be compatible. The whole raw response is validated first, then selected values are also
validated against any stronger `FieldSpec.json_schema` contract before unit normalization.

Numeric type compatibility is directional: an integer-producing fallback can satisfy a numeric
requirement, but an arbitrary number-producing fallback cannot satisfy an integer-only requirement.
Numeric arrays also compare their item types.

Execution order remains fail-closed:

```text
provider raw value
  -> raw JSON Schema validation
  -> field projection / canonical result path
  -> explicit unit normalization
  -> ToolResult
```

This means a provider returning `"130"` for a numeric GPa field fails before conversion.

`ToolResult.field_contracts` exposes only the selected field contracts needed downstream:

```python
result.field_contracts["elastic_modulus"]
# ResultFieldContract(
#     semantic_id="elastic_modulus",
#     json_schema={"type": "number"},
#     source_unit="GPa",
#     unit="Pa",
#     dimension="pressure",
# )
```

So answer-generation code can consume a compact canonical value plus the unit/type contract without
pulling unrelated provider metadata into context.

Affine conversions are supported explicitly:

```text
canonical_value = source_value * scale + offset
```

This covers SI-prefix scaling and offset units when the application declares the exact conversion.
For example, `degC -> K` can use `scale=1.0, offset=273.15`. A source unit that is already equal
to the canonical unit must use the identity transform; contradictory same-unit conversion contracts
are rejected or excluded from fallback.

The planner compares the **post-normalization result datatype**, not just the provider raw datatype.
For example, an integer source value converted by an affine unit contract is treated as a canonical
JSON `number`, so a provider that already returns the canonical quantity as `number` can be a
valid fallback.

Unit symbols remain exact and case-/punctuation-sensitive. Surrounding whitespace is rejected.
Nonlinear/logarithmic conversions are not inferred or synthesized. Non-finite/overflowed normalized
values fail closed.


## Scientific field qualifiers

A semantic field name, datatype, and unit are not always sufficient to prove that two scientific
values are interchangeable. The value may depend on a fixed measurement/material context such as:

- temperature;
- pressure;
- phase;
- crystal orientation;
- measurement method;
- sample state.

`FieldSpec.qualifiers` is an optional trusted exact-string map for this context:

```python
FieldSpec(
    name="elastic_modulus",
    semantic_id="elastic_modulus",
    json_schema={"type": "number"},
    unit="GPa",
    qualifiers={
        "temperature": "300 K",
        "phase": "alpha",
        "orientation": "[100]",
    },
)
```

Qualifiers are optional. Text/document/search fields and scientific fields with no fixed contextual
constraint normally keep `qualifiers={}`.

Automatic provider fallback requires exact qualifier equality after semantic/type/unit checks. A
300 K field is therefore not silently substituted with a 500 K field, and a qualified field is not
silently substituted with an unqualified field.

Qualifier values are deliberately opaque and case-sensitive. SchemaRouter does not infer that
`300 K` equals `26.85 degC`, normalize phase names, parse crystallographic notation, or derive a
measurement condition from natural language. If multiple provider representations are known to mean
the same condition, trusted adapter/application code should canonicalize them before registration.

Selected qualifiers are preserved in `ToolResult.field_contracts`, so downstream answer generation
can consume the minimal value together with the context that gives the value its meaning.


### Qualifier-aware routing remains lexical and bounded

Trusted qualifiers can also break ties between otherwise equivalent schema candidates when the
qualifier value is visibly present in the user query. For example, between two
`elastic_modulus` endpoints qualified as `300 K` and `500 K`, the query
`elastic modulus at 500 K` receives a deterministic score boost only for the `500 K` field.

This is exact lexical routing, not scientific inference. SchemaRouter does not convert temperatures,
expand synonyms, or infer unstated experimental conditions. ASCII and numeric qualifier values are matched on token boundaries, so `300 K` does not match
`1300 K`. Very short ASCII qualifier values are not matched by value alone. Bounded field-selection backends also
receive the trusted qualifier tags in their option descriptions, while execution metadata remains
outside the decision surface.

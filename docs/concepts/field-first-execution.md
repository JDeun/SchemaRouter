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


## Typed quantity input arguments

Scientific retrieval often needs unit-bearing filters as well as unit-bearing output fields.
For example, one provider may accept `max_size` in meters while another accepts nanometers.

SchemaRouter preserves the existing raw-argument contract:

```python
PlanRequest(
    query="particle size",
    arguments={"max_size": 1e-7},
)
```

A plain number remains **provider-native**. SchemaRouter does not reinterpret or convert it.

Unit-aware conversion is opt-in through `QuantityArgument`:

```python
from schemarouter import (
    ParameterSpec,
    QuantityArgument,
    UnitNormalizationSpec,
)

parameter = ParameterSpec(
    name="max_size",
    json_schema={"type": "number"},
    unit="m",
    unit_normalization=UnitNormalizationSpec(
        dimension="length",
        canonical_unit="nm",
        scale=1e9,
    ),
)

request = PlanRequest(
    query="particles below 100 nm",
    arguments={
        "max_size": QuantityArgument(
            value=100.0,
            unit="nm",
        )
    },
)
```

The local parameter contract means:

```text
canonical_value = provider_value * scale + offset
```

so the planner can safely invert it for input:

```text
provider_value = (canonical_value - offset) / scale
```

The example above compiles `100 nm` to `1e-7 m` for that provider.

If a fallback provider accepts `nm` directly, its separately compiled `ToolCall` keeps
`max_size=100`. Every provider/access route therefore receives its own native argument value.

### Trust boundary

A `QuantityArgument` carries only:

- a numeric scalar or numeric array;
- an exact unit label.

It carries **no** scale, offset, physical dimension, or conversion authority. Those values remain in
trusted local `ParameterSpec.unit_normalization`.

Model-backed analyzers may structure an explicit query quantity as:

```json
{"value": 100, "unit": "nm"}
```

but the model-visible catalog exposes only the provider unit and canonical unit names, not
conversion factors. A model cannot invent a conversion factor that SchemaRouter will execute.

Remote OpenAPI/MCP annotations such as `x-ucum-unit`, `x-unit`, or `unit` are likewise preserved
only as provider-unit labels. They never synthesize a `UnitNormalizationSpec`.

### Candidate behavior

For a unit-bearing parameter:

- a typed quantity already expressed in the provider unit is passed through;
- a typed quantity expressed in the declared canonical unit is converted to provider-native units;
- any other unit makes that candidate incompatible;
- SchemaRouter continues evaluating other schema-compatible providers/access paths;
- converted provider-native values are validated against the declared parameter JSON Schema before
  the call is compiled.

This keeps field-first/provider-aware routing intact for scientific filters without introducing a
general unit-inference engine.

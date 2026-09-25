# Adapter authoring

Adapters connect structured capability sources to SchemaRouter without changing the core planner,
registry, policy, or executor.

## SourceAdapter contract

A source adapter has a stable `kind`, a discovery `priority`, and one async load method:

```python
from schemarouter import (
    AdapterContext,
    AdapterLoadResult,
    SourceAdapter,
)


class MyAdapter:
    kind = "my_protocol"
    priority = 50

    async def load(
        self,
        context: AdapterContext,
    ) -> AdapterLoadResult | None:
        ...
```

Return `None` when the source is not recognized during auto discovery. Return
`AdapterLoadResult(tool=..., invoker=...)` when the source is supported.

## Registering adapters

```python
router = SchemaRouter()
router.register_adapter(MyAdapter())

tool = await router.add_url(
    "https://example.com/capability",
    kind="my_protocol",
)
```

Applications can also construct an `AdapterRegistry` and inject it into `SchemaRouter`.

## Publishing a third-party adapter

Installed packages can expose adapters through the `schemarouter.adapters` entry-point group:

```toml
[project.entry-points."schemarouter.adapters"]
my_protocol = "my_package.adapter:MyAdapter"
```

SchemaRouter never auto-imports discovered plugins. Applications must explicitly allowlist plugin
entry-point names:

```python
router.load_adapter_plugins(allowlist={"my_protocol"})
```

Use `discover_adapter_plugins()` to inspect metadata without importing plugin code. Unknown
allowlisted names fail before any plugin is loaded. See
[Third-party adapter plugins](guides/adapter-plugins.md) for the complete trust model.

## Adapter responsibilities

A schema adapter should return:

- a `ToolSpec`;
- one or more `EndpointSpec` objects;
- declared `ParameterSpec` objects;
- declared `FieldSpec` objects when fields are projectable;
- input/output JSON Schema where the source provides it;
- descriptive metadata marked as untrusted when it originates remotely;
- `tool.remote=True` for capabilities whose invoker crosses a remote trust boundary;
- `ToolSpec.execution_metadata` / `EndpointSpec.execution_metadata` for JSON-safe values that
  alter transport/runtime behavior and therefore must participate in fingerprints.

A normal transport adapter can provide an invoker compatible with:

```python
invoker(endpoint_name: str, arguments: dict[str, Any]) -> Any | Awaitable[Any]
```

Protocols whose transport needs the planner-selected fields may instead implement:

```python
invoke_call(call: ToolCall) -> Any | Awaitable[Any]
```

The OPTIMADE adapter uses this call-aware path to translate `ToolCall.fields` into
`response_fields`. Future GraphQL/OData adapters can use the same mechanism for selection sets or
`$select` without putting protocol logic into the core executor.

The invoker is bound through `RegistryExecutor.bind()`, so tool fingerprint drift remains
enforceable.

## Trust boundary

Adapters must not:

- turn remote annotations into local mutation/destructive permission;
- expose API keys, cookies, bearer tokens, or other runtime secrets as model-selectable parameters;
- silently follow an endpoint to an unapproved origin;
- coerce invalid model values into schema-valid values behind the executor;
- skip SchemaRouter input/output validation;
- call a remote service directly from planning.

Remote adapters must set `tool.remote = True` (or construct `ToolSpec(remote=True, ...)`) so
unclassified side effects remain policy-gated. Ordinary `metadata` is descriptive only and must
not be read by an invoker to decide execution origin, transport target, request encoding, or other
runtime semantics.

If an invoker needs adapter-specific runtime values, put them in fingerprinted
`execution_metadata`. For example:

```python
tool = ToolSpec(
    name="graphql",
    remote=True,
    execution_metadata={
        "adapter": "graphql",
        "approved_base_url": approved_base_url,
    },
    endpoints=[
        EndpointSpec(
            name="query",
            execution_metadata={"selection_mode": "typed"},
            # ...
        )
    ],
)
```

Do not place credentials in either metadata bag. Secrets remain only in the trusted invoker object.
A discovery/schema URL is provenance, not automatically runtime identity; keep it descriptive unless
the invoker actually calls that URL. If a URL is part of `execution_metadata`, require a stable,
credential-free form and keep query/fragment authentication in trusted transport configuration.

## Schema fidelity

Preserve the richest source schema available. Flattened fields may be useful for planning and
projection, but the full input/output schema should remain available for runtime validation.

Unsupported constructs should be preserved as metadata or rejected explicitly rather than guessed.

## Custom registries

Applications can provide any structural implementation of `ToolRegistry`:

```python
from schemarouter import SchemaRouter, ToolRegistry

registry: ToolRegistry = MyPersistentRegistry(...)
router = SchemaRouter(registry=registry)
```

The registry must provide a monotonic version and current tool/endpoint lookup semantics. Read
methods must return detached snapshots or immutable equivalents; callers must not be able to mutate
stored schemas without a versioned write. Persistent implementations are responsible for
concurrency control and atomic replacement.

## Conformance expectations

New adapters should test:

- explicit-kind and auto-discovery behavior;
- registration collisions and namespaces;
- schema fingerprint changes;
- required and undeclared parameters;
- invalid input values;
- invalid raw output values;
- stale invoker bindings;
- stale plans after tool-level origin/transport changes;
- ordinary metadata changes not altering execution semantics;
- credential separation;
- mutation/destructive policy;
- selected-field propagation when the protocol supports server-side projection;
- transport-specific origin/redirect behavior where relevant.


## Canonical result paths

When a provider's response key differs from the local semantic field name, keep the local field
identity stable and separate the provider source path from the downstream result path:

```python
FieldSpec(
    name="elastic_modulus",
    semantic_id="elastic_modulus",
    path=["_provider_specific_elasticity"],
    result_path=["elastic_modulus"],
)
```

`path` describes where SchemaRouter reads the value from the validated provider response.
`result_path` describes where the projected value is written in `ToolResult.data`. If
`result_path` is omitted, existing behavior is preserved and the source projection path is also
used as the output shape.

This lets multiple provider/access contracts expose different wire schemas while keeping the
downstream context provider-neutral.


## Scientific datatype and unit contracts

Adapters that expose scientific quantities should preserve both the raw value schema and the exact
provider source unit whenever the source contract makes them known.

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

`FieldSpec.unit` is the provider/source unit. `unit_normalization` is optional and must only be
populated when trusted local code has an exact affine conversion contract:

```text
canonical_value = source_value * scale + offset
```

SchemaRouter never infers a conversion factor from a unit label, SI prefix, spelling, or model
output. Unit symbols remain case- and punctuation-sensitive. A remote label such as `nm`, `GPa`,
or `degC` is descriptive until a trusted adapter/application declares the conversion.

The built-in OpenAPI and MCP adapters preserve recognized schema annotations
`x-ucum-unit`, `x-unit`, and `unit` as the source-unit label. They do **not** create a
`UnitNormalizationSpec` from those strings. OPTIMADE continues to preserve provider-declared
units through its schema adapter.

Unit normalization requires a numeric scalar or recursively numeric-array schema, supplied either
by `FieldSpec.json_schema` or by the endpoint raw `output_schema`. If both field-level and raw
endpoint schemas describe the value, their datatype shapes must be compatible. Field-level schemas
are enforced at execution time, so a loose provider response schema cannot bypass a stronger local
field contract.

For automatic cross-provider fallback, unit-bearing fields require an explicit datatype contract on
both routes. Unknown datatype + known unit is insufficient evidence for automatic substitution.
Fallback requires semantic compatibility plus compatible result datatype and either:

- the same exact source unit; or
- explicit matching physical `dimension` and `canonical_unit` normalization contracts.

Units are optional. Text/document/search fields normally use `unit=None`; no unit metadata is required for strings such as
abstracts, snippets, titles, or prose.


### When to omit units

Do **not** attach a unit merely because a field comes from a scientific source. The unit belongs to
the value contract, not to the provider category.

Typical unitless fields include:

- paper titles, abstracts, and full text;
- web-search snippets and URLs;
- material names and identifiers;
- categorical labels, symmetry symbols, and free-form notes;
- provenance/license/source strings.

For example:

```python
FieldSpec(
    name="abstract",
    semantic_id="document_text",
    json_schema={"type": "string"},
    unit=None,  # optional; this is also the default
)
```

A unit should be declared only when the field represents a physical/numeric quantity and the source
contract actually defines that unit. If the unit is unknown, leave it unset rather than guessing.


### Dynamic per-record units

The current field contract assumes one declared source unit for a `FieldSpec`. If a provider can
return different unit labels for the same field on different records, do not let SchemaRouter infer
conversion behavior from those runtime strings.

Prefer one of these approaches:

- normalize the provider response inside a trusted adapter into one stable source/canonical unit
  before it reaches SchemaRouter; or
- expose separate locally declared field/access contracts whose unit semantics are stable.

For example, a payload shaped like:

```json
{"value": 130, "unit": "GPa"}
```

must not be converted merely because the runtime string says `GPa`. The conversion relationship
remains trusted local configuration. Until an explicit dynamic-unit contract exists, row-dependent
unit interpretation should remain outside the generic SchemaRouter execution core.


### Dimensionless numeric quantities

Numeric scientific data can also be unitless. Do not invent a unit for dimensionless quantities
such as a Poisson ratio, probability, normalized score, or other dimensionless coefficient.

```python
FieldSpec(
    name="poisson_ratio",
    semantic_id="poisson_ratio",
    json_schema={"type": "number"},
    unit=None,
)
```

This remains a typed numeric contract even though the unit is absent. Cross-provider fallback may
match another compatible unitless numeric field, but it will not silently substitute a unit-bearing
quantity for a unitless one (or vice versa).


## Trusted parameter aliases

Different provider/access contracts can accept the same logical input under different local
parameter names. Use `ParameterSpec.aliases` only for trusted key equivalence:

```python
ParameterSpec(
    name="chemical_formula",
    aliases=["formula"],
    required=True,
)
```

A request argument `{"formula": "Si"}` may then compile to
`{"chemical_formula": "Si"}` for that endpoint.

Alias routing is deliberately narrow:

- exact parameter names always win;
- aliases only rename keys and copy values unchanged;
- if one supplied alias can target multiple parameters, SchemaRouter does not guess;
- if multiple supplied aliases compete for one parameter, SchemaRouter does not guess;
- fallback candidates compile arguments independently against their own parameter contracts.

`aliases` are not a value transformation language. For example, this is valid:

```text
formula="Si" -> chemical_formula="Si"
```

but SchemaRouter does not generically synthesize:

```text
formula="Si" -> filter='chemical_formula_reduced="Si"'
```

Protocol expressions, coercions, and provider-specific query-language construction belong in
trusted adapter/application code. `wire_name` remains the serialization boundary for a declared
parameter and is distinct from semantic aliases.

Adapters must not infer trusted aliases from arbitrary remote descriptions or model output. Remote
schemas may describe names, but local code decides whether two argument keys are semantically
equivalent.


## Scientific qualifiers are exact local contracts

When a provider field has a fixed contextual meaning that affects scientific comparability, adapters
may preserve that context with `FieldSpec.qualifiers`.

```python
FieldSpec(
    name="youngs_modulus",
    semantic_id="elastic_modulus",
    json_schema={"type": "number"},
    unit="GPa",
    qualifiers={
        "temperature": "300 K",
        "orientation": "[100]",
    },
)
```

Only declare qualifiers that are fixed and trusted for the field contract. Do not copy arbitrary
per-record metadata into this map. If a condition varies per record, keep it as an ordinary returned
field or normalize the provider data in trusted application/adapter code first.

Qualifier keys and values must be non-empty and have no surrounding whitespace. Their values are
exact opaque tags; SchemaRouter does not perform unit conversion, synonym expansion, or natural
language inference inside qualifier strings.

This makes qualifiers suitable for conservative fallback safety without turning SchemaRouter into a
scientific ontology or query-language engine.

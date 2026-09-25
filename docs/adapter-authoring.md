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


## Canonical input names

When two access paths accept the same value under different parameter names, declare the local
equivalence explicitly:

```python
ParameterSpec(
    name="chemical_formula",
    aliases=["formula"],
)
```

Planning may then copy the unchanged value from a supplied `formula` argument into the endpoint's
`chemical_formula` argument. Alias resolution is exact/local and fails closed when more than one
parameter claims the same alias.

Do not use aliases to imply a value transformation. For example, converting a formula value into an
OPTIMADE filter expression is protocol/domain logic and should live in trusted adapter code behind a
canonical local parameter contract.

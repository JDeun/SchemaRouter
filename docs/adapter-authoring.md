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

## Adapter responsibilities

A schema adapter should return:

- a `ToolSpec`;
- one or more `EndpointSpec` objects;
- declared `ParameterSpec` objects;
- declared `FieldSpec` objects when fields are projectable;
- input/output JSON Schema where the source provides it;
- descriptive metadata marked as untrusted when it originates remotely.

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

Remote adapters should set `tool.metadata["remote"] = True` so unclassified side effects remain
policy-gated.

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
- credential separation;
- mutation/destructive policy;
- selected-field propagation when the protocol supports server-side projection;
- transport-specific origin/redirect behavior where relevant.

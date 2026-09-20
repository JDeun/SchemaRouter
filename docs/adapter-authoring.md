# Adapter authoring

Adapters connect an external capability source to SchemaRouter without changing the core planner or
trust model.

## Adapter responsibilities

A schema adapter should return:

- a `ToolSpec`;
- one or more `EndpointSpec` objects;
- declared `ParameterSpec` objects;
- declared `FieldSpec` objects when fields are projectable;
- input/output JSON Schema where the source provides it;
- descriptive metadata marked as untrusted when it originates remotely.

A transport adapter should provide an invoker compatible with:

```python
invoker(endpoint_name: str, arguments: dict[str, Any]) -> Any | Awaitable[Any]
```

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

The registry must provide a monotonic version and current tool/endpoint lookup semantics. Persistent
implementations are responsible for concurrency control and atomic replacement.

## Conformance expectations

New adapters should test:

- registration collisions and namespaces;
- schema fingerprint changes;
- required and undeclared parameters;
- invalid input values;
- invalid raw output values;
- stale invoker bindings;
- credential separation;
- mutation/destructive policy;
- transport-specific origin/redirect behavior where relevant.

# Registry and schema identity

The registry is the authoritative catalog used by the planner and executor.

## Namespaces

Tool keys are collision-safe:

```python
ToolSpec(name="search", namespace="materials", endpoints=[...])
```

becomes:

```text
materials.search
```

## Versioning

Every registry mutation advances a monotonic version. Plans record the registry version they were
compiled against, while each call records the endpoint fingerprint that matters for execution.

## Snapshot semantics

`InMemoryRegistry` stores detached deep copies and returns detached snapshots.

This prevents a caller from mutating a previously registered `ToolSpec` object and silently changing
the execution contract without a versioned registry write.

```python
tool = registry.get("weather")
tool.metadata["local_change"] = True

# A fresh registry read is unchanged.
assert "local_change" not in registry.get("weather").metadata
```

Custom `ToolRegistry` implementations must provide the same semantic guarantee, either through
detached snapshots or immutable values.

## Schema fingerprints

Fingerprinting covers executable schema structure rather than descriptive metadata.

A plan compiled against an older endpoint fingerprint fails closed:

```text
plan fingerprint != current endpoint fingerprint
 -> SchemaDriftError
```

Invoker bindings also carry the tool fingerprint that existed at bind time. Replacing a tool
contract without rebinding its transport yields `BindingDriftError`.

## Custom registries

Applications can inject a structural registry implementation:

```python
router = SchemaRouter(registry=MyPersistentRegistry(...))
```

Persistent implementations are responsible for atomic writes and concurrency control.

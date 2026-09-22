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

## Persistent SQLite registry

SchemaRouter includes a dependency-free persistent implementation backed by Python's standard
`sqlite3` module:

```python
from schemarouter import SQLiteRegistry, SchemaRouter

registry = SQLiteRegistry("schemarouter.sqlite3")
router = SchemaRouter(registry=registry)
```

`SQLiteRegistry` preserves tool order and the monotonic registry version across process restarts.
Single-tool writes, replacement, deletion, and `update_many()` batches are transactional. A failed
collision or invalid batch is rolled back without advancing the version.

Tool specifications are stored as validated Pydantic JSON rather than pickle. Reopening the database
therefore does not import or execute arbitrary Python objects. Corrupt or key-mismatched stored rows
fail closed with `RegistrationError`.

The persistent registry stores **schema/catalog state only**. Trusted invokers, HTTP clients,
credentials, approval callbacks, and execution policy are intentionally not serialized. After a
process restart, the application must re-establish the trusted execution bindings:

```python
registry = SQLiteRegistry("schemarouter.sqlite3")
router = SchemaRouter(registry=registry)
router.executor.bind("weather", trusted_weather_invoker)
```

Call `registry.close()` when its lifecycle is not managed by a context manager.

## Custom registries

Applications can still inject any structural registry implementation:

```python
router = SchemaRouter(registry=MyPersistentRegistry(...))
```

Custom persistent implementations are responsible for atomic writes, snapshot semantics, and
concurrency control.

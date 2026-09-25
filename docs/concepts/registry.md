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
compiled against, while each planned call records both the endpoint fingerprint and the current
tool fingerprint. The second fingerprint pins tool-level execution-origin and transport identity
that cannot be represented by the endpoint contract alone.

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

The built-in registries also revalidate the complete `ToolSpec` at every write boundary. This is
necessary because nested Pydantic collections can be mutated after initial model construction
without triggering assignment validation. A tool whose endpoint/parameter/field collections were
made invalid after construction is rejected atomically rather than snapshotted or persisted.

## Schema fingerprints

Fingerprinting excludes arbitrary descriptive `metadata`, but it intentionally includes the
declared planner/execution contract: endpoint descriptions, aliases, parameters, fields,
side-effect classification, evidence metadata, JSON Schemas, `ToolSpec.remote`, and explicit
`execution_metadata`.

`execution_metadata` is reserved for trusted adapter/runtime values that can change what gets
executed, such as an approved OpenAPI base URL, the actual MCP/OPTIMADE runtime target,
request-body mode, or built-in callable identity. Schema-document provenance such as an OpenAPI
source URL remains descriptive metadata unless that URL is itself the invocation target. Custom
adapters must put execution-affecting values in `execution_metadata` rather than reading them from
ordinary `metadata` at invocation time. Ordinary `metadata` remains descriptive/observability
data and must not grant authority or alter transport semantics.

A plan compiled against an older endpoint or tool execution contract fails closed:

```text
endpoint fingerprint != current endpoint fingerprint
 OR
tool fingerprint != current tool fingerprint
 -> SchemaDriftError
```

Invoker bindings also carry the tool fingerprint that existed at bind time. Replacing a tool
contract without rebinding its transport yields `BindingDriftError`.

For operational diagnosis, `compare_endpoint_specs()` and `compare_tool_specs()` explain why two
trusted snapshots differ and classify the change conservatively. A compatible report never bypasses
the fingerprint gate; callers still replan/rebind against the current contract. See
[Schema drift analysis](../guides/schema-drift.md).

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

Custom persistent implementations are responsible for atomic writes, snapshot semantics,
write-time contract revalidation, and concurrency control.

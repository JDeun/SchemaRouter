# Observability

SchemaRouter exposes a local, privacy-safe observation surface for capability catalogs, execution
bindings, OpenAPI compatibility, and persisted run traces.

The goal is operational inspection, not remote telemetry. SchemaRouter does not send these
observations anywhere by itself.

## Live router snapshot

A running `SchemaRouter` instance can report its current registry, planner, decision backend,
execution policy, and trusted invoker bindings:

```python
router = SchemaRouter()
# ... register/import tools ...

snapshot = router.observe()
print(snapshot.model_dump_json(indent=2))
```

The live snapshot includes actual executor binding keys, so it can distinguish a schema that is
registered from one that is currently bound to a trusted invoker.

Arbitrary tool metadata values and invoker objects are deliberately omitted.

## Inspect a persistent registry

For a `SQLiteRegistry` database:

```bash
schemarouter inspect registry --db .schemarouter/registry.db
```

Machine-readable form:

```bash
schemarouter inspect registry \
  --db .schemarouter/registry.db \
  --json
```

The report includes:

- registry version;
- tools and endpoints;
- adapter/source classification;
- method and path;
- read-only, mutating, destructive, and unclassified side-effect status;
- required parameter names;
- output field names;
- schema fingerprints;
- execution-bound metadata when the persisted schema records it.

A persistent registry cannot prove a live in-process Python invoker binding. Use
`SchemaRouter.observe()` when live binding state matters.

## Inspect run traces

For a `SQLiteRunTraceStore`:

```bash
schemarouter inspect traces --db .schemarouter/traces.db
```

Filter complete or incomplete runs:

```bash
schemarouter inspect traces --db .schemarouter/traces.db --complete yes
schemarouter inspect traces --db .schemarouter/traces.db --complete no
```

Inspect one run:

```bash
schemarouter inspect traces \
  --db .schemarouter/traces.db \
  --run-id <RUN_ID>
```

The default observation surface summarizes event counts, time bounds, terminal state, tool/endpoint
names, and error types. It does **not** render raw trace payload values, even if the original run
used `include_payloads=True`.

## Inspect OpenAPI compatibility

Before importing a local OpenAPI JSON/YAML document:

```bash
schemarouter inspect openapi openapi.yaml
```

Machine-readable form:

```bash
schemarouter inspect openapi openapi.yaml --json
```

This uses the same compatibility analyzer as SchemaRouter's OpenAPI tooling and reports supported,
partial, and unsupported constructs without executing an API call.

## Export a dashboard

Create a self-contained HTML file from persistent registry and trace databases:

```bash
schemarouter dashboard \
  --registry .schemarouter/registry.db \
  --traces .schemarouter/traces.db \
  --output artifacts/schemarouter-dashboard.html
```

The dashboard contains:

- registry/tool/endpoint counts;
- adapter distribution;
- side-effect classification;
- capability table with search/filter;
- execution-bound status available from persisted metadata;
- privacy-safe run summaries and error types.

The output has no server dependency, external JavaScript, analytics, or network calls. It can be
opened directly in a browser or archived with benchmark/release evidence.

## Privacy boundary

The default observation contract intentionally excludes:

- arbitrary `ToolSpec.metadata` values;
- trusted invoker objects;
- credentials and headers;
- request argument values;
- result payload values;
- trace payload values and exception messages.

This means the observability surface is useful for topology and operational state without silently
turning the registry or trace store into a secret-dumping interface.

If an application needs richer inspection, build it on the typed observation models and add an
explicit application-owned disclosure policy rather than weakening the core defaults.

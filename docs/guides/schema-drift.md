# Schema drift and compatibility

SchemaRouter rejects stale plans and stale invoker bindings by exact fingerprint. Compatibility
analysis is diagnostic only: it explains why two trusted schema snapshots differ, but it never
permits an old plan to execute against a new contract.

## Compare endpoint snapshots

```python
from schemarouter import compare_endpoint_specs

report = compare_endpoint_specs(previous_endpoint, current_endpoint)

print(report.compatibility)
for change in report.changes:
    print(change.severity, change.path, change.kind)
```

Compatibility values are:

- `identical` — the compared executable contracts have the same fingerprint;
- `compatible` — only changes that SchemaRouter can conservatively prove additive/widening were
  found;
- `breaking` — at least one contract change can invalidate callers or projections;
- `security_review` — side-effect or destructive semantics changed and local authority must be
  reviewed.

The implementation is conservative. Arbitrary JSON Schema compatibility is difficult
to prove, so unknown schema changes are classified as breaking instead of guessed safe.

## Compare complete tools

```python
from schemarouter import compare_tool_specs

report = compare_tool_specs(previous_tool, current_tool)
```

Tool comparison includes endpoint additions/removals, endpoint contract changes, evidence metadata
such as source type/license, and ordering changes that can explain a fingerprint change.

## CLI inspection across persisted registries

When old and current registry snapshots are available as SQLite registries, compare them without
executing any tool:

```bash
schemarouter inspect diff materials \
  --old-db registry-before.sqlite3 \
  --new-db registry-current.sqlite3
```

Compare one endpoint or emit machine-readable JSON:

```bash
schemarouter inspect diff materials \
  --endpoint search \
  --old-db registry-before.sqlite3 \
  --new-db registry-current.sqlite3 \
  --json
```

The CLI loads validated `ToolSpec` snapshots and runs the same conservative comparison functions
used by the Python API. It does not register, bind, or invoke tools. The underlying SQLite registry
connection uses the normal registry implementation, so this is an execution-safe inspection path
rather than a claim of filesystem-level read-only access.

## Reinspect a registered provider

For URL-backed OpenAPI, MCP, OPTIMADE, GraphQL, OData, and OpenRPC tools, SchemaRouter can
reinspect the provider without committing the candidate first:

```python
result = await router.arefresh_schema("materials")

print(result.action)
print(result.report.compatibility)
```

The one-shot refresh path is conservative:

- `identical` -> no registry write;
- `compatible` -> applied atomically by default;
- `breaking` / `security_review` -> reported as `pending_review` and left unapplied.

Use `apply_compatible=False` to make even compatible changes report-only.

```python
result = await router.arefresh_schema(
    "materials",
    apply_compatible=False,
)
```

Schema and runtime authentication material is intentionally not persisted. If the provider requires
headers, pass trusted `schema_headers` / `trusted_headers` again during refresh.

The apply step uses the exact registry version and tool fingerprint that were compared. If another
writer mutates the registry while remote inspection is in progress, the compare-and-swap fails
instead of applying a candidate against an unseen newer snapshot.

## Periodic provider-schema watcher

The one-shot primitive can be scheduled per tool without persisting credentials into the registry:

```python
router.register_schema_watch(
    "materials",
    interval_seconds=300,
    apply_compatible=True,
    refresh_timeout_seconds=20,
    schema_headers={"X-Schema-Key": schema_key},
    trusted_headers={"Authorization": f"Bearer {runtime_token}"},
)

await router.start_schema_watcher(max_concurrency=4)
```

Each watched tool has its own interval and compatible-change policy. A watcher cycle calls the same
`arefresh_schema()` path, so the exact same conservative diff and compare-and-swap boundary
applies:

```text
identical        -> no-op
compatible       -> atomic apply only when apply_compatible=True
breaking         -> pending_review, registry unchanged
security_review  -> pending_review, registry unchanged
error / timeout  -> recorded in watcher snapshot, loop continues
```

Run all registered watches once on demand:

```python
snapshots = await router.check_schema_watches_once()
```

Inspect them without exposing secrets:

```python
for snapshot in router.schema_watch_snapshots():
    print(
        snapshot.tool_key,
        snapshot.status,
        snapshot.last_compatibility,
        snapshot.last_error_type,
    )

live = router.inspect()
print(live.execution.schema_watcher_running)
print(live.execution.schema_watches)
```

Stop background refresh cleanly:

```python
await router.stop_schema_watcher()
```

Schema headers, runtime headers, and MCP client factories live only in trusted watcher state. Public
snapshots and `router.inspect()` contain only operational status.

The watcher bounds total refresh time per tool and global concurrency. Concurrent cycles skip a
tool that is already being refreshed instead of launching duplicate writes.

Conditional HTTP requests with `ETag` / `Last-Modified` remain an optional transport
optimization. Correctness does not depend on conditional fetch: every fetched candidate is still
fingerprinted, semantically compared, and committed through compare-and-swap.

## Security-semantic drift

Changes such as:

```text
GET -> POST / PUT / PATCH / DELETE
read_only: True -> False
destructive: False -> True
```

produce `security_review`, not ordinary compatibility. Remote descriptions never authorize that
transition; the application must re-import/review/rebind under trusted local policy.

## Important: compatible does not mean executable

This is still invalid:

```text
old plan fingerprint
        !=
current endpoint fingerprint
        -> SchemaDriftError
```

Even when `compare_endpoint_specs(...).compatibility == "compatible"`, the old plan must be
replanned and stale bindings must be rebound. The report is for review, migration tooling,
observability, and CI—not for bypassing execution checks.

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

## HTTP validator optimization

GET-backed schema sources can reuse authoritative HTTP validators during refresh. SchemaRouter
stores only privacy-safe validator values and never stores authentication headers:

- `ETag` -> `If-None-Match`;
- `Last-Modified` -> `If-Modified-Since`;
- `304 Not Modified` -> immediate `unchanged` refresh result without a registry write.

Validator metadata is excluded from canonical tool fingerprints. Updated validators can also live in
the router's trusted loader cache, so an unchanged schema does not need a registry-version bump just
to remember a new ETag.

Correctness never depends on HTTP validators. If a provider does not supply one, ignores it, or
returns a new document, SchemaRouter falls back to the existing full fetch, fingerprint comparison,
compatibility classification, and compare-and-swap apply path.

The optimization is deliberately limited to schema surfaces where one conditional GET can prove
that the complete inspected document is unchanged:

| Source | Conditional refresh |
| --- | --- |
| OpenAPI without external refs | ETag / Last-Modified |
| OpenRPC document | ETag / Last-Modified |
| OData `$metadata` | ETag / Last-Modified |
| OpenAPI with external refs | full fetch; root validator alone is insufficient |
| OPTIMADE | full multi-resource fetch; `/info` alone is insufficient |
| GraphQL introspection | full introspection POST; HTTP 304 is not used |
| MCP | transport-specific refresh; no HTTP-validator assumption |

`If-None-Match` and `If-Modified-Since` are reserved for SchemaRouter's accepted-schema
validator state during refresh. Caller-supplied values for those two headers are stripped before the
conditional request is built; unrelated trusted schema headers are preserved. This prevents an
arbitrary external condition from producing a 304 that is unrelated to the currently registered
schema snapshot.

## Reinspect a registered provider

For URL-backed OpenAPI, MCP, OPTIMADE, GraphQL, OData, and OpenRPC tools, SchemaRouter can
reinspect the provider without committing the candidate first. MCP tools registered through
`add_mcp_stdio()` or `add_mcp_client_factory()` are also refreshable while their exact
process-local trusted binding remains current:

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

Schema and runtime authentication material is intentionally not persisted. If a URL-backed provider
requires headers, pass trusted `schema_headers` / `trusted_headers` again during refresh. For
stdio and transport-neutral MCP registrations, refresh reuses only the current fingerprint-matched
process-local `MCPBoundInvoker` factory; the factory, credentials, subprocess configuration, and
transport state are never copied into `ToolSpec` or watcher snapshots. If that trusted binding is
missing or stale, refresh fails closed instead of fabricating source provenance.

The apply step uses the exact registry version and tool fingerprint that were compared. If another
writer mutates the registry while remote inspection is in progress, the compare-and-swap fails
instead of applying a candidate against an unseen newer snapshot.

## Native database schema refresh

Caller-owned relational, vector, graph, and record-store backends registered through the native
onboarding APIs keep a process-local re-introspection callback. The backend client, credentials,
connection pool, and other transport state are never persisted in ToolSpec metadata.

```python
result = await router.arefresh_native_schema("warehouse.orders")
```

The same conservative policy applies: identical contracts are unchanged, proven-compatible drift
can be applied and rebound atomically, and breaking drift is quarantined as `pending_review` while
the current executable contract remains active. Explicit acceptance is available through
`aaccept_native_schema_pending(...)`.

For long-lived processes, the native watcher can periodically re-introspect all currently bound
native sources:

```python
await router.start_native_schema_watcher(interval_seconds=300)
# ...
await router.stop_native_schema_watcher()
```

A one-shot sweep is also available as `check_native_schema_watches_once()`. These watchers are
process-local by design; restarting the process requires onboarding the caller-owned backend again.

## Periodic schema watcher

Register a refresh policy per remote tool and start the optional watcher:

```python
router.register_schema_watch(
    "materials",
    interval_seconds=300,
    apply_compatible=True,
    schema_headers={"Authorization": f"Bearer {schema_token}"},
    trusted_headers={"Authorization": f"Bearer {runtime_token}"},
)

await router.start_schema_watcher(max_concurrency=4)
```

Each due check reuses the one-shot refresh boundary above. The watcher never bypasses
`compare_tool_specs()`, fingerprint checks, or compare-and-swap replacement.

The default policy is:

- identical -> record `unchanged`;
- proven-compatible -> atomically apply when `apply_compatible=True`;
- compatible with `apply_compatible=False` -> `report_only`;
- breaking/security drift -> keep the current registry contract and record `pending_review`;
- transport/schema errors -> record `error` and retry on the next interval;
- removed/unrefreshable capability -> record `stale`.

Inspect the live state without exposing credentials:

```python
for watch in router.schema_watch_snapshots():
    print(
        watch.tool,
        watch.status,
        watch.last_compatibility,
        watch.pending_change_count,
    )

pending = router.schema_watch_pending_review("materials")
if pending is not None:
    for change in pending.report.changes:
        print(change.severity, change.path, change.kind)
```

`router.inspect()` also reports watcher state. Header values, client factories, and other trusted
transport state never appear in snapshots.

Run all registered checks once on demand:

```python
await router.check_schema_watches_once()
```

Stop the background task cleanly:

```python
await router.stop_schema_watcher()
```

Intervals are per tool. The watcher serializes overlapping watch cycles and bounds refresh
concurrency, so one slow provider does not create unbounded duplicate refresh writes.

Where supported, conditional HTTP requests using `ETag` / `Last-Modified` are an optimization
only; correctness does not depend on them because every fetched candidate is still fingerprinted
and compared before replacement.

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

# Operational inspection

SchemaRouter can persist its registered capability catalog with `SQLiteRegistry` and execution
event streams with `SQLiteRunTraceStore`. The `schemarouter inspect` command exposes those
artifacts without executing any registered tool.

This is the operational answer to questions such as:

- Which APIs/tools are currently registered?
- Which endpoints were constructed from them?
- Which endpoints are read-only, mutating, destructive, or still unclassified?
- What HTTP method/path, parameters, and output fields does SchemaRouter know?
- Which source URL/adapter produced the registered capability?
- Was an OpenAPI execution base URL bound, and were external references resolved?
- What schema fingerprint is currently bound to each tool/endpoint?
- Which persisted runs completed, failed, or touched a given endpoint?

## Inspect a registry

```bash
schemarouter inspect registry --db ./schemarouter-registry.sqlite3
```

Example shape:

```text
Registry v3: 2 tools, 5 endpoints (4 read-only, 1 mutating, 0 unclassified)
- materials: 3 endpoints [9e8d12a6b487]
  - search: GET /materials · read-only · 2 params/6 fields [c77ac9d7181a]
- experiments: 2 endpoints [93aaf450ac8c]
  - create: POST /experiments · mutating · 4 params/2 fields [ea179fd5cf2a]
```

The abbreviated fingerprints are display aids. JSON output contains the full SHA-256 fingerprints.

When available, the registry/tool view also exposes an allowlisted ingestion provenance set such as
`adapter`, `source_url`, resolved/approved OpenAPI URLs, OPTIMADE versioned base URL, protocol/API
version, execution-binding state, and external-reference resolution counts. Arbitrary metadata is
not copied into the inspection view.

## Inspect one tool in detail

```bash
schemarouter inspect tool materials --db ./schemarouter-registry.sqlite3
```

This expands endpoint classification, method/path, parameters, required/optional status, output
fields, projection paths, and full fingerprints.

For automation or a future dashboard:

```bash
schemarouter inspect tool materials \
  --db ./schemarouter-registry.sqlite3 \
  --json
```

The JSON form includes the persisted ToolSpec document plus derived tool and endpoint fingerprints.

## Inspect run traces

List all persisted runs:

```bash
schemarouter inspect traces --db ./schemarouter-traces.sqlite3
```

Filter by completion state:

```bash
schemarouter inspect traces --db ./schemarouter-traces.sqlite3 --complete
schemarouter inspect traces --db ./schemarouter-traces.sqlite3 --incomplete
```

Inspect one event stream:

```bash
schemarouter inspect trace <RUN_ID> --db ./schemarouter-traces.sqlite3
```

Use `--json` on any inspection command for machine-readable output.

## What the CLI does not do

Inspection is deliberately separate from execution.

- it does not call a registered API;
- it does not approve proposals;
- it does not bind invokers or credentials;
- it does not change execution policy;
- it refuses a missing DB path rather than creating an empty database;
- trace payload visibility is limited to what the application originally persisted.

If traces were recorded with the default redacted `RunConfig`, inspection cannot recover hidden
arguments or result payloads. If an application persisted traces with
`include_payloads=True`, the resulting SQLite database must be protected accordingly.

## Python inspection API

The same derived views are available without the CLI:

```python
from schemarouter import SQLiteRegistry, inspect_registry

with SQLiteRegistry("registry.sqlite3") as registry:
    snapshot = inspect_registry(registry)

print(snapshot.tool_count)
print(snapshot.endpoint_count)
```

Useful public helpers include `inspect_registry`, `inspect_tool`, `inspect_trace`, and
`inspect_traces`.

## Dashboard direction

The JSON contracts are intentionally stable enough to act as the backend boundary for a later
local dashboard or TUI. A dashboard should consume these inspection models rather than query
SchemaRouter's SQLite tables directly.

That keeps one source of truth for:

```text
SQLiteRegistry / SQLiteRunTraceStore
              |
        inspection API
         /           \
       CLI       dashboard/TUI
```

The first dashboard milestone should remain observational: catalog topology, endpoint
classification, fingerprints, recent runs, errors, and latency/event summaries. Mutation controls,
credential editing, or execution buttons should not be introduced into the same surface by default.

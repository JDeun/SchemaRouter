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

For one registered Python weather tool, the CLI looks like:

```text
Registry v1: 1 tools, 1 endpoints (1 read-only, 0 mutating, 0 unclassified)
- current_weather: 1 endpoints [7c5d43e1f901]
  - current_weather: - - · read-only · 1 params/3 fields [f1d90a4c6b2e]
```

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

## Live router inspection

Persistent SQLite inspection shows what was saved. A running process can additionally report the
actual trusted invoker bindings and planner/policy configuration:

```python
router = SchemaRouter()
# ... register/import capabilities ...

snapshot = router.inspect()
print(snapshot.model_dump_json(indent=2))
```

The live view adds:

- analyzer class;
- configured decision-backend class;
- bounded decision policy;
- execution policy;
- actual bound tool keys from the current executor.

Invoker objects, credentials, arbitrary metadata values, arguments, results, and payload values are
not included.

Representative `router.inspect()` JSON:

```json
{
  "registry": {
    "version": 1,
    "tool_count": 1,
    "endpoint_count": 1,
    "read_only_endpoints": 1,
    "mutating_endpoints": 0,
    "unclassified_endpoints": 0
  },
  "planner": {
    "analyzer": "KeywordAnalyzer",
    "decision_backend": null,
    "decision_policy": {
      "enabled": false,
      "tool_selection": false,
      "endpoint_selection": false,
      "field_selection": false,
      "evidence_sufficiency": false,
      "fallback": "deterministic"
    }
  },
  "execution": {
    "policy": {
      "allow_mutations": false,
      "allow_destructive": false,
      "allow_unclassified_remote": false,
      "approval_mode": "never"
    },
    "bound_tools": ["current_weather"]
  }
}
```

The full registry section also contains the safe tool/endpoint inspection records and fingerprints.

## Export a dashboard

The 0.6 development line can render the same read-only inspection models into one self-contained
HTML file:

```bash
schemarouter dashboard \
  --registry ./schemarouter-registry.sqlite3 \
  --traces ./schemarouter-traces.sqlite3 \
  --output ./artifacts/schemarouter-dashboard.html
```

The trace database is optional:

```bash
schemarouter dashboard \
  --registry ./schemarouter-registry.sqlite3 \
  --output ./artifacts/schemarouter-dashboard.html
```

The dashboard contains capability counts, adapter/source provenance, endpoint method/path and
side-effect classification, schema fingerprints, persisted binding state, recent run summaries, and
error counts. The capability table is filterable in the browser.

It is deliberately a static export:

- no server dependency;
- no external JavaScript;
- no analytics;
- no tool execution buttons;
- no credential editing;
- no raw trace payload rendering.

Applications may also call `render_dashboard(...)` or `write_dashboard(...)` directly with the
typed inspection models.

### What the dashboard looks like

The preview below is a checked-in representative output using the same layout and interaction model
as the generated dashboard. It contains demo data only.

<iframe
  src="../assets/inspection-dashboard-preview.html"
  title="SchemaRouter inspection dashboard preview"
  style="width: 100%; height: 720px; border: 1px solid var(--md-default-fg-color--lightest); border-radius: 12px;"
></iframe>

[Open the dashboard preview in a separate page](../assets/inspection-dashboard-preview.html)

### Run the end-to-end example

The repository includes a runnable example that creates a persistent registry, executes one real
SchemaRouter run into a trace store, prints the live `router.inspect()` snapshot, and writes the
HTML dashboard:

```bash
python examples/inspection_dashboard.py
```

Default outputs:

```text
artifacts/inspection-demo/registry.sqlite3
artifacts/inspection-demo/traces.sqlite3
artifacts/inspection-demo/dashboard.html
```

Override paths when needed:

```bash
python examples/inspection_dashboard.py \
  --registry /tmp/registry.sqlite3 \
  --traces /tmp/traces.sqlite3 \
  --output /tmp/schemarouter-dashboard.html
```

The architecture remains:

```text
SQLiteRegistry / SQLiteRunTraceStore       live SchemaRouter
              |                                  |
        inspection API ------------------- inspect_router()
         /           \
       CLI       static dashboard
```

A future TUI or long-running web console should consume these same inspection contracts instead of
querying SchemaRouter's SQLite tables directly.

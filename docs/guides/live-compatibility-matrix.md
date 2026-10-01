# Live adapter compatibility matrix

SchemaRouter keeps deterministic fixture coverage in mandatory CI and uses a separate
scheduled/manual compatibility workflow for public-provider evidence. Public services are
external dependencies, so an outage is recorded as compatibility evidence rather than
automatically classified as a SchemaRouter regression.

## Matrix

| Adapter | Deterministic local conformance | Scheduled/manual evidence | Safe execution | Evidence source | Known limitation |
| --- | --- | --- | --- | --- | --- |
| OpenAPI | Yes | Live public provider | Read-only metrics request | APIs.guru | Public provider availability is external state. |
| OPTIMADE | Yes | Live public provider | Read-only structure search | COD OPTIMADE | Public provider availability and dataset latency vary. |
| GraphQL | Yes | Live public provider | Read-only country query | Rick and Morty GraphQL API | Public third-party service; introspection availability can change. |
| OData | Yes | Live public provider | Read-only People query with `$top=1` | OData.org V4 reference service | Only a read-only Products query with `$top=1` is exercised. |
| OpenRPC | Yes | Pinned reference implementation | Harmless local echo method | In-repo local JSON-RPC server | No stable unauthenticated public execution endpoint is assumed. |
| MCP Streamable HTTP | Yes | Pinned reference implementation | Local `add` tool | In-repo MCP SDK fixture server | Reference server is used instead of assuming a stable public MCP endpoint. |

The compatibility workflow records a timestamp, SchemaRouter version, source, discovery and
execution success, endpoint count, binding state, returned-data shape, latency, auth state, and
provider-specific notes in machine-readable JSON.

## Running the matrix

The GitHub Actions **Compatibility Smoke** workflow runs weekly and can also be dispatched
manually. The `adapter-compatibility-matrix` job produces:

- one `*-compatibility.json` report per adapter;
- `adapter-compatibility-matrix.json`;
- `adapter-compatibility-matrix.md`;
- the same Markdown table in the workflow step summary.

Public-provider jobs are intentionally non-blocking. Pinned-reference failures are treated
differently by the aggregator because they represent locally controlled compatibility evidence.

Individual smokes can also be run locally:

```bash
python scripts/live_graphql_smoke.py --json-out /tmp/graphql-compatibility.json
python scripts/live_odata_smoke.py --json-out /tmp/odata-compatibility.json
python scripts/live_reference_openrpc_smoke.py --json-out /tmp/openrpc-compatibility.json
python scripts/live_reference_mcp_smoke.py --json-out /tmp/mcp-compatibility.json
```

MCP reference evidence requires the optional MCP dependency:

```bash
pip install ".[mcp]"
```

## Evidence interpretation

A green public-provider row means the provider was reachable and compatible at the report's
`generated_at` timestamp. It is not a permanent availability guarantee. A public-provider
failure should first be classified as provider/network/infrastructure state.

Pinned OpenRPC and MCP rows are reproducible compatibility evidence owned by this repository.
A failure there is actionable as a likely SchemaRouter or dependency compatibility regression.

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
| GraphQL | Yes | Live public provider + pinned reference | Read-only media/reference query | AniList + in-repo GraphQL reference | Public introspection may change; pinned reference is release-gated. |
| OData | Yes | Live public provider | Read-only Products query with `$top=1` | OData.org V4 reference service | Only a read-only Products query with `$top=1` is exercised. |
| OpenRPC | Yes | Pinned reference implementation | Harmless local echo method | In-repo local JSON-RPC server | No stable unauthenticated public execution endpoint is assumed. |
| MCP Streamable HTTP | Yes | Pinned reference implementation | Local `add` tool | In-repo MCP SDK fixture server | Reference server is used instead of assuming a stable public MCP endpoint. |
| Provider profile: Materials Project | Yes | Live public provider | Provider identity -> public OPTIMADE -> read-only structure query | Materials Project OPTIMADE | Authenticated OpenAPI/SDK paths remain separately gated. |
| Provider profile: Crossref | Yes | Live public provider | Provider identity -> public REST -> works query | Crossref REST API | Public provider availability is external state. |
| Provider profile: Tavily | Yes | Auth-contract + optional live execution | Provider identity -> auth-required REST; live search when `TAVILY_API_KEY` is configured | Tavily Search API | No secret means explicit auth-required evidence, not fabricated execution success. |
| Provider profile: APIs.guru | Yes | Live public provider | Provider identity -> OpenAPI -> read-only metrics request | APIs.guru | Public provider availability is external state. |
| Provider profile: AniList | Yes | Live public provider | Provider identity -> GraphQL -> read-only media query | AniList | Public third-party service; introspection availability can change. |
| Provider profile: OData V4 reference | Yes | Live public provider | Provider identity -> OData -> read-only Products query | OData.org V4 reference service | Reference-service availability is external state. |

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
python scripts/live_reference_graphql_smoke.py --json-out /tmp/graphql-reference-compatibility.json
python scripts/live_materials_project_provider_smoke.py
python scripts/live_crossref_provider_smoke.py
python scripts/live_tavily_provider_smoke.py
python scripts/live_provider_first_protocol_smoke.py --provider apis-guru
python scripts/live_provider_first_protocol_smoke.py --provider anilist
python scripts/live_provider_first_protocol_smoke.py --provider odata-v4-reference
```

MCP reference evidence requires the optional MCP dependency:

```bash
pip install ".[mcp]"
```

## Evidence interpretation

A green public-provider row means the provider was reachable and compatible at the report's
`generated_at` timestamp. It is not a permanent availability guarantee. A public-provider
failure should first be classified as provider/network/infrastructure state.

Pinned GraphQL, OpenRPC, and MCP rows are reproducible provider-first compatibility evidence owned by this repository: each reference source is registered through a process-local `ProviderProfile` before it reaches the normal protocol adapter.
A failure there is actionable as a likely SchemaRouter or dependency compatibility regression.

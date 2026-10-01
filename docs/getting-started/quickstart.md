# Quickstart

The fastest user-facing path uses a real public provider. Mandatory CI remains offline and
deterministic, so a third-party outage cannot block a release.

## 1. Install SchemaRouter

```bash
pip install schemarouter
```

No API key is required for this example.

## 2. Discover and execute a real OpenAPI capability

The example below uses the same APIs.guru source that SchemaRouter's scheduled compatibility smoke
checks. The provider owns the schema and returned data.

--8<-- "examples/live_openapi_quickstart.py"

Run it from a checkout with:

```bash
python examples/live_openapi_quickstart.py
```

The exact count changes over time. A successful run has this shape:

```text
source: https://api.apis.guru/v2/openapi.yaml
discovered: apis.guru:getMetrics (... endpoints on this tool)
selected: apis.guru:getMetrics
current numAPIs: <current positive integer>
```

Four product boundaries are visible in that short program:

1. `from_url(..., kind="openapi")` inspects an external machine-readable contract;
2. SchemaRouter registers typed tools/endpoints with stable fingerprints;
3. the planner selects one bounded capability from that catalog;
4. execution validates the call and raw response before returning a `ToolResult`.

## 3. Why the live example is not a required CI dependency

Public services can rate-limit, change, or go offline. Required CI therefore validates the same
quickstart path with a deterministic OpenAPI fixture in `tests/test_live_quickstart.py`.

The older local callable example remains deliberately boring and deterministic:

--8<-- "examples/quickstart.py"

That file is executed from source, wheel, and sdist acceptance jobs. It proves packaging and local
execution without pretending that a fixed weather value is real provider data.

## 4. Unsupported ordinary websites fail loudly

SchemaRouter does not silently turn arbitrary HTML into executable tools:

```python
from schemarouter import SchemaRouter, UnsupportedSchemaSourceError


async def inspect_docs_page():
    try:
        await SchemaRouter.from_url(
            "https://example.com/",
            kind="auto",
        )
    except UnsupportedSchemaSourceError:
        print("ordinary HTML was rejected as an executable source")
```

For human-readable API documentation, use the explicit inspect/proposal/approval path instead of
automatic execution authority.

## 5. Use async, batch, or streaming

Once a router is configured, the same request model supports the larger runtime surface:

```python
result = await router.ainvoke(request)

results = await router.abatch([request, request])

async for result in router.astream(request):
    print(result)

async for event in router.astream_events(request):
    print(event.event, event.tool, event.endpoint)
```

Event payloads are redacted by default.

## Time-to-value budget

The promoted path is intentionally bounded:

- **1 install command**: `pip install schemarouter`;
- **1 executable Python snippet** with no credentials;
- **4 concepts before the first useful result**: source URL, discovered capability, selected plan,
  validated result;
- no database, model API, vector store, or agent framework is required.

The live request itself depends on internet/provider latency; the local setup path has no hidden
infrastructure requirement.

## Choose your path

| You already have | Install | Minimal tested path |
| --- | --- | --- |
| OpenAPI URL | `pip install schemarouter` | [live OpenAPI quickstart](#2-discover-and-execute-a-real-openapi-capability) |
| Typed Python function | core install | [Python tools](../guides/python-tools.md) and `examples/quickstart.py` |
| MCP server | `pip install "schemarouter[mcp]"` | [MCP HTTP / stdio guide](../guides/mcp.md) |
| LangChain tools | `pip install "schemarouter[langchain]"` | `examples/langchain_quickstart.py` |
| LangGraph app | `pip install "schemarouter[langgraph]"` | `examples/langgraph_quickstart.py` |
| LlamaIndex tools | `pip install "schemarouter[llamaindex]"` | `examples/llamaindex_quickstart.py` |
| Human-readable API docs only | core install | [inspect → proposal → approval](../guides/html-documentation.md) |

The framework examples are executed in dedicated CI jobs. The OpenAPI live path is checked by the
scheduled compatibility workflow and by an offline contract-equivalent wheel/sdist smoke.

For SDK-bound tools, mixed-provider execution, context-reduction before/after, schema drift/watch, and MCP transport demos, continue to the [examples gallery](examples.md).

## Troubleshooting

**`ModuleNotFoundError` for MCP/LangChain/LlamaIndex**

Install the matching optional extra shown above. The core package intentionally does not pull every
framework into every environment.

**401/403 or provider credentials are required**

Keep credentials in trusted runtime configuration such as `trusted_headers` or an injected client
factory. Do not put secrets into `ToolSpec`, planner arguments, or URLs.

**MCP server cannot connect**

Choose the transport you actually own: Streamable HTTP via `from_url(..., kind="mcp")`, local
stdio via `add_mcp_stdio()`, or a caller-owned client lifecycle via
`add_mcp_client_factory()`.

**Schema discovery fails**

Use `router.probe_url(...)` to get a typed, privacy-safe diagnosis. An ordinary website is rejected
rather than silently producing zero tools.

**Execution is denied even though discovery worked**

Discovery does not grant authority. Check read/write/destructive classification, the execution
policy, required approval callbacks, and whether the current binding fingerprint is ready.

## Next

For deeper protocol details:

- [OpenAPI](../guides/openapi.md)
- [MCP](../guides/mcp.md)
- [GraphQL](../guides/graphql.md)
- [OData](../guides/odata.md)
- [OpenRPC / JSON-RPC](../guides/openrpc.md)
- [OPTIMADE](../guides/optimade.md)
- [Universal ingestion matrix](../guides/universal-ingestion.md)

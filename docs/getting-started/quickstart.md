# Quickstart

The fastest user-facing path uses a real public provider. Mandatory CI remains offline and
deterministic, so a third-party outage cannot block a release.

## 1. Install SchemaRouter

```bash
pip install schemarouter
```

No API key is required for this example.

## 2. Start from a provider name

If the user knows the provider rather than its protocol surface, use provider-first registration:

```python
from schemarouter import SchemaRouter

router = SchemaRouter()
result = await router.add_provider("materials-project")
```

SchemaRouter resolves the provider's known access methods and registers only methods that are usable
in the current environment. The built-in acceptance profiles cover Materials Project, Crossref, Tavily, APIs.guru, and the
OData.org V4 reference service. Missing credentials or optional SDKs are reported explicitly.

[Provider-first registration details →](../guides/provider-first-registration.md)

## 3. Resolve and execute a real provider capability {#live-provider-capability}

The example below starts from the built-in `apis-guru` provider profile. SchemaRouter resolves that
identity to the same public OpenAPI source used by the compatibility smoke, then sends it through the
normal OpenAPI adapter. The provider owns the schema and returned data.

```python
--8<-- "examples/live_openapi_quickstart.py"
```

Run it from a checkout with:

```bash
python examples/live_openapi_quickstart.py
```

The exact count changes over time. A successful run has this shape:

```text
provider: apis-guru
source: https://api.apis.guru/v2/openapi.yaml
discovered: apis.guru:getMetrics (... endpoints on this tool)
selected: apis.guru:getMetrics
current numAPIs: <current positive integer>
```

Four product boundaries are visible in that short program:

1. `add_provider("apis-guru")` resolves a provider profile without requiring the caller to know its protocol URL;
2. the declared OpenAPI method flows through the ordinary OpenAPI adapter and becomes typed tools/endpoints with stable fingerprints;
3. the planner selects one bounded capability from that catalog;
4. execution validates the call and raw response before returning a `ToolResult`.

## 4. Why the live example is not a required CI dependency

Public services can rate-limit, change, or go offline. Required CI therefore validates the same
quickstart path with a deterministic OpenAPI fixture in `tests/test_live_quickstart.py`.

The older local callable example remains deliberately boring and deterministic:

```python
--8<-- "examples/quickstart.py"
```

That file is executed from source, wheel, and sdist acceptance jobs. It proves packaging and local
execution without pretending that a fixed weather value is real provider data.

## 5. Unsupported ordinary websites fail loudly

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

## 6. Use async, batch, or streaming

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
- **4 concepts before the first useful result**: provider name, resolved capability, selected plan,
  validated result;
- no database, model API, vector store, or agent framework is required.

The live request itself depends on internet/provider latency; the local setup path has no hidden
infrastructure requirement. Lower-level `from_url(...)` remains available when the caller already
owns a concrete protocol endpoint.

## Choose your path

| You already have | Install | Minimal tested path |
| --- | --- | --- |
| Provider name | `pip install schemarouter` | `await router.add_provider("materials-project")` and [provider-first registration](../guides/provider-first-registration.md) |
| OpenAPI URL | `pip install schemarouter` | [live OpenAPI quickstart](#live-provider-capability) |
| Typed Python function | core install | [Python tools](../guides/python-tools.md) and `examples/quickstart.py` |
| MCP server | `pip install "schemarouter[mcp]"` | [MCP HTTP / stdio guide](../guides/mcp.md) |
| LangChain tools | `pip install "schemarouter[langchain]"` | `examples/langchain_quickstart.py` |
| LangGraph app | `pip install "schemarouter[langgraph]"` | `examples/langgraph_quickstart.py` |
| LlamaIndex tools | `pip install "schemarouter[llamaindex]"` | `examples/llamaindex_quickstart.py` |
| Human-readable API docs only | core install | [inspect → proposal → approval](../guides/html-documentation.md) |

The framework examples are executed in dedicated CI jobs. The provider-first APIs.guru/OpenAPI path
is checked by the compatibility workflow and by an offline contract-equivalent quickstart smoke.

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

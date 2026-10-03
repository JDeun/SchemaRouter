# Example and demo gallery

Use this page to choose the shortest runnable SchemaRouter path for the stack you already have.
Examples are either **offline deterministic** or explicitly marked as **live/pinned provider**
evidence.

![SchemaRouter field-first, route-second scenario](../assets/real-world-scenario.svg)

## Start from your existing stack

| You have | Example | What it demonstrates |
| --- | --- | --- |
| Provider name | [provider-first guide](../guides/provider-first-registration.md) | provider identity -> safe usable access methods |
| Python function | [typed callable](https://github.com/JDeun/SchemaRouter/blob/main/examples/quickstart.py) | typed local discovery + execution |
| SDK/client object | [SDK-bound demo](https://github.com/JDeun/SchemaRouter/blob/main/examples/sdk_bound_demo.py) | explicit contract around opaque trusted runtime state |
| Many tools | [context reduction](https://github.com/JDeun/SchemaRouter/blob/main/examples/context_reduction_demo.py) | full catalog versus bounded Top-K retrieval |
| Multiple providers | [mixed-provider demo](https://github.com/JDeun/SchemaRouter/blob/main/examples/mixed_provider_demo.py) | complementary semantic-field coverage |
| MCP stdio | [stdio quickstart](https://github.com/JDeun/SchemaRouter/blob/main/examples/mcp_stdio_quickstart.py) | real MCP subprocess discovery and execution |
| MCP Streamable HTTP | [reference smoke](https://github.com/JDeun/SchemaRouter/blob/main/scripts/live_reference_mcp_smoke.py) | real SDK HTTP transport against a pinned server |
| OpenAPI URL | [live OpenAPI quickstart](https://github.com/JDeun/SchemaRouter/blob/main/examples/live_openapi_quickstart.py) | public provider discovery and execution |
| LangChain | [LangChain quickstart](https://github.com/JDeun/SchemaRouter/blob/main/examples/langchain_quickstart.py) | `StructuredTool` bridge |
| LangGraph | [LangGraph quickstart](https://github.com/JDeun/SchemaRouter/blob/main/examples/langgraph_quickstart.py) | SchemaRouter as a graph node |
| LlamaIndex | [LlamaIndex quickstart](https://github.com/JDeun/SchemaRouter/blob/main/examples/llamaindex_quickstart.py) | `FunctionTool` bridge |
| Persisted registry/traces | [inspection dashboard](https://github.com/JDeun/SchemaRouter/blob/main/examples/inspection_dashboard.py) | live inspection + static HTML dashboard |
| Changing provider schema | [schema drift demo](https://github.com/JDeun/SchemaRouter/blob/main/examples/schema_drift_demo.py) | conservative compatibility classification |

The repository-level
[examples README](https://github.com/JDeun/SchemaRouter/tree/main/examples)
contains the exact commands, optional extras, expected-output shapes, and evidence classification.

## Real-provider paths

The user-facing quickstart uses APIs.guru because it is public, read-only, and needs no key:

```bash
python examples/live_openapi_quickstart.py
```

Provider-first acceptance additionally exercises Materials Project, Crossref, and Tavily:

```bash
python scripts/live_materials_project_provider_smoke.py
python scripts/live_crossref_provider_smoke.py
python scripts/live_tavily_provider_smoke.py
```

The Materials Project and Crossref paths execute real read-only provider queries. Tavily validates
the auth contract without a secret and executes a real search when `TAVILY_API_KEY` is configured.

Additional public compatibility examples cover other protocol surfaces:

```bash
python scripts/live_graphql_smoke.py
python scripts/live_odata_smoke.py
```

The GraphQL example uses the Rick and Morty API; the OData example uses the OData.org V4 reference
service. Materials-specific live evidence is available through COD OPTIMADE:

```bash
python scripts/live_optimade_smoke.py
```

Public-provider uptime is external state, so these paths are scheduled/manual compatibility evidence,
not mandatory PR gates.

## Pinned protocol references

When no stable unauthenticated public provider is appropriate, the repository uses a local reference
implementation rather than pretending a fixture is live public evidence.

For MCP stdio:

```bash
pip install "schemarouter[mcp]"
python examples/mcp_stdio_quickstart.py
```

For MCP Streamable HTTP:

```bash
python scripts/live_reference_mcp_smoke.py
```

For OpenRPC / JSON-RPC:

```bash
python scripts/live_reference_openrpc_smoke.py
```

## Before and after: avoid dumping every schema

Run:

```bash
python examples/context_reduction_demo.py
```

The example constructs a 40-tool registry and reports the serialized size of:

- the complete registered tool catalog;
- a bounded Top-3 `CapabilityRetrieval` result.

The bounded payload must be smaller, and the weather route must rank first for a weather query. This
is a product demonstration, not a token benchmark: actual model-token measurements remain in the
research benchmark suite.

## Mixed-provider field-first planning

Run:

```bash
python examples/mixed_provider_demo.py
```

One provider declares `band_gap`; another declares `document_abstract`. The request asks for both
and allows two calls. SchemaRouter compiles the semantic field need first and then selects
complementary executable routes.

That is the same architecture used when one logical answer requires evidence from heterogeneous
providers.

## Schema drift and operational inspection

Run the offline drift classifier:

```bash
python examples/schema_drift_demo.py
```

Then use [schema drift and compatibility](../guides/schema-drift.md) for remote refresh/watch,
pending review, explicit accept/reject, and fingerprint behavior.

For runtime observability:

```bash
python examples/inspection_dashboard.py
```

The example writes a static HTML dashboard from a real registry and trace store. The
[Capability Explorer](schema-explorer.md) provides the protocol-neutral Swagger-style view of
registered capabilities.

## CI and reproducibility

Mandatory CI runs deterministic examples with installed wheel/sdist artifacts. Optional integration
jobs execute framework and MCP examples with the relevant extras. Live public providers stay in the
separate compatibility workflow so external outages do not block a release.

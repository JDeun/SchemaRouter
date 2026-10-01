# SchemaRouter example and demo gallery

This directory is the shortest path from "what is SchemaRouter?" to a runnable scenario.

The examples are deliberately split into two evidence classes:

- **offline deterministic** — safe for required CI and reproducible without external services;
- **live/pinned provider** — proves discovery/execution against a real public provider or a locally
  pinned protocol reference implementation.

SchemaRouter is domain-neutral. The gallery includes finance, weather, generic APIs, enterprise
OData, entertainment GraphQL, materials data, and agent-framework bridges in addition to the
materials-science examples used elsewhere in the project.

![Field-first, route-second overview](../docs/assets/real-world-scenario.svg)

## Choose a scenario

| Scenario | Run | Extra | Evidence |
| --- | --- | --- | --- |
| Typed Python callable | `python examples/quickstart.py` | core | offline deterministic |
| Opaque SDK / client | `python examples/sdk_bound_demo.py` | core | offline deterministic |
| Mixed-provider field coverage | `python examples/mixed_provider_demo.py` | core | offline deterministic |
| Full catalog vs bounded Top-K | `python examples/context_reduction_demo.py` | core | offline deterministic |
| Schema drift comparison | `python examples/schema_drift_demo.py` | core | offline deterministic |
| Inspection + HTML dashboard | `python examples/inspection_dashboard.py` | core | offline deterministic |
| Third-party SourceAdapter plugin | `python examples/adapter_plugin_quickstart.py` | install local demo package | offline deterministic |
| LangChain bridge | `python examples/langchain_quickstart.py` | `langchain` | offline deterministic |
| LangGraph node | `python examples/langgraph_quickstart.py` | `langgraph` | offline deterministic |
| LlamaIndex bridge | `python examples/llamaindex_quickstart.py` | `llamaindex` | offline deterministic |
| MCP stdio subprocess | `python examples/mcp_stdio_quickstart.py` | `mcp` | pinned local MCP server |
| OpenAPI public provider | `python examples/live_openapi_quickstart.py` | core | live APIs.guru |
| OPTIMADE public provider | `python scripts/live_optimade_smoke.py` | core | live COD OPTIMADE |
| GraphQL public provider | `python scripts/live_graphql_smoke.py` | core | live Rick and Morty API |
| OData public provider | `python scripts/live_odata_smoke.py` | core | live OData.org V4 |
| OpenRPC / JSON-RPC | `python scripts/live_reference_openrpc_smoke.py` | core | pinned local reference |
| MCP Streamable HTTP | `python scripts/live_reference_mcp_smoke.py` | `mcp` | pinned local MCP server |

Install an extra with, for example:

```bash
pip install "schemarouter[mcp]"
```

The live compatibility scripts accept `--json-out <path>` when machine-readable evidence is
needed.

## Why bounded capability retrieval helps

`context_reduction_demo.py` creates a 40-tool catalog, then compares two payloads:

1. serializing every registered tool schema for an agent;
2. asking SchemaRouter for a bounded Top-3 capability shortlist.

Run:

```bash
python examples/context_reduction_demo.py
```

Output has this shape:

```text
full catalog: 40 tools / <larger byte count> bytes
SchemaRouter shortlist: 3 capabilities / <smaller byte count> bytes
routes: ['weather_lookup.lookup', ...]
```

The demo intentionally reports bytes rather than pretending bytes are model tokens. Research
benchmarks measure actual tool-schema tokens separately. The product point is the bounded contract:
an orchestrator can expose only the retrieved candidates instead of dumping every schema into model
context.

## SDK-bound capability

`sdk_bound_demo.py` shows the safe path for a client library whose runtime object should not be
reflected or exposed to a model:

```text
trusted SDK/client
    |
explicit ToolSpec
    |
SchemaRouter validation / planning / policy
    |
trusted invoker
```

Expected output:

```text
{'symbol': 'AAPL', 'price': 123.45}
```

The SDK object remains trusted local state. Only the explicit `ToolSpec` becomes model-visible.

## Mixed-provider field coverage

`mixed_provider_demo.py` registers one provider for `band_gap` and another for a paper
`abstract`. A single request asks for both fields with `max_calls=2`.

The planner selects complementary providers because neither route alone covers the requested
semantic field set. This is the small deterministic version of the field-first / route-second
architecture.

## Third-party SourceAdapter plugin

The plugin example is a separate installable package rather than an in-tree import trick:

```bash
python -m pip install -e examples/adapter_plugin_demo
python examples/adapter_plugin_quickstart.py
```

It demonstrates metadata-only discovery, explicit allowlisted loading, a normal typed
`ToolSpec`, and deterministic execution without network access or credentials. Discovery does not
import the plugin module; import occurs only when the application explicitly loads
`demo_static`.

See the [adapter plugin guide](../docs/guides/adapter-plugins.md).

## MCP: HTTP and stdio are both covered

For local stdio:

```bash
pip install "schemarouter[mcp]"
python examples/mcp_stdio_quickstart.py
```

Expected output:

```text
{'result': 5}
```

For Streamable HTTP, the repository uses the official MCP SDK fixture server and runs the complete
discovery -> planning -> execution path:

```bash
python scripts/live_reference_mcp_smoke.py
```

A stable public unauthenticated MCP server is not assumed. The HTTP example is therefore a pinned
reference implementation rather than mislabeled public-provider evidence.

## Schema drift and watch lifecycle

Start with the deterministic compatibility report:

```bash
python examples/schema_drift_demo.py
```

It adds an optional output field and verifies that the candidate is classified as compatible.
For remote providers, continue with the
[schema drift/watch guide](../docs/guides/schema-drift.md), which covers one-shot refresh, periodic
watching, pending review, accept/reject lifecycle, conditional HTTP validators, and fail-closed
fingerprint behavior.

## Live public providers

Live examples are intentionally not release-blocking CI dependencies. They can rate-limit, change,
or go offline.

The scheduled/manual compatibility workflow records timestamped evidence for:

- APIs.guru OpenAPI;
- COD OPTIMADE;
- Rick and Morty GraphQL;
- OData.org V4;
- pinned OpenRPC;
- pinned MCP Streamable HTTP.

See the [live compatibility matrix](../docs/guides/live-compatibility-matrix.md).

## CI contract

Required CI executes the deterministic examples from the installed package. Framework-specific jobs
run the LangChain, LangGraph, LlamaIndex, and MCP examples with their optional dependencies.

This keeps the gallery executable without making third-party network uptime a release gate.

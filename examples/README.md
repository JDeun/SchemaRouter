# SchemaRouter examples

This directory is the shortest path from "what is SchemaRouter?" to a runnable scenario.

The examples deliberately separate **offline deterministic demos**, **live public providers**, and
**pinned local protocol references**. A public service outage is useful compatibility evidence, but
it must not make mandatory package CI flaky.

## Start here

| Scenario | Run | Mode | Required install | Expected result |
| --- | --- | --- | --- | --- |
| Real OpenAPI discovery + execution | python examples/live_openapi_quickstart.py | live public provider | schemarouter | APIs.guru getMetrics returns the current numAPIs |
| Typed local Python callable | python examples/quickstart.py | offline deterministic | schemarouter | projected Seoul weather fixture |
| Existing SDK/client behind a trusted contract | python examples/sdk_bound.py | offline deterministic | schemarouter | quote data is validated and undeclared data is projected out |
| One request, complementary providers | python examples/mixed_provider.py | offline deterministic | schemarouter | CRM + billing routes jointly satisfy the field set |
| Full schema dump vs Top-K retrieval | python examples/context_reduction.py | offline deterministic | schemarouter | shortlist context is smaller than the full catalog |
| Schema drift/watch | python examples/schema_drift_watch.py | offline deterministic | schemarouter | breaking drift becomes pending_review; accepted contract stays unchanged |
| MCP Streamable HTTP + stdio | python examples/mcp_transports.py | pinned local reference | schemarouter[mcp] | MCP add executes over both transports |
| LangChain bridge | python examples/langchain_quickstart.py | offline deterministic | schemarouter[langchain] | SchemaRouter-backed StructuredTool returns 5 |
| LangGraph node | python examples/langgraph_quickstart.py | offline deterministic | schemarouter[langgraph] | graph state receives a SchemaRouter result |
| LlamaIndex bridge | python examples/llamaindex_quickstart.py | offline deterministic | schemarouter[llamaindex] | SchemaRouter-backed FunctionTool returns 5 |
| Inspection dashboard | python examples/inspection_dashboard.py | offline deterministic | schemarouter | registry/trace HTML dashboard is written |

The MCP example is intentionally a pinned repository reference implementation. SchemaRouter does not
pretend that an arbitrary third-party MCP endpoint is a stable public compatibility dependency.

## Live provider evidence

The repository also has scheduled/manual compatibility smokes for the core network adapters:

| Adapter | Provider/evidence | Command |
| --- | --- | --- |
| OpenAPI | APIs.guru, live public | python scripts/live_openapi_smoke.py |
| OPTIMADE | COD OPTIMADE, live public | python scripts/live_optimade_smoke.py |
| GraphQL | Rick and Morty GraphQL API, live public | python scripts/live_graphql_smoke.py |
| OData | OData.org V4 reference service, live public | python scripts/live_odata_smoke.py |
| OpenRPC | repository-owned local JSON-RPC reference | python scripts/live_reference_openrpc_smoke.py |
| MCP HTTP | repository-owned MCP SDK reference server | python scripts/live_reference_mcp_smoke.py |

Those smokes record provider identity, discovery/execution status, latency, and returned-data shape.
See [the live compatibility matrix](../docs/guides/live-compatibility-matrix.md) for interpretation
and limitations.

## Why typed capability retrieval matters

context_reduction.py shows the central boundary without requiring an LLM:

~~~text
all registered tool schemas
        |
        | query: "weather temperature for a city"
        v
SchemaRouter.retrieve(..., k=2)
        |
        v
bounded typed candidate set
~~~

The full registry remains local execution authority. The downstream agent receives only a compact
candidate set rather than every schema by default. Retrieval itself does not execute a tool and does
not grant new authority.

## Mixed providers are field-first

mixed_provider.py demonstrates that a query can require fields that no single provider supplies.
SchemaRouter identifies the field coverage and compiles two complementary calls instead of treating
"choose one tool" as the only routing shape.

The same mechanism applies to scientific and non-scientific systems: materials + literature, CRM +
billing, inventory + shipping, observability + incident management, and similar combinations.

## Visual walkthrough

![SchemaRouter field-first routing walkthrough](../docs/assets/real-world-scenario.svg)

The diagram is also used in the documentation home page and is kept as a small shareable visual
artifact for explaining the architecture.

## CI policy

Mandatory CI executes the deterministic core examples and the pinned MCP transport example.
Framework-specific examples run in their matching optional-extra jobs. Live public providers run in
the scheduled/manual compatibility workflow, not as release-blocking network dependencies.

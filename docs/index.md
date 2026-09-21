<div class="brand-lockup">
  <img class="brand-lockup--light" src="assets/brand/schemarouter-lockup-light.svg" alt="SchemaRouter">
  <img class="brand-lockup--dark" src="assets/brand/schemarouter-lockup-dark.svg" alt="SchemaRouter">
</div>

# SchemaRouter

**Schema-aware planning and execution for LLM tool ecosystems.**

SchemaRouter turns a natural-language request plus a tool catalog into a typed, auditable execution
plan. It is designed for agents that have access to many OpenAPI, OPTIMADE, MCP, or Python
capabilities and need stronger guarantees than "pick a tool and call it."

```text
Traditional tool routing

Query -> Tool -> Execute


SchemaRouter

Query
  -> Tool
  -> Endpoint
  -> Parameters
  -> Response fields
  -> Evidence / policy
  -> Schema validation
  -> Execute
```

## Why SchemaRouter?

As tool catalogs grow, the difficult part is no longer only **which tool should I call?** The runtime
also needs to decide:

- which operation inside the tool is relevant;
- which arguments are actually declared;
- which response fields are needed without pruning away answer-critical context;
- whether the operation is read-only, mutating, destructive, or unclassified;
- whether the schema changed after the plan was created;
- whether the raw result satisfies the declared contract.

SchemaRouter makes those decisions explicit and machine-checkable.

## Where it fits

SchemaRouter complements existing standards and frameworks rather than replacing them.

| Layer | Role |
| --- | --- |
| OpenAPI | Describes HTTP APIs |
| MCP | Exposes tools through a standard protocol |
| LangChain / LangGraph / LlamaIndex | Provides broader orchestration and agent composition |
| Jev / bounded decision providers | Optionally refine finite schema-derived choices |
| **SchemaRouter** | Compiles requests into schema-constrained tool calls and enforces them |

A surrounding agent framework can remain responsible for conversation, graph orchestration, model
selection, checkpoints, and memory. SchemaRouter stays focused on the **tool-schema boundary**.

## Five-minute example

A typed Python function can become a validated tool with no manual schema construction:

--8<-- "examples/quickstart.py"

The same execution surface is used for OpenAPI, OPTIMADE, MCP, and approved documentation-derived
tools:

```python
result = router.invoke(request)
result = await router.ainvoke(request)

results = router.batch(requests)
results = await router.abatch(requests)

async for event in router.astream_events(request):
    ...
```

## Ingestion paths

Choose the strongest available source of truth.

=== "Python"

    Use typed Python callables when the capability is local and under your control.

    ```python
    router.add_callable(my_function)
    ```

=== "OpenAPI"

    Use an OpenAPI 3.x document when an HTTP API already publishes a machine-readable contract.

    ```python
    router = await SchemaRouter.from_url(
        "https://api.example.com/openapi.json",
        kind="openapi",
    )
    ```

=== "MCP"

    Use an MCP Streamable HTTP endpoint when the capability is already exposed through MCP.

    ```python
    router = await SchemaRouter.from_url(
        "http://localhost:8000/mcp",
        kind="mcp",
    )
    ```

=== "Human-readable docs"

    Documentation pages are not trusted as executable schemas. SchemaRouter first creates an
    evidence-grounded proposal, then requires explicit approval.

    ```python
    proposal = await router.inspect_url(url, model=documentation_model)
    router.approve_proposal(proposal, base_url="https://api.example.com")
    ```

## Core guarantees

SchemaRouter's current core is built around fail-closed behavior:

- unknown tools, endpoints, arguments, and fields do not become executable;
- required arguments are recomputed at execution time;
- input and raw output are validated with JSON Schema;
- stale schema fingerprints and stale invoker bindings are rejected;
- remote metadata and model output cannot grant side-effect permissions;
- schema-fetch credentials and runtime credentials use separate channels;
- event payloads are redacted unless explicitly enabled;
- automatic retries are read-only by default;
- optional decision providers may select only from finite locally authorized choices;
- OpenAPI and OPTIMADE remote responses are bounded before decoding.

## Next steps

<div class="grid cards" markdown>

-   **Getting started**

    ---

    Install the project and run the first offline example.

    [Installation →](getting-started/installation.md)

-   **Understand the model**

    ---

    Learn why Tool, Endpoint, Parameter, Field, and Policy are separate contracts.

    [Core concepts →](concepts/schema-router.md)

-   **Connect a real API**

    ---

    Import an OpenAPI document and keep execution authority explicit.

    [OpenAPI guide →](guides/openapi.md)

-   **Use it with agent frameworks**

    ---

    Expose validated endpoints to LangChain or LlamaIndex without bypassing SchemaRouter.

    [LangChain integration →](integrations/langchain.md)

-   **Use bounded decisions**

    ---

    Add an opt-in finite-choice provider such as Jev while retaining deterministic fallback.

    [Decision backends →](concepts/decision-backends.md)

</div>

<div class="brand-lockup">
  <img class="brand-lockup--light" src="assets/brand/schemarouter-lockup-light.svg" alt="SchemaRouter">
  <img class="brand-lockup--dark" src="assets/brand/schemarouter-lockup-dark.svg" alt="SchemaRouter">
</div>

<div class="sr-hero" markdown>

<span class="sr-kicker">SchemaRouter 0.5.0</span>

# Put a typed execution boundary between agents and tools

SchemaRouter compiles a natural-language request into a **schema-constrained tool call**, then
validates policy, schema identity, arguments, and raw output before execution is accepted.

```bash
pip install schemarouter
```

[Get started](getting-started/installation.md){ .md-button .md-button--primary }
[OpenAPI guide](guides/openapi.md){ .md-button }
[GitHub](https://github.com/JDeun/SchemaRouter){ .md-button }

</div>

<div class="grid cards" markdown>

-   **Compile**

    Turn OpenAPI, MCP, OPTIMADE, Python callables, or approved documentation into one typed
    Tool / Endpoint / Parameter / Field model.

-   **Validate**

    Reject undeclared arguments, invalid raw outputs, stale schema fingerprints, stale bindings,
    and unsupported schema assumptions.

-   **Enforce**

    Keep mutation authority, credentials, retries, budgets, approvals, and execution hooks inside
    trusted local boundaries.

</div>

## Where it fits

```text
LangChain / LangGraph / LlamaIndex / your orchestrator
                         |
                    SchemaRouter
                         |
          OpenAPI / MCP / OPTIMADE / Python
```

SchemaRouter is deliberately narrower than an agent framework. The orchestrator owns conversation,
graphs, models, memory, and checkpoints. SchemaRouter owns the **tool-schema execution boundary**.

## Start in five minutes

```python
from pydantic import BaseModel
from schemarouter import PlanRequest, SchemaRouter, schema_tool


class Weather(BaseModel):
    city: str
    temperature: float


@schema_tool(read_only=True)
def current_weather(city: str) -> Weather:
    return Weather(city=city, temperature=20.5)


router = SchemaRouter()
router.add_callable(current_weather)

result = router.invoke(
    PlanRequest(query="city temperature", arguments={"city": "Seoul"})
)
```

[Continue the quickstart →](getting-started/quickstart.md)

## Connect a capability source

<div class="grid cards" markdown>

-   **Python**

    Best when the capability is local and typed.

    [Python tools →](guides/python-tools.md)

-   **OpenAPI**

    Best when an HTTP API already publishes a machine-readable contract.

    [OpenAPI →](guides/openapi.md)

-   **MCP**

    Best when tools are already exposed through MCP.

    [MCP →](guides/mcp.md)

-   **OPTIMADE**

    Best for materials-data providers that expose OPTIMADE.

    [OPTIMADE →](guides/optimade.md)

</div>

Human-readable API documentation follows a separate **inspect → proposal → explicit approval**
flow and never becomes executable automatically.

[Documentation-derived tools →](guides/html-documentation.md)

## Core runtime guarantees

- unknown tools, endpoints, parameters, and fields do not become executable;
- input and raw output are validated with JSON Schema;
- stale schema fingerprints and invoker bindings fail closed;
- remote metadata and model output cannot grant mutation or destructive authority;
- credentials remain outside model-visible planner arguments;
- retries, wall-clock time, remote calls, response size, and optional cost units can be bounded;
- OpenAPI compatibility gaps are reported instead of silently guessed;
- event payloads remain redacted unless explicitly enabled.

## 0.5 focus

Version 0.5 tightens existing contracts rather than expanding into a broader agent framework. It
adds transient-aware retry classification, budget-bounded backoff, elapsed-time enforcement across
approval/hooks, and a concentrated OpenAPI fidelity pass covering parameter precedence, required
JSON bodies, protocol-controlled headers, generated endpoint collisions, and multiple 2xx response
variants.

[Read the 0.5.0 release notes →](releases/0.5.0.md)

## Go deeper

<div class="grid cards" markdown>

-   **Execution model**

    Tool, endpoint, schema identity, planning, and policy.

    [Core concepts →](concepts/schema-router.md)

-   **Runtime controls**

    Retry, execution policy, approvals, hooks, events, traces, and operational inspection.

    [Inspect registries and runs →](guides/inspection.md)

-   **Framework integrations**

    LangChain, LangGraph, LlamaIndex, Jev, Laya, Ollama, and OpenTelemetry.

    [Integrations →](integrations/langchain.md)

-   **Architecture**

    Maturity, compatibility policy, security boundaries, and API reference.

    [Architecture →](architecture.md)

</div>

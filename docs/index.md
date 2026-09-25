<div class="brand-lockup">
  <img class="brand-lockup--light" src="assets/brand/schemarouter-lockup-light.svg" alt="SchemaRouter">
  <img class="brand-lockup--dark" src="assets/brand/schemarouter-lockup-dark.svg" alt="SchemaRouter">
</div>

<div class="sr-hero" markdown>

<span class="sr-kicker">SchemaRouter 0.7.0</span>

# Put a typed execution boundary between agents and tools

SchemaRouter compiles a natural-language request into the **smallest declared data-field plan it can
justify**, chooses a trusted provider/access path that can supply those fields, and validates policy,
schema identity, arguments, availability, and raw output before execution is accepted.

```bash
pip install schemarouter
```

[Get started](getting-started/installation.md){ .md-button .md-button--primary }
[OpenAPI guide](guides/openapi.md){ .md-button }
[GitHub](https://github.com/JDeun/SchemaRouter){ .md-button }

</div>

<div class="grid cards" markdown>

-   **Minimize**

    Resolve the semantic data need first. Request only the planned fields upstream when the endpoint
    explicitly supports server-side projection, then keep only those fields downstream.

-   **Compile**

    Turn OpenAPI, MCP, OPTIMADE, Python callables, or approved documentation into one typed
    Provider / Access path / Tool / Endpoint / Parameter / Field model.

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
graphs, model invocation strategy, memory, checkpoints, and agent loops. SchemaRouter owns the
**tool-schema execution boundary**.

Optional decision backends such as Laya, Ollama, and Jev sit **inside the bounded selection step**.
They receive only finite candidate IDs already produced from the local schema catalog. They do not
become orchestrators, cannot invent executable capabilities, and cannot grant execution authority.

Applications that already use GPT, Gemini, Claude, or another hosted model can inject that existing
client through SchemaRouter's provider-neutral analyzer or decision-backend callable contracts.
SchemaRouter does not require a second local model stack.

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
- event payloads remain redacted unless explicitly enabled;
- temporary access failures use finite cooldowns and optional trusted health probes rather than
  permanent blacklists;
- provider/access fallback never broadens the logical field need compiled from the query.

## 0.6 focus

Version 0.6 keeps the same execution-boundary scope while adding bounded local/model-assisted
decisions, operational inspection, and a broader fail-closed OpenAPI subset. It adds Laya as an
optional local decision backend, provider-neutral hosted-model reuse, live/SQLite inspection and a
static dashboard, composed-response field discovery, bounded static `$id`/`$anchor` resolution,
typed JSON root bodies, nullable normalization, and spec-faithful default parameter serialization.

[Read the 0.6.0 release notes →](releases/0.6.0.md)

## 0.7 focus

Version `0.7.0` keeps SchemaRouter focused on the execution boundary while adding
provider/access fallback, recoverable health state, trusted parameter aliases, and stricter
field-first contracts. Scientific result fields can now carry explicit datatypes, optional unit
metadata and canonical normalization, plus exact trusted qualifiers such as temperature, phase,
orientation, or method.

Those qualifiers can participate in deterministic routing only when the condition is visibly present
in the query. They also gate cross-provider fallback exactly. SchemaRouter does not infer scientific
equivalence, convert qualifier values, or synthesize measurement context.

[Field-first execution and scientific contracts →](concepts/field-first-execution.md)

[Read the 0.7.0 release notes →](releases/0.7.0.md)

## Go deeper

<div class="grid cards" markdown>

-   **Execution model**

    Tool, endpoint, schema identity, planning, and policy.

    [Core concepts →](concepts/schema-router.md) · [Design principles →](concepts/design-principles.md)

-   **Runtime controls**

    Retry, execution policy, approvals, hooks, events, traces, and operational inspection.

    [Inspect registries and runs →](guides/inspection.md)

-   **Frameworks and decision backends**

    LangChain/LangGraph/LlamaIndex integrate above SchemaRouter. Laya/Ollama/Jev are optional
    bounded decision providers inside it. OpenTelemetry exports telemetry.

    [Decision backends →](concepts/decision-backends.md)

-   **Architecture**

    Maturity, compatibility policy, security boundaries, and API reference.

    [Architecture →](architecture.md)

</div>

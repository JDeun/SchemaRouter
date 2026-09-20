<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-dark.svg">
    <img alt="SchemaRouter" src="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-light.svg" width="760">
  </picture>
</p>

# SchemaRouter

**Schema-aware planning and execution for LLM tool ecosystems.**

[![CI](https://github.com/JDeun/SchemaRouter/actions/workflows/ci.yml/badge.svg)](https://github.com/JDeun/SchemaRouter/actions/workflows/ci.yml)
[![Docs](https://github.com/JDeun/SchemaRouter/actions/workflows/docs.yml/badge.svg)](https://github.com/JDeun/SchemaRouter/actions/workflows/docs.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://github.com/JDeun/SchemaRouter/blob/main/LICENSE)

SchemaRouter compiles a natural-language request plus a registered capability catalog into a small,
typed, auditable execution plan.

It goes beyond `Query -> Tool` routing:

```text
Query
  -> Tool
  -> Endpoint
  -> Parameters
  -> Response fields
  -> Evidence / policy
  -> Schema validation
  -> Execute
```

SchemaRouter is intentionally narrower than LangChain or LangGraph. It is designed to sit at the
**tool-schema boundary** between an agent and structured capability sources such as OpenAPI, MCP,
OPTIMADE, Python callables, and third-party adapter protocols.

> Status: **v0.2 alpha development**. The v0.1 core is frozen on main; v0.2 adds a pluggable
> adapter ecosystem without weakening the existing planner/executor trust boundary.

## Why

As an agent gains more tools, choosing the tool is only one part of the problem. The runtime also
needs to know:

- which operation inside that tool is relevant;
- which parameters are declared and valid;
- which response fields should be retained;
- whether the operation is read-only, mutating, destructive, or unclassified;
- whether the schema changed after planning;
- whether the raw tool result actually satisfies the declared contract.

SchemaRouter makes those decisions explicit.

## Quickstart

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

results = router.invoke(
    PlanRequest(
        query="city temperature",
        arguments={"city": "Seoul"},
    )
)

print(results[0].data)
```

The same execution vocabulary works across capability sources:

```python
router.invoke(request)
await router.ainvoke(request)

router.batch(requests)
await router.abatch(requests)

router.stream(request)
router.astream(request)
router.astream_events(request)
```

## Bring your schema

### OpenAPI

```python
router = await SchemaRouter.from_url(
    "https://api.example.com/openapi.json",
    kind="openapi",
)
```

### OPTIMADE

```python
router = await SchemaRouter.from_url(
    "https://www.crystallography.net/cod/optimade",
    kind="optimade",
)
```

OPTIMADE entry schemas are discovered from `/info/<entry_type>`. Planned fields are translated
into the protocol's `response_fields` query parameter before execution.

### MCP

```bash
pip install -e ".[mcp]"
```

```python
router = await SchemaRouter.from_url(
    "http://localhost:8000/mcp",
    kind="mcp",
)
```

### Python

```python
router.add_callable(my_typed_function)
```

### Human-readable API docs

```python
proposal = await router.inspect_url(
    "https://docs.example.com/api",
    model=documentation_model,
)

router.approve_proposal(
    proposal,
    base_url="https://api.example.com",
)
```

Human-readable documentation never becomes executable automatically. It first becomes an
evidence-grounded proposal and then requires explicit approval.

## Core guarantees

- **Schema-constrained planning** — unknown tools, endpoints, parameters, and fields cannot become
  executable calls.
- **Runtime JSON Schema validation** — validate arguments before invocation and raw output before
  projection.
- **Schema and binding drift detection** — stale plans and stale transports fail closed.
- **Local execution authority** — remote metadata and model output cannot grant mutation or
  destructive permissions.
- **Credential separation** — schema-fetch credentials and runtime credentials stay in different
  channels.
- **Read-only retries by default** — contract violations are never retried.
- **Redacted runtime events by default** — payload tracing is opt-in.
- **Pluggable registry** — custom registries can implement the public `ToolRegistry` protocol.
- **Pluggable source adapters** — `AdapterRegistry` lets structured protocols compile into the same
  `ToolSpec` / `EndpointSpec` execution model.

## With LangChain

Install the optional integration:

```bash
pip install -e ".[langchain]"
```

Then expose registered endpoints as LangChain `StructuredTool` objects:

```python
from schemarouter.integrations import to_langchain_tools

tools = to_langchain_tools(router)
```

Execution still flows through SchemaRouter's policy, fingerprint, input, and output validation.

## Documentation

Full documentation is organized as a framework manual rather than embedded in this README:

- [Getting started](https://jdeun.github.io/SchemaRouter/getting-started/installation/)
- [Core concepts](https://jdeun.github.io/SchemaRouter/concepts/schema-router/)
- [OpenAPI guide](https://jdeun.github.io/SchemaRouter/guides/openapi/)
- [OPTIMADE guide](https://jdeun.github.io/SchemaRouter/guides/optimade/)
- [MCP guide](https://jdeun.github.io/SchemaRouter/guides/mcp/)
- [LangChain integration](https://jdeun.github.io/SchemaRouter/integrations/langchain/)
- [API reference](https://jdeun.github.io/SchemaRouter/reference/api/)
- [Architecture](https://jdeun.github.io/SchemaRouter/architecture/)
- [Security](https://github.com/JDeun/SchemaRouter/blob/main/SECURITY.md)
- [Brand assets](https://jdeun.github.io/SchemaRouter/project/brand/)

Build the docs locally with:

```bash
pip install -e ".[docs]"
mkdocs serve
```

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest -q -m "not mcp_integration"
python examples/quickstart.py
```

Optional integration suites are isolated from the core package:

```bash
pip install -e ".[dev,mcp]"
pytest -q tests/test_mcp_integration.py

pip install -e ".[dev,langchain]"
pytest -q tests/test_langchain_integration.py
```

## Project scope

SchemaRouter does **not** implement another chat abstraction, graph runtime, model-provider layer,
memory system, or checkpoint store. Those belong in surrounding agent frameworks.

Its scope is:

> **Natural-language request -> typed tool execution plan -> validated execution.**

## Research

SchemaRouter originated from
[SchemaRouter: Field-Aware Tool Routing for Efficient Heterogeneous Agentic RAG](https://github.com/JDeun/paper_SchemaRouter).
The framework keeps the research idea while removing harness assumptions such as one endpoint per
tool and fixture-only execution.

## License

[MIT](LICENSE) © 2026 Yong-eun Cho

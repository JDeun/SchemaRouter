<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-dark.svg">
    <img alt="SchemaRouter" src="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-light.svg" width="680">
  </picture>
</p>

<p align="center"><strong>Schema-aware planning and execution for LLM tool ecosystems.</strong></p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="https://jdeun.github.io/SchemaRouter/">Docs</a> ·
  <a href="https://github.com/JDeun/SchemaRouter/releases/latest">Latest release</a>
</p>

<p align="center">
  <a href="https://github.com/JDeun/SchemaRouter/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/JDeun/SchemaRouter/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/JDeun/SchemaRouter/actions/workflows/docs.yml"><img alt="Docs" src="https://github.com/JDeun/SchemaRouter/actions/workflows/docs.yml/badge.svg"></a>
  <a href="https://pypi.org/project/schemarouter/"><img alt="PyPI" src="https://img.shields.io/pypi/v/schemarouter"></a>
  <a href="https://github.com/JDeun/SchemaRouter/blob/main/LICENSE"><img alt="MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
</p>

SchemaRouter sits between an agent and its tools. It turns a natural-language request plus a
registered capability catalog into a small, typed execution plan, then validates that plan again at
runtime before anything executes.

```text
Query
  -> Tool
  -> Endpoint
  -> Parameters
  -> Response fields
  -> Policy / evidence
  -> Schema validation
  -> Execute
```

It is **not** another general agent framework. LangChain, LangGraph, LlamaIndex, or your own
orchestrator can stay above it; OpenAPI, MCP, OPTIMADE, Python callables, and adapter plugins stay
below it.

> **Current stable release: 0.5.0** · `pip install schemarouter` · pre-1.0

## Why SchemaRouter

Tool selection alone is not enough once an agent has many capabilities. SchemaRouter makes the
execution boundary explicit:

- choose a declared tool and endpoint;
- accept only declared parameters and output fields;
- validate inputs and raw outputs with JSON Schema;
- reject stale schema fingerprints and stale invoker bindings;
- keep mutation/destructive authority local and fail closed;
- separate credentials from model-visible arguments;
- bound retries, elapsed time, remote calls, and response size;
- surface OpenAPI compatibility gaps instead of silently guessing.

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

result = router.invoke(
    PlanRequest(query="city temperature", arguments={"city": "Seoul"})
)

print(result[0].data)
```

## Connect capabilities

| Source | Use when | Entry point |
| --- | --- | --- |
| **Python** | capability is local and typed | `router.add_callable(...)` |
| **OpenAPI** | HTTP API publishes a machine-readable contract | `SchemaRouter.from_url(..., kind="openapi")` |
| **MCP** | tools are exposed through MCP | `SchemaRouter.from_url(..., kind="mcp")` |
| **OPTIMADE** | materials data is exposed through OPTIMADE | `SchemaRouter.from_url(..., kind="optimade")` |
| **Human-readable docs** | no machine-readable schema exists | inspect → proposal → explicit approval |

Optional bridges are available for **LangChain, LangGraph, LlamaIndex, Jev / TypeSafe, Ollama, and
OpenTelemetry**. They do not bypass SchemaRouter's policy or validation boundary.

## What 0.5 adds

0.5 is a runtime-hardening release rather than a scope expansion:

- transient-aware HTTP retry classification and explicit non-retryable failures;
- retry backoff constrained by wall-clock execution budgets;
- elapsed-time enforcement across approval callbacks and execution hooks;
- more faithful OpenAPI parameter precedence and generated endpoint naming;
- required JSON request-body presence without fabricating schema-less bodies;
- protocol-controlled OpenAPI headers kept out of planner arguments;
- multiple 2xx JSON/no-content response variants preserved and validated correctly.

See the [0.5.0 release notes](https://jdeun.github.io/SchemaRouter/releases/0.5.0/) for details.

## Documentation

Start with the manual rather than this README:

- [Install and quickstart](https://jdeun.github.io/SchemaRouter/getting-started/installation/)
- [Understand the execution model](https://jdeun.github.io/SchemaRouter/concepts/schema-router/)
- [OpenAPI guide](https://jdeun.github.io/SchemaRouter/guides/openapi/)
- [Runtime policy and retry](https://jdeun.github.io/SchemaRouter/guides/execution-policy/)
- [Framework integrations](https://jdeun.github.io/SchemaRouter/integrations/langchain/)
- [API reference](https://jdeun.github.io/SchemaRouter/reference/api/)
- [Architecture and maturity](https://jdeun.github.io/SchemaRouter/architecture/)
- [Security model](https://jdeun.github.io/SchemaRouter/security/threat-model/)

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

ruff check .
pytest -q -m "not mcp_integration"
```

The protected CI surface also covers Python 3.10–3.14, Windows, minimum dependencies, package
artifacts, Pyright, coverage, documentation, and optional integration suites.

## Scope

SchemaRouter intentionally does **not** implement another chat abstraction, model-provider layer,
memory system, checkpoint store, or graph runtime.

> **Natural-language request → typed tool execution plan → validated execution.**

## Research and license

SchemaRouter originated from
[SchemaRouter: Field-Aware Tool Routing for Efficient Heterogeneous Agentic RAG](https://github.com/JDeun/paper_SchemaRouter).

[MIT](LICENSE) © 2026 Yong-eun Cho

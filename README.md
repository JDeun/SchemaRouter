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

```text
Agent / graph / application orchestrator
                 |
           SchemaRouter
     typed planning + validation
                 |
        capability sources
 OpenAPI / MCP / OPTIMADE / Python

Optional decision backends (Laya / Ollama / Jev) plug into SchemaRouter's bounded selection step.
They do not become agents, do not run tool loops, and do not receive execution authority.
```

> **Current stable release: 0.6.0** · `pip install schemarouter` · pre-1.0

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

Framework bridges are available for **LangChain, LangGraph, and LlamaIndex**. **OpenTelemetry**
provides optional telemetry export. **Jev / TypeSafe, Laya, and Ollama are optional decision
backends**, not agent frameworks. Existing **GPT, Gemini, Claude, or other hosted model clients**
can also be injected through the provider-neutral `ModelQueryAnalyzer` or
`CallableDecisionBackend` contracts. None of these paths bypass SchemaRouter's policy, schema
validation, or execution boundary.

## What 0.6 adds

0.6 adds optional local/model-assisted decision backends, operational inspection/dashboard
surfaces, and a broader fail-closed OpenAPI subset:

- local Laya decisions with CPU/CUDA/MPS device controls and benchmark metadata;
- provider-neutral reuse of existing GPT, Gemini, Claude, or other hosted clients;
- live/persistent inspection plus a self-contained read-only HTML dashboard;
- response `oneOf`/`anyOf` field discovery and static same-origin `$id`/`$anchor` resolution;
- typed JSON root request bodies, OpenAPI 3.0 nullable normalization, and default parameter-style
  serialization.

See the [0.6.0 release notes](https://jdeun.github.io/SchemaRouter/releases/0.6.0/) for details.

## Inspect what SchemaRouter built

Persisted registries and run traces can be inspected without executing tools:

```bash
schemarouter inspect registry --db ./registry.sqlite3
schemarouter inspect tool materials --db ./registry.sqlite3
schemarouter inspect traces --db ./traces.sqlite3
schemarouter inspect trace <RUN_ID> --db ./traces.sqlite3
schemarouter dashboard \
  --registry ./registry.sqlite3 \
  --traces ./traces.sqlite3 \
  --output ./artifacts/schemarouter-dashboard.html
```

Add `--json` to inspection commands for automation. The dashboard is a self-contained read-only
HTML export built from the same inspection contracts. The registry view exposes tool/endpoint
topology, method/path, mutation classification, parameter/output-field counts, and schema
fingerprints; trace views expose persisted run/event history.

[Operational inspection guide](https://jdeun.github.io/SchemaRouter/guides/inspection/)

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

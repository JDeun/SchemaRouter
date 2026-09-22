<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-dark.svg">
    <img alt="SchemaRouter" src="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-light.svg" width="760">
  </picture>
</p>

# SchemaRouter

**Schema-aware planning and execution for LLM tool ecosystems.**

[English](README.md) · [한국어](README.ko.md)

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

> Status: **0.3.0 is the current public non-prerelease release**. Install it from PyPI with
> `pip install schemarouter`. SchemaRouter remains pre-1.0, so deliberate compatibility changes
> may still occur in later 0.x minor releases under the documented versioning policy.

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
pip install "schemarouter[mcp]"
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
  channels; authenticated MCP keeps secrets in the trusted transport boundary.
- **Read-only retries by default** — contract violations are never retried.
- **Per-call approval and execution budgets** — trusted local callbacks and deterministic call,
  attempt, remote, time, quota, and cost-unit limits fail closed.
- **OpenAPI compatibility reporting** — partial/unsupported constructs are machine-readable instead
  of silently reinterpreted.
- **Redacted runtime events by default** — payload tracing is opt-in.
- **Pluggable registry** — custom registries can implement the public `ToolRegistry` protocol.
- **Pluggable source adapters** — `AdapterRegistry` lets structured protocols compile into the same
  `ToolSpec` / `EndpointSpec` execution model; installed entry-point plugins require an explicit
  allowlist before import.
- **Optional OpenTelemetry export** — redacted runtime events can become parented run/tool spans
  without exporting payload values.

## With LangChain

```bash
pip install "schemarouter[langchain]"
```

```python
from schemarouter.integrations import to_langchain_tools

tools = to_langchain_tools(router)
```

Execution still flows through SchemaRouter's policy, fingerprint, input, and output validation.

## With LangGraph

```bash
pip install "schemarouter[langgraph]"
```

```python
from schemarouter.integrations import to_langgraph_node

builder.add_node("schema_router", to_langgraph_node(router))
```

The node supports sync/async `StateGraph` execution and returns checkpoint-friendly partial state
updates while SchemaRouter retains planning, policy, and validated execution authority.

## With LlamaIndex

Install the packaged LlamaIndex bridge:

```bash
pip install "schemarouter[llamaindex]"
```

```python
from schemarouter.integrations import to_llamaindex_tools

tools = to_llamaindex_tools(router)
```

LlamaIndex remains the agent/workflow layer; SchemaRouter retains schema identity, validation, and
endpoint execution.

## Experimental bounded decisions

SchemaRouter includes an optional bounded `DecisionBackend` for tool/endpoint selection. It is
**off by default** and cannot invent executable schema members.

```python
from schemarouter import DecisionPolicy, SchemaPlanner
from schemarouter.integrations import JevDecisionBackend

planner = SchemaPlanner(
    registry,
    decision_backend=JevDecisionBackend(min_confidence=0.65),
    decision_policy=DecisionPolicy(
        enabled=True,
        endpoint_selection=True,
        fallback="deterministic",
    ),
)
```

Jev / TypeSafe System One is optional:

```bash
pip install "schemarouter[jev]"
export TYPESAFE_API_KEY="..."
```

A local Ollama model can also serve as the bounded decision backend without an additional Python
SDK:

```python
from schemarouter.integrations import OllamaDecisionBackend

backend = OllamaDecisionBackend("your-installed-model")
```

Providers receive only bounded decision inputs. Unknown option IDs fail closed, and deterministic
fallback remains available. No decision backend is enabled merely because a dependency, API key, or
local model exists.

## Decision benchmark

Run the deterministic baseline:

```bash
python scripts/benchmark_decision_routing.py
```

Compare Jev when credentials are available:

```bash
TYPESAFE_API_KEY="..." python scripts/benchmark_decision_routing.py --jev
```

Compare an installed local Ollama model:

```bash
python scripts/benchmark_decision_routing.py --ollama-model your-installed-model
```

The harness includes a checked-in 144-case multilingual/adversarial corpus and reports routing
accuracy, invalid-plan rate, abstentions/fallbacks, category accuracy, p50/p95 latency, token usage,
errors, and optional cost estimates. A provider-neutral `ModelQueryAnalyzer` callable can also be
supplied with `--model-callable module:function`.

```bash
python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --json-out artifacts/decision-benchmark.json \
  --csv-out artifacts/decision-benchmark.csv
```

## Documentation

Full documentation is organized as a framework manual rather than embedded in this README:

- [Getting started](https://jdeun.github.io/SchemaRouter/getting-started/installation/)
- [Core concepts](https://jdeun.github.io/SchemaRouter/concepts/schema-router/)
- [OpenAPI guide](https://jdeun.github.io/SchemaRouter/guides/openapi/)
- [OpenAPI compatibility](https://jdeun.github.io/SchemaRouter/guides/openapi-compatibility/)
- [OPTIMADE guide](https://jdeun.github.io/SchemaRouter/guides/optimade/)
- [MCP guide](https://jdeun.github.io/SchemaRouter/guides/mcp/)
- [LangChain integration](https://jdeun.github.io/SchemaRouter/integrations/langchain/)
- [LlamaIndex integration](https://jdeun.github.io/SchemaRouter/integrations/llamaindex/)
- [Jev / TypeSafe integration](https://jdeun.github.io/SchemaRouter/integrations/jev/)
- [OpenTelemetry integration](https://jdeun.github.io/SchemaRouter/integrations/opentelemetry/)
- [Third-party adapter plugins](https://jdeun.github.io/SchemaRouter/guides/adapter-plugins/)
- [Decision backends](https://jdeun.github.io/SchemaRouter/concepts/decision-backends/)
- [Decision benchmark](https://jdeun.github.io/SchemaRouter/guides/decision-benchmark/)
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
python scripts/benchmark_decision_routing.py

# Type-check the complete packaged surface, including optional integrations.
pip install -e ".[dev,mcp,langchain,langgraph,llamaindex,jev,otel]"
pyright
pytest -q --cov=schemarouter --cov-branch --cov-report=term-missing
```

Optional integration suites are isolated from the core package:

```bash
pip install -e ".[dev,mcp]"
pytest -q tests/test_mcp_integration.py

pip install -e ".[dev,langchain]"
pytest -q tests/test_langchain_integration.py

pip install -e ".[dev,llamaindex]"
pytest -q tests/test_llamaindex_integration.py

pip install -e ".[dev,jev]"
pytest -q tests/test_jev_integration.py

pip install -e ".[dev,otel]"
pytest -q tests/test_opentelemetry_integration.py
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

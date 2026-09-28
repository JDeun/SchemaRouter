<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-dark.svg">
    <img alt="SchemaRouter" src="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-light.svg" width="680">
  </picture>
</p>

<p align="center"><strong>Typed capability routing and execution for RAG and LLM agent systems.</strong></p>

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

> **Stable release: 0.10.0** · `pip install schemarouter` · Beta / pre-1.0

SchemaRouter sits between a RAG/agent application and its structured external capabilities. It
normalizes OpenAPI, MCP, OPTIMADE, Python, and plugin-defined tools into a typed capability catalog,
selects a bounded executable route for the requested data, and validates the contract again before
and after execution.

It is **not** a general agent framework, an LLM provider layer, or a RAG generator.

## Where SchemaRouter fits in RAG

**Retrieval-Augmented Generation (RAG)** augments generation with information retrieved from
external, non-parametric sources.

SchemaRouter does not perform the final generation step. Its role is narrower: it can provide the
**structured retrieval and execution layer** that lets a RAG or agent system obtain live external
data from APIs and tools under explicit schemas and policy.

```text
User query
    |
    v
RAG / Agent / Application
    |
    |  "I need elastic modulus + provenance"
    v
SchemaRouter
    |
    +--> retrieve a registered capability
    +--> select endpoint + required fields
    +--> validate parameters / policy / health
    +--> execute trusted transport
    +--> validate raw output
    +--> normalize declared units / project fields
    |
    v
Typed external data
    |
    v
RAG generation / agent reasoning
```

For document-centric RAG, a retriever commonly searches chunks or records. SchemaRouter addresses a
different retrieval surface: **executable capabilities and the structured data they can return**.

[Read the RAG positioning and capability model](https://jdeun.github.io/SchemaRouter/concepts/capability-catalog/)

## Field-first, route-second

SchemaRouter first resolves **what data is required**, then chooses a registered route that can
provide it.

For example:

```text
Query: "What is the elastic modulus of this material at 300 K?"

Required field
  semantic_id: mechanical.elastic_modulus
  datatype: number
  unit: optional but declared when applicable
  qualifiers:
    temperature: 300 K

Possible routes
  provider A / REST endpoint
  provider A / OPTIMADE access
  provider B / MCP tool
```

Availability can change the route. It must not silently change the requested data contract.

A field contract can carry:

- JSON datatype / shape;
- semantic ID and aliases;
- optional source unit;
- explicit canonical unit normalization;
- exact qualifiers such as temperature, pressure, phase, orientation, or method;
- provenance, license, or source-type evidence;
- provider/access identity and availability metadata.

Units are optional because many legitimate fields are text, identifiers, booleans, structured
objects, or dimensionless values. SchemaRouter does not infer scientific equivalence or conversion
factors from a unit string alone.

## Execution boundary

```text
LangChain / LangGraph / LlamaIndex / your application
                         |
                    SchemaRouter
                         |
          OpenAPI / MCP / OPTIMADE / Python
```

The surrounding framework owns conversation, decomposition, generation, memory, graphs, and agent
loops. SchemaRouter owns the typed capability and execution boundary.

Optional Laya, Ollama, Jev/System-One, hosted-model, embedding, or pairwise decision backends may
assist selection over locally registered candidates. They do not become execution authority and
cannot invent tools, fields, credentials, permissions, or side effects.

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
| **MCP** | capabilities are exposed through MCP | `SchemaRouter.from_url(..., kind="mcp")` |
| **OPTIMADE** | materials data is exposed through OPTIMADE | `SchemaRouter.from_url(..., kind="optimade")` |
| **Human-readable docs** | no machine-readable contract exists | inspect → proposal → explicit approval |

Framework bridges are available for LangChain, LangGraph, and LlamaIndex. OpenTelemetry is optional.
Third-party bounded decision backends can be published through the
`schemarouter.decision_backends` entry-point group.

## What works in 0.10.0

The released package provides a working beta implementation of the core architecture:

- typed Tool / Endpoint / Parameter / Field registry contracts;
- Python, OpenAPI, MCP, and OPTIMADE ingestion paths;
- field-first planning and bounded multi-provider field coverage;
- input and raw-output JSON Schema validation;
- schema fingerprints and binding-drift rejection;
- read/write/destructive local policy gates and per-call approval hooks;
- explicit server-side field projection plus final local projection;
- optional datatype/unit normalization and exact scientific qualifiers;
- provider/access fallback with finite cooldown and trusted health recovery;
- sync/async invocation, batch, streaming, typed events, traces, and inspection/dashboard surfaces;
- LangChain, LangGraph, LlamaIndex, Jev/System-One, Laya, Ollama, and OpenTelemetry integration
  surfaces.

So **the architecture works today** for declared capabilities and supported routing cases.

## Current limitation: open-set natural-language routing

The unresolved research problem is not basic execution. It is reliably distinguishing:

> "This request is similar to a registered domain"

from:

> "This exact operation is actually supported by a registered capability."

The strongest frozen development candidate met the standing target on canonical DEV, but failed the
independent zero-overlap fresh confirmation. Therefore no experimental learned router is promoted as
an unconditional production default in 0.10.0.

The first arbitrary-tool registry-compiled learned veto was also terminally rejected because it
became too conservative and rejected most valid supported requests.

See:

- [Routing research status](https://jdeun.github.io/SchemaRouter/research/routing-status/)
- [0.10.0 release notes](https://jdeun.github.io/SchemaRouter/releases/0.10.0/)
- [Changelog](CHANGELOG.md)

## Inspect the registry and runs

```bash
schemarouter inspect registry --db ./registry.sqlite3
schemarouter inspect tool materials --db ./registry.sqlite3
schemarouter inspect diff materials \
  --old-db ./registry-before.sqlite3 \
  --new-db ./registry-current.sqlite3
schemarouter inspect traces --db ./traces.sqlite3
schemarouter inspect trace <RUN_ID> --db ./traces.sqlite3
schemarouter dashboard \
  --registry ./registry.sqlite3 \
  --traces ./traces.sqlite3 \
  --output ./artifacts/schemarouter-dashboard.html
```

## Documentation

- [Installation](https://jdeun.github.io/SchemaRouter/getting-started/installation/)
- [Quickstart](https://jdeun.github.io/SchemaRouter/getting-started/quickstart/)
- [What SchemaRouter is](https://jdeun.github.io/SchemaRouter/concepts/schema-router/)
- [RAG positioning and capability model](https://jdeun.github.io/SchemaRouter/concepts/capability-catalog/)
- [Field-first execution](https://jdeun.github.io/SchemaRouter/concepts/field-first-execution/)
- [OpenAPI](https://jdeun.github.io/SchemaRouter/guides/openapi/)
- [MCP](https://jdeun.github.io/SchemaRouter/guides/mcp/)
- [Architecture and maturity](https://jdeun.github.io/SchemaRouter/architecture/)
- [Security model](https://jdeun.github.io/SchemaRouter/security/threat-model/)

## Scope

SchemaRouter intentionally does not implement another chat abstraction, prompt framework,
model-provider layer, conversation memory, checkpoint store, or graph runtime.

> **Natural-language request → typed capability plan → validated external data → surrounding RAG/agent**

## Research and license

SchemaRouter originated from
[SchemaRouter: Field-Aware Tool Routing for Efficient Heterogeneous Agentic RAG](https://github.com/JDeun/paper_SchemaRouter).

[MIT](LICENSE) © 2026 Yong-eun Cho

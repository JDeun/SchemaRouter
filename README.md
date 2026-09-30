<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-dark.svg">
    <img alt="SchemaRouter" src="https://raw.githubusercontent.com/JDeun/SchemaRouter/main/docs/assets/brand/schemarouter-lockup-light.svg" width="680">
  </picture>
</p>

<p align="center"><strong>Your agent has too many tools, and each one returns too much. Put a typed boundary in between.</strong></p>

<p align="center">
  <a href="README.md">English</a> ·
  <a href="README.ko.md">한국어</a> ·
  <a href="https://jdeun.github.io/SchemaRouter/">Docs</a> ·
  <a href="https://github.com/JDeun/SchemaRouter/releases/latest">Latest release</a>
</p>

<p align="center">
  <a href="https://github.com/JDeun/SchemaRouter/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/JDeun/SchemaRouter/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://github.com/JDeun/SchemaRouter/actions/workflows/docs.yml"><img alt="Docs" src="https://github.com/JDeun/SchemaRouter/actions/workflows/docs.yml/badge.svg"></a>
  <a href="https://pypi.org/project/schemarouter/"><img alt="PyPI" src="https://img.shields.io/pypi/v/schemarouter?label=PyPI&cacheSeconds=300&v=0.12.0"></a>
  <a href="https://github.com/JDeun/SchemaRouter/blob/main/LICENSE"><img alt="MIT" src="https://img.shields.io/badge/License-MIT-yellow.svg"></a>
</p>

> **Stable release: 0.12.0** · `pip install schemarouter` · Beta / pre-1.0

Agents get harder to steer as their tool catalog grows, and tool responses often contain far more
than the request needs. SchemaRouter works out **which declared data fields are needed**, exposes a
bounded set of registered tools that can supply them, and keeps only declared output fields before
the result reaches the model. Typed contracts can carry units, qualifiers, provenance, and
validation rules so one value cannot silently stand in for another.

`pip install schemarouter`

It is **not** a general agent framework, an LLM provider layer, or a RAG generator.

[Declare a result contract for an MCP server that does not publish one →](docs/guides/mcp.md) ·
[See the measured agent-utility result →](docs/research/agent-utility-b1-result.md)

## Where SchemaRouter fits in RAG

SchemaRouter does not perform final generation. It provides a **structured retrieval and execution
boundary** for applications that need live external data from APIs and tools under explicit schemas
and policy.

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

## Retrieve a compact tool set for an agent

SchemaRouter can return registered capability candidates **without planning or executing them**:

```python
candidates = router.retrieve(
    "current Young's modulus for MAT-7",
    k=5,
)

for candidate in candidates.candidates:
    print(candidate.route_id, candidate.output_fields)
```

Use `retrieve_executable(..., k=5)` when candidates must also have a currently ready local
execution binding. Async counterparts are `aretrieve` and `aretrieve_executable`.

Current `main` also includes an **experimental, default-off** structural retrieval profile:

```python
router = SchemaRouter(structural_retrieval=True)
candidates = router.retrieve("cancel this registered job", k=3)
```

This profile adds conservative tool-identifier and operation-family evidence plus a schema-specificity
tie-break. It does **not** change execution authority, and it is not the product default. Independent
retrieval confirmation passed for a fixed Top-3 shortlist, but the preregistered strong-agent
K3-vs-K5 downstream gate later failed its -2pp task-pass promotion floor. Top-3 is therefore **not**
promoted into the held-out benchmark. Treat structural retrieval as an opt-in research surface until
a later release explicitly changes that status.

The returned candidates retain the full effective input/output JSON Schemas plus registered
parameters/output fields, semantic IDs, optional units and qualifiers, provider/access identity,
read/write/destructive metadata, and schema fingerprints. Retrieval has no side effect and does not grant execution authority; the surrounding
agent still chooses among candidates and execution remains subject to SchemaRouter validation and
policy.

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

## What works in 0.12.0

The released package provides a working beta implementation of the core architecture:

- typed Tool / Endpoint / Parameter / Field registry contracts;
- first-class bounded Top-K capability retrieval through `retrieve` / `aretrieve` and executable-ready variants;
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

## Current research direction: compact capability retrieval for agents

The stable 0.12.0 execution boundary is unchanged. The active research question has shifted from
making SchemaRouter itself the final open-set classifier to evaluating it as a **typed capability
retrieval substrate** for a downstream LLM agent.

The intended separation is:

```text
registered capability catalog
  -> SchemaRouter Top-K typed candidates
  -> downstream agent chooses among candidates
  -> local schema / argument / permission / destructive policy
  -> execution
```

Why this matters: on the corrected frozen 0.14 Phase-A benchmark, Top-1 required-route recall was
**68.97%**, while Top-5 preserved **100%** of required capabilities. At 250 registered endpoints,
Top-5 exposed only **2.38%** of the FULL serialized schema context on average.

The canonical B1 Qwen3-0.6B agent benchmark is terminal: SR-5 achieved **91.30%** task pass
versus **68.48%** for FULL while using **5.42%** of FULL tool-schema tokens, with **0**
unauthorized destructive executions. This remains controlled mechanism evidence rather than a broad
production claim. The materially stronger SmolLM3-3B B2 replication (#423) is also terminal
success. A separate structural K3-vs-K5 optimization failed its preregistered task-pass promotion
gate, so K3 is not carried into the held-out benchmark. Execution-state-aware corrective retrieval
(#431) is the active gate; the 780-task held-out benchmark (#432) and final-answer quality benchmark
(#424) remain downstream confirmation stages.

The earlier 0.11–0.13 open-set classifier/veto experiments remain valuable negative evidence. No
experimental learned router or structural retrieval profile is promoted as an unconditional production default in 0.12.0.

See:

- [Routing research status](https://jdeun.github.io/SchemaRouter/research/routing-status/)
- [Prior-art roadmap](https://jdeun.github.io/SchemaRouter/research/prior-art-roadmap/)
- [Complete experiment index](https://jdeun.github.io/SchemaRouter/research/experiment-index/)
- [0.14 paper-evidence checkpoint](https://jdeun.github.io/SchemaRouter/research/0.14-paper-evidence-checkpoint/)
- [0.12.0 release notes](https://jdeun.github.io/SchemaRouter/releases/0.12.0/)
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
- [Prior-art roadmap](https://jdeun.github.io/SchemaRouter/research/prior-art-roadmap/)
- [Routing research status](https://jdeun.github.io/SchemaRouter/research/routing-status/)
- [Complete experiment index](https://jdeun.github.io/SchemaRouter/research/experiment-index/)

## Scope

SchemaRouter intentionally does not implement another chat abstraction, prompt framework,
model-provider layer, conversation memory, checkpoint store, or graph runtime.

> **Natural-language request → typed capability plan → validated external data → surrounding RAG/agent**

## Research and license

SchemaRouter originated from
[SchemaRouter: Field-Aware Tool Routing for Efficient Heterogeneous Agentic RAG](https://github.com/JDeun/paper_SchemaRouter).

[MIT](LICENSE) © 2026 Yong-eun Cho

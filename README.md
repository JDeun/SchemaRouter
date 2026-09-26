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

### Field-first, route-second

SchemaRouter first asks **which declared data fields are actually needed to answer the request**,
then chooses a provider/access path that can supply those fields. When an endpoint explicitly
supports server-side projection, only the planned fields are requested upstream; after raw schema
validation, final local projection keeps the downstream LLM context narrow even if a provider sends
extra data.

Availability may change the route, but it does not broaden the data need. Precompiled read-only
fallbacks can move from one access mode to another—and, when explicitly enabled, to another
provider—without turning runtime into an autonomous agent loop.

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

> **Current stable release: 0.8.0** · `pip install schemarouter` · pre-1.0

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

## Real-world scenario

<p align="center">
  <img src="docs/assets/real-world-scenario.svg" alt="SchemaRouter real-world scenario: field-first, route-second" width="100%">
</p>

A single request can require fields from different providers. For example, a materials question may
need a numeric `band_gap` from Materials Project and a text `abstract` from arXiv.

SchemaRouter resolves the **semantic field need first**, then spends the bounded `max_calls` budget
on complementary provider/access paths that can satisfy those fields. A route can change because of
health, policy, or availability; the required data contract does not.

```text
band_gap  -> Materials Project / OpenAPI
             ↳ OPTIMADE fallback
abstract  -> arXiv API
```

The final execution plan remains schema-validated, policy-bounded, and fail-closed. When one route
already covers every matched field, SchemaRouter can stop before reaching the `max_calls` bound.

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

## What 0.7 adds

Version `0.7.0` strengthens the same narrow execution boundary rather than adding agent orchestration:

- conservative schema-drift explanations while exact fingerprints still fail closed;
- operation-scoped local allow/deny/approval policy rules;
- structured, auditable plan explanations based on SchemaRouter-visible signals;
- explicit flat parallel fan-out only when every planned call is currently trusted read-only;
- provider/access identity, bounded read-only fallback, server-side field projection contracts,
  and recoverable access-path health state;
- typed scientific result contracts with explicit JSON datatypes, optional unit metadata, canonical
  affine unit normalization, and exact measurement/material qualifiers such as temperature, phase,
  orientation, or method;
- qualifier-aware routing that can distinguish otherwise equivalent scientific fields when the
  condition is explicitly present in the query, without unit conversion or scientific inference;
- trusted parameter aliases so the same logical argument can bind safely to provider-specific local
  parameter names without model-authored remapping.

Workflow/DAG semantics, memory, prompt systems, and autonomous tool loops remain out of scope.

See the [0.7.0 release notes](https://jdeun.github.io/SchemaRouter/releases/0.7.0/) for details.

## What 0.8 adds

Version `0.8.0` extends field-first routing with bounded semantic recall and explicit
multi-provider evidence handling while keeping execution authority local:

- optional semantic candidate recall plus separate capability-fit, operation-fit, and same-tool
  endpoint-disambiguation stages;
- trusted endpoint operation aliases without model-authored capability expansion;
- per-field evidence requirements and explicit plan coverage reporting;
- coverage-aware multi-call selection across complementary providers;
- opt-in corroboration across distinct providers plus provenance-preserving aggregation that keeps
  independent scientific observations separate instead of silently choosing a value;
- reproducible multilingual routing corpora with frozen development/calibration/holdout discipline.

The fresh 600-case v10 one-shot holdout reached **55.667% overall accuracy**, **42.188%
supported-operation routed accuracy**, **77.083% near-domain unsupported-operation rejection**, and
**100% ordinary OOD rejection**. Operation-fit remains the dominant recall bottleneck, so v10 is
treated as consumed regression evidence and will not be reused for tuning.

See the [0.8.0 release notes](https://jdeun.github.io/SchemaRouter/releases/0.8.0/) and the
[multi-provider evidence guide](https://jdeun.github.io/SchemaRouter/guides/multi-provider-evidence/).

## Inspect what SchemaRouter built

Persisted registries and run traces can be inspected without executing tools:

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

Add `--json` to inspection commands for automation. The dashboard is a self-contained read-only
HTML export built from the same inspection contracts. The registry view exposes tool/endpoint
topology, method/path, mutation classification, parameter/output-field counts, and schema
fingerprints; trace views expose persisted run/event history.

[Operational inspection guide](https://jdeun.github.io/SchemaRouter/guides/inspection/)

## Documentation

Start with the manual rather than this README:

- [Install and quickstart](https://jdeun.github.io/SchemaRouter/getting-started/installation/)
- [Understand the execution model](https://jdeun.github.io/SchemaRouter/concepts/schema-router/)
- [Read the design principles](https://jdeun.github.io/SchemaRouter/concepts/design-principles/)
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

# SchemaRouter

**Schema-aware planning and execution for LLM tool ecosystems.**

SchemaRouter compiles a natural-language request plus a registered tool catalog into a small, typed, auditable execution plan. It is designed for environments where an agent may have many OpenAPI or MCP capabilities and should not expose or fetch everything by default.

> Status: **v0.1 pre-alpha**. The current branch establishes the core contracts and deterministic planner. Network transports, model-assisted query understanding, and production observability are intentionally not hidden behind unstable APIs yet.

## Why

Most tool routers stop at **which tool?** SchemaRouter keeps the schema boundary explicit:

```text
query
  -> tool
  -> endpoint / operation
  -> validated parameters
  -> response-field projection
  -> evidence / policy requirements
  -> executable plan
```

The design comes from the [SchemaRouter research artifact](https://github.com/JDeun/paper_SchemaRouter), but the library is not a copy of the experiment harness. The framework makes endpoint schemas, output fields, schema versions, and execution validation first-class runtime contracts.

## Non-goals

SchemaRouter is **not** another LangChain clone, a model router, or a replacement for MCP. It is a planning/execution layer that can sit between an agent framework and MCP/OpenAPI/Python tools.

## v0.1 quick start

```python
from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InMemoryRegistry,
    ParameterSpec,
    PlanRequest,
    SchemaPlanner,
    ToolSpec,
)

registry = InMemoryRegistry()
registry.register(
    ToolSpec(
        name="materials",
        description="Materials property database",
        endpoints=[
            EndpointSpec(
                name="search",
                description="Search material properties",
                parameters=[ParameterSpec(name="formula", required=True)],
                output_fields=[
                    FieldSpec(name="material_id", identifier=True),
                    FieldSpec(name="band_gap", aliases=["band gap"], unit="eV"),
                    FieldSpec(
                        name="formation_energy_per_atom",
                        aliases=["formation energy"],
                        unit="eV/atom",
                    ),
                ],
            )
        ],
    )
)

planner = SchemaPlanner(registry)
plan = planner.plan(
    PlanRequest(
        query="LiFePO4 band gap and formation energy",
        arguments={"formula": "LiFePO4"},
    )
)

print(plan.model_dump())
```

The planner never invents undeclared arguments. Missing required arguments are surfaced as plan requirements instead of being silently hallucinated. Each call also carries a schema fingerprint; execution rejects a stale plan if the registered schema changed.

## Ingestion adapters

### MCP

```python
from schemarouter.adapters.mcp import tool_from_mcp

tool = tool_from_mcp(
    server_name="docs",
    tools_list_result={"tools": [...]},
)
registry.register(tool)
```

MCP `inputSchema` becomes endpoint parameters and `outputSchema` becomes projectable response fields. Endpoint names are scoped by the server tool registry, avoiding cross-server name collisions.

### OpenAPI

```python
from schemarouter.adapters.openapi import tool_from_openapi

tool = tool_from_openapi("billing", openapi_document)
registry.register(tool)
```

The v0.1 adapter supports operations, path/query/header parameters, JSON request-body properties, local `#/...` references, and JSON response schemas. Unsupported constructs remain in metadata rather than being guessed.

## Safety and correctness invariants

- **Fail closed on schema drift:** a plan fingerprint must match the current endpoint schema before execution.
- **No argument hallucination:** only declared parameters survive planning and execution validation.
- **Namespaced tools:** registry keys are `<namespace>.<tool>` when a namespace is supplied.
- **Recall-preserving projection:** identifiers plus matched fields are retained; if no output concept is confidently matched, the planner does not aggressively prune fields.
- **No hidden network behavior:** core planning is deterministic and offline.

See [`docs/architecture.md`](docs/architecture.md) for the adversarial design review and v0.1 boundaries.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check .
```

## Roadmap

1. model-assisted `QueryAnalyzer` with provider-neutral structured output
2. live MCP client adapter for the 2026-07-28 protocol plus backward compatibility
3. OpenAPI HTTP executor with auth injection outside model-visible schemas
4. policy engine for provenance, license, permissions, cost, and destructive operations
5. tracing, replay, schema-drift diagnostics, and benchmark suite
6. LangGraph/LangChain integration adapters

## Research

SchemaRouter originated from *SchemaRouter: Field-Aware Tool Routing for Efficient Heterogeneous Agentic RAG*. The framework keeps the paper's useful idea—schema-aware, field-aware planning—while correcting research-harness assumptions such as one endpoint per tool and fixture-only execution.

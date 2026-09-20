# SchemaRouter

**Schema-aware planning and execution for LLM tool ecosystems.**

SchemaRouter compiles a natural-language request plus a registered tool catalog into a small, typed, auditable execution plan. It is designed for environments where an agent may have many OpenAPI or MCP capabilities and should not expose or fetch everything by default.

> Status: **v0.1 pre-alpha**. URL-driven OpenAPI ingestion and live MCP discovery are now part of the core development branch. Model-assisted query understanding and production observability are still intentionally deferred.

## URL-first usage

For structured sources, the intended developer experience is now:

```python
from schemarouter import SchemaRouter

router = await SchemaRouter.from_url(
    "https://api.example.com/openapi.json"
)

plan = router.plan("Get user 42")
result = await router.execute(plan)
```

or for MCP:

```python
from schemarouter import SchemaRouter

router = await SchemaRouter.from_url(
    "http://localhost:8000/mcp",
    kind="mcp",
)
```

For MCP install the optional runtime:

```bash
pip install "schemarouter[mcp]"
```

`kind="auto"` first checks whether the URL is an OpenAPI 3.x JSON/YAML document and otherwise attempts MCP discovery. A normal HTML documentation page is **not** silently converted into guessed tool contracts.

This is deliberate:

```text
OpenAPI URL
   -> fetch document
   -> parse paths / operations / parameters / responses
   -> ToolSpec / EndpointSpec / FieldSpec
   -> Registry
   -> Planner
   -> HTTP executor

MCP URL
   -> connect
   -> list_tools() with pagination
   -> inputSchema / outputSchema
   -> ToolSpec / EndpointSpec / FieldSpec
   -> Registry
   -> MCP executor
```

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

## Manual registration

Manual contracts remain available when no machine-readable schema exists:

```python
from schemarouter import (
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PlanRequest,
    SchemaRouter,
    ToolSpec,
)

router = SchemaRouter()
router.add_tool(
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

plan = router.plan(
    PlanRequest(
        query="LiFePO4 band gap and formation energy",
        arguments={"formula": "LiFePO4"},
    )
)
```

The planner never invents undeclared arguments. Missing required arguments are surfaced as plan requirements instead of being silently hallucinated. Each call also carries a schema fingerprint; execution rejects a stale plan if the registered schema changed.

## Ingestion behavior

### OpenAPI

The current OpenAPI path supports:

- OpenAPI 3.x JSON or YAML URLs
- operations under `paths`
- path/query/header parameters
- JSON request-body object properties
- JSON response object fields
- local `#/...` references
- automatic HTTP execution
- trusted headers kept outside the model-visible schema

Unsupported or ambiguous constructs remain explicit instead of being guessed.

### MCP

The live MCP path uses the official Python SDK when `schemarouter[mcp]` is installed:

- URL connection
- protocol negotiation / compatibility handling by the SDK
- paginated `list_tools()`
- `inputSchema` -> endpoint parameters
- `outputSchema` -> response fields
- `call_tool()` execution
- `structured_content` preferred for projection

Remote annotations remain untrusted metadata and do not grant authorization.

## Safety and correctness invariants

- **Fail closed on schema drift:** a plan fingerprint must match the current endpoint schema before execution.
- **No argument hallucination:** only declared parameters survive planning and execution validation.
- **Namespaced tools:** registry keys are `<namespace>.<tool>` when a namespace is supplied.
- **Recall-preserving projection:** identifiers plus matched fields are retained; if no output concept is confidently matched, the planner does not aggressively prune fields.
- **Structured-source first:** URL auto-ingestion accepts OpenAPI/MCP contracts, not arbitrary HTML inference.
- **No hidden network behavior in planning:** core planning itself remains deterministic and offline.

See [`docs/architecture.md`](docs/architecture.md) for the adversarial design review and v0.1 boundaries.

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest -q
ruff check .
```

For live MCP development:

```bash
pip install -e ".[dev,mcp]"
```

## Roadmap

1. provider-neutral model-assisted `QueryAnalyzer`
2. authenticated/custom-transport MCP URL loading
3. richer OpenAPI composition/external-reference support
4. policy engine for provenance, license, permissions, cost, and destructive operations
5. HTML documentation assistant that proposes schemas for explicit user review rather than silently trusting inference
6. tracing, replay, schema-drift diagnostics, and benchmark suite
7. LangGraph/LangChain integration adapters

## Research

SchemaRouter originated from *SchemaRouter: Field-Aware Tool Routing for Efficient Heterogeneous Agentic RAG*. The framework keeps the paper's useful idea—schema-aware, field-aware planning—while correcting research-harness assumptions such as one endpoint per tool and fixture-only execution.

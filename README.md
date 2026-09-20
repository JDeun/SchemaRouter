# SchemaRouter

**Schema-aware planning and execution for LLM tool ecosystems.**

SchemaRouter compiles a natural-language request plus a registered tool catalog into a small, typed, auditable execution plan. It is designed for environments where an agent may have many OpenAPI or MCP capabilities and should not expose or fetch everything by default.

> Status: **v0.1 pre-alpha**. The core development branch includes URL-driven OpenAPI ingestion, live MCP discovery, model-assisted query analysis, grounded HTML schema proposals, runtime JSON Schema validation, fail-closed execution policy, Runnable-style execution APIs, typed Python tools, and optional LangChain integration.

## Framework interface

SchemaRouter uses one execution vocabulary across local Python tools, OpenAPI, MCP, and approved
documentation-derived tools:

```python
result = router.invoke(request)
result = await router.ainvoke(request)

results = router.batch(requests)
results = await router.abatch(requests)

for result in router.stream(request):
    ...

async for result in router.astream(request):
    ...

async for event in router.astream_events(request):
    ...
```

Per-run configuration is typed and reusable:

```python
from schemarouter import RetryPolicy, RunConfig

configured = router.with_config(
    RunConfig(
        tags=["production"],
        metadata={"service": "research-agent"},
        max_concurrency=8,
        retry=RetryPolicy(max_attempts=3),
    )
)

result = await configured.ainvoke(request)
```

Retries are read-only by default. Mutating operations are not retried unless trusted local code
explicitly opts in. Event arguments and result payloads are also redacted by default; use
`RunConfig(include_payloads=True)` only when the trace sink is trusted.

The framework exposes machine-readable `input_schema`, `output_schema`, and `config_schema`
properties for serving layers, generated UIs, tests, and integrations.

## Python tools

Normal typed Python functions can become SchemaRouter tools without manually constructing a
`ToolSpec`:

```python
from pydantic import BaseModel

from schemarouter import SchemaRouter, schema_tool

class Weather(BaseModel):
    city: str
    temperature: float

@schema_tool(read_only=True)
def current_weather(city: str) -> Weather:
    return Weather(city=city, temperature=20.5)

router = SchemaRouter()
router.add_callable(current_weather)

result = router.invoke(
    PlanRequest(
        query="city temperature",
        arguments={"city": "Seoul"},
    )
)
```

Type hints are converted to JSON Schema and remain runtime validation contracts. Ambiguous
`*args` / `**kwargs` and positional-only functions require an explicit contract instead of being
silently guessed.

## LangChain integration

LangChain is an optional integration, not a core dependency:

```bash
pip install "schemarouter[langchain]"
```

Registered SchemaRouter endpoints can be exposed as LangChain `StructuredTool` objects:

```python
from schemarouter.integrations import to_langchain_tools

tools = to_langchain_tools(router)
```

LangChain remains the surrounding orchestration surface while SchemaRouter stays authoritative for
schema fingerprints, execution policy, input/output validation, and bound invokers.

See [framework maturity](docs/framework-maturity.md) for the explicit comparison with mature agent
frameworks.

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

## Model-assisted natural-language planning

The default `KeywordAnalyzer` is deterministic and offline. For natural-language parameter and
field extraction, inject a provider-neutral callable:

```python
from schemarouter import ModelQueryAnalyzer, SchemaRouter

async def my_model(payload: dict) -> dict:
    # Bridge this payload to any structured-output LLM provider.
    # Return JSON matching payload["response_schema"].
    return {
        "preferred_tools": ["users_api"],
        "preferred_endpoints": ["users_api.get_user"],
        "arguments": {"user_id": "42"},
        "fields": ["name", "email"],
        "concepts": [],
        "evidence": {},
    }

router = await SchemaRouter.from_url(
    "https://api.example.com/openapi.json",
    analyzer=ModelQueryAnalyzer(my_model),
)

plan = await router.aplan("42번 사용자의 이름과 이메일을 알려줘")
result = await router.arun("42번 사용자의 이름과 이메일을 알려줘")
```

Model output is never used as an executable contract directly. SchemaRouter projects it back onto
the current registry:

```text
LLM output
  -> validate JSON shape
  -> drop unknown tools
  -> drop unknown endpoints
  -> drop undeclared parameters
  -> drop unknown response fields
  -> merge explicit caller arguments with higher priority
  -> deterministic planner
  -> execution validation
```

Descriptions from remote OpenAPI/MCP sources are treated as untrusted data. The model is explicitly
instructed not to follow instructions embedded in descriptions.

## Human-readable API documentation

A normal HTML documentation page is not silently trusted as an executable schema. Use
`inspect_url()` to create an evidence-grounded proposal first:

```python
from schemarouter import SchemaRouter

async def documentation_model(payload: dict) -> dict:
    # Bridge to a structured-output LLM provider.
    # Every endpoint, parameter, and field must include exact evidence quotes.
    ...

router = SchemaRouter()

proposal = await router.inspect_url(
    "https://docs.example.com/api",
    model=documentation_model,
)

print(proposal.status)
print(proposal.grounding_score)
print(proposal.rejected_items)
```

SchemaRouter strips scripts/styles, treats page text as untrusted data, and verifies each model
quote against the fetched document. Hallucinated endpoints, parameters, or fields without a
matching quote are rejected.

A proposal remains non-executable until explicit approval:

```python
router.approve_proposal(
    proposal,
    base_url="https://api.example.com",
    min_grounding_score=0.8,
)
```

Approval has additional runtime gates:

- proposals below the grounding threshold are rejected;
- POST/PUT/PATCH/DELETE require `allow_mutations=True`;
- the API base URL must be supplied explicitly rather than inferred from the docs URL;
- credentials cannot be embedded in the URL and must stay in trusted runtime auth;
- only after approval is the HTTP invoker bound to the registry.

This makes the unstructured path:

```text
HTML docs
  -> text extraction
  -> structured model proposal
  -> exact-quote grounding
  -> non-executable SchemaProposal
  -> explicit human/application approval
  -> registry + HTTP executor
```

Current limitation: client-rendered documentation whose API details are absent from the initial
HTML response may need a future browser/rendering adapter.

## Execution policy and trust boundaries

Schema discovery and execution authority are intentionally separate.

For OpenAPI documents, a same-origin API server can be bound automatically. If the document points
to a different origin, SchemaRouter imports the schema but **does not bind an executor** until the
caller explicitly approves the runtime base URL:

```python
router = await SchemaRouter.from_url(
    "https://docs.example.com/openapi.json"
)

router.bind_openapi(
    "users_api",
    base_url="https://api.example.com",
    trusted_headers={"Authorization": "Bearer ..."},
)
```

Documentation credentials and API runtime credentials are also separate:

```python
router = await SchemaRouter.from_url(
    "https://docs.example.com/openapi.json",
    schema_headers={"X-Docs-Token": "..."},
    trusted_headers={"Authorization": "Bearer ..."},
    base_url="https://api.example.com",
)
```

- `schema_headers` are sent only while fetching the schema document.
- schema redirects are limited to the original origin.
- `trusted_headers` are never exposed as model-selected parameters.
- sensitive headers such as `Authorization`, `Cookie`, and `Host` cannot be supplied through
  tool arguments.
- runtime HTTP redirects are disabled.
- path parameters are encoded and cannot escape the approved API origin/base path.

Execution has a second local policy gate:

```python
from schemarouter import ExecutionPolicy, SchemaRouter

router = SchemaRouter(
    policy=ExecutionPolicy(
        allow_mutations=True,
        allow_destructive=False,
        allow_unclassified_remote=False,
    )
)
```

The default policy allows normal manual/local contracts, but blocks:

- known OpenAPI mutations such as POST/PUT/PATCH;
- destructive operations such as DELETE;
- remote MCP operations whose side effects cannot be trusted from remote annotations alone.

These permissions can only be raised by trusted local application code. A model or remote schema
cannot grant itself execution authority.

### JSON Schema validation

Arguments are validated immediately before invocation and raw tool output is validated immediately
after invocation, before response-field projection. Type, enum, range, pattern, required-property,
and other supported JSON Schema constraints therefore remain runtime contracts rather than prompt
instructions.

MCP `inputSchema` and `outputSchema` are preserved as endpoint contracts. OpenAPI parameter and
response schemas are also retained. Schema changes alter the endpoint/tool fingerprint, invalidating
stale plans and stale invoker bindings.

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
- same-origin automatic HTTP binding
- explicit `bind_openapi()` / `base_url` approval for cross-origin servers
- separate schema-fetch and runtime authentication headers
- JSON Schema argument and output validation

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

Remote annotations remain untrusted metadata and do not grant authorization. Because MCP
annotations are not treated as trusted side-effect policy, remote MCP execution is blocked by
default unless the caller opts into `allow_unclassified_remote=True` or supplies a future trusted
local classification layer.

## Safety and correctness invariants

- **Fail closed on schema drift:** a plan fingerprint must match the current endpoint schema before execution.
- **Fail closed on binding drift:** replacing a tool schema invalidates an older bound invoker.
- **Runtime JSON Schema validation:** arguments and raw outputs are validated around invocation.
- **No argument hallucination:** only declared parameters survive planning and execution validation.
- **Local authority only:** remote metadata and model output cannot grant mutation/destructive permissions.
- **Credential separation:** schema-fetch secrets and runtime API secrets use different channels.
- **Origin confinement:** cross-origin schema redirects and unapproved API origins are blocked.
- **Namespaced tools:** registry keys are `<namespace>.<tool>` when a namespace is supplied.
- **Recall-preserving projection:** ambiguous/no-match output selection favors recall over aggressive pruning.
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

1. authenticated/custom-transport MCP URL loading with trusted local side-effect classification
2. richer OpenAPI composition, nested schemas, and external-reference support
3. callback/exporter and OpenTelemetry-compatible tracing
4. policy extensions for provenance, license, cost, quotas, and per-call approval
5. multi-page and client-rendered documentation discovery
6. replay, compatibility benchmarks, and LangGraph-native integration

Release expectations and compatibility rules live in
[`docs/versioning.md`](docs/versioning.md) and
[`docs/release-checklist.md`](docs/release-checklist.md).

## Research

SchemaRouter originated from *SchemaRouter: Field-Aware Tool Routing for Efficient Heterogeneous Agentic RAG*. The framework keeps the paper's useful idea—schema-aware, field-aware planning—while correcting research-harness assumptions such as one endpoint per tool and fixture-only execution.

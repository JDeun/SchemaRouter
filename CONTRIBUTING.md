# Contributing to SchemaRouter

SchemaRouter is a focused schema-aware planning and execution layer. Contributions should extend
that boundary without turning the project into a second general-purpose agent framework.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest -q -m "not mcp_integration"
python examples/quickstart.py

# Check the complete typed surface and optional integrations.
pip install -e ".[dev,mcp,langchain,langgraph,llamaindex,jev,otel]"
pyright
pytest -q --cov=schemarouter --cov-branch --cov-report=term-missing
```

Optional integrations have separate extras and focused tests. The required CI exercises
LangChain/LangGraph, LlamaIndex, Jev/TypeSafe, Laya, MCP, and OpenTelemetry independently in
addition to the full coverage run. Laya has a separate CPU-only CI setup because its PyTorch
dependency is intentionally not installed into the ordinary development environment.

## Design rules

Changes must preserve these principles:

1. remote metadata describes capability but never grants execution authority;
2. model output is untrusted until projected onto registered schemas;
3. credentials remain outside model-visible arguments;
4. schema and invoker drift fail closed;
5. raw input/output values are validated before crossing the trusted execution boundary;
6. mutations, destructive calls, and ambiguous remote side effects require local policy;
7. observability must not expose payloads by default;
8. integrations must call through SchemaRouter execution rather than bypassing it;
9. installed adapter plugins must never be auto-imported from discovery alone;
10. approval and execution-budget failures must remain fail-closed.

## Adding an adapter

Adapters should produce normal `ToolSpec` / `EndpointSpec` contracts and a trusted invoker.
See [adapter authoring](https://jdeun.github.io/SchemaRouter/adapter-authoring/).

Do not embed provider-specific authorization decisions into generic schema parsing.

## Adding a framework integration

Integrations belong under `schemarouter.integrations` and should use optional dependencies with
lazy imports. The core package must remain importable without integration extras installed.

An integration should expose SchemaRouter contracts to another ecosystem; it should not duplicate
SchemaRouter planning, policy, schema validation, or transport authorization.

## Brand changes

Production brand assets live under `docs/assets/brand/`. Treat the SVG files as the source of truth.

Brand changes should preserve the brace + routing-hub concept, graphite/teal palette, light/dark
contrast, and compact-mark legibility. Do not replace production SVGs with raster-only generated
artwork.

See the [brand guide](https://jdeun.github.io/SchemaRouter/project/brand/).

## Pull requests

A change is not complete until:

- tests cover its public behavior and adversarial failure cases;
- warnings remain clean;
- supported Python versions pass, including the Windows smoke surface;
- Pyright and the 84% branch-coverage floor pass;
- minimum declared runtime dependencies remain usable;
- wheel and sdist clean-install smokes pass;
- public behavior is documented;
- new optional dependencies are isolated behind extras;
- breaking API changes include a changelog and migration note.

See [versioning](https://jdeun.github.io/SchemaRouter/versioning/) and the
[release checklist](https://jdeun.github.io/SchemaRouter/release-checklist/).

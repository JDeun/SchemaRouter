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
pip install -e ".[dev,mcp,langchain,llamaindex,jev]"
pyright
pytest -q --cov=schemarouter --cov-branch --cov-report=term-missing
```

Optional integrations have separate extras and focused tests. The required CI exercises
LangChain, LlamaIndex, Jev/TypeSafe, and MCP independently in addition to the full coverage run.

## Design rules

Changes must preserve these principles:

1. remote metadata describes capability but never grants execution authority;
2. model output is untrusted until projected onto registered schemas;
3. credentials remain outside model-visible arguments;
4. schema and invoker drift fail closed;
5. raw input/output values are validated before crossing the trusted execution boundary;
6. mutations, destructive calls, and ambiguous remote side effects require local policy;
7. observability must not expose payloads by default;
8. integrations must call through SchemaRouter execution rather than bypassing it.

## Adding an adapter

Adapters should produce normal `ToolSpec` / `EndpointSpec` contracts and a trusted invoker.
See [adapter authoring](adapter-authoring.md).

Do not embed provider-specific authorization decisions into generic schema parsing.

## Adding a framework integration

Integrations belong under `schemarouter.integrations` and should use optional dependencies with
lazy imports. The core package must remain importable without integration extras installed.

An integration should expose SchemaRouter contracts to another ecosystem; it should not duplicate
SchemaRouter planning, policy, schema validation, or transport authorization.

## Pull requests

A change is not complete until:

- tests cover its public behavior and adversarial failure cases;
- warnings remain clean;
- supported Python versions pass, including the Windows smoke surface;
- Pyright and the 82% branch-coverage floor pass;
- minimum declared runtime dependencies remain usable;
- wheel and sdist clean-install smokes pass;
- public behavior is documented;
- new optional dependencies are isolated behind extras;
- breaking API changes include a changelog and migration note.

See [versioning](versioning.md) and the [release checklist](release-checklist.md).

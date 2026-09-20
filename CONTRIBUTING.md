# Contributing to SchemaRouter

SchemaRouter is a focused schema-aware planning and execution layer. Contributions should extend
that boundary without turning the project into a second general-purpose agent framework.

## Development setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
ruff check .
pytest -q
python examples/quickstart.py
```

Optional integrations have separate extras and tests. For example:

```bash
pip install -e ".[dev,langchain]"
pytest -q tests/test_langchain_integration.py
```

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
See [adapter authoring](docs/adapter-authoring.md).

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
- supported Python versions pass;
- public behavior is documented;
- new optional dependencies are isolated behind extras;
- breaking API changes include a changelog and migration note.

See [versioning](docs/versioning.md) and the [release checklist](docs/release-checklist.md).

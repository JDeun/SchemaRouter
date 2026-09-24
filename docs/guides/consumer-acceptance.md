# Consumer acceptance validation

SchemaRouter keeps a small end-to-end acceptance suite in
`scripts/consumer_acceptance.py`. It is deliberately separate from the unit and adapter contract
tests: the script uses only the public package surface and is designed to run against an installed
wheel or sdist as if it were a downstream application.

The suite exercises the following production boundaries:

- normal Python-tool planning and execution;
- default mutation denial and trusted approval gating;
- schema-drift and invoker-binding-drift fail-closed behavior;
- runtime output JSON Schema validation;
- read-only retry behavior and elapsed-time execution budgets;
- SQLite registry persistence;
- redacted run-trace persistence;
- read-only inspection/dashboard generation;
- installed `schemarouter inspect` and `schemarouter dashboard` CLI execution against persisted SQLite artifacts.

Run it locally with:

```bash
python scripts/consumer_acceptance.py
```

To retain a machine-readable report:

```bash
python scripts/consumer_acceptance.py --json-out artifacts/consumer-acceptance.json
```

## CI coverage

The same script runs on the supported Linux Python matrix, the Windows smoke job, the
minimum-dependency job, and again from clean wheel and sdist virtual environments.

The package job also installs the built wheel through its lightweight optional extras:
`mcp`, `langchain`, `langgraph`, `llamaindex`, `jev`, and `otel`. It runs a no-network
SDK/import smoke for MCP, Jev, and OpenTelemetry and executes the LangChain, LangGraph, and
LlamaIndex runnable examples. It then exercises the installed inspection CLI against the SQLite
registry/trace artifacts created by the end-to-end example, validates the emitted JSON, and exports
a dashboard through the installed console script. This catches packaging-metadata,
optional-dependency, and CLI-entry-point regressions that editable installs cannot detect. Laya
remains in its dedicated CPU integration job because its PyTorch dependency is intentionally handled
separately.

Public OpenAPI and OPTIMADE compatibility smokes remain separate because they depend on external
services. Those checks install the current source tree non-editably, run `pip check`, call the
public services, and retain machine-readable artifacts. They are intentionally not treated as
deterministic package acceptance gates.

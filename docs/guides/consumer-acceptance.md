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
- read-only inspection/dashboard generation.

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

The package job also installs the built wheel through its declared
`langchain`, `langgraph`, and `llamaindex` extras and executes the corresponding runnable
examples. This catches packaging-metadata or optional-dependency regressions that editable installs
cannot detect.

Public OpenAPI and OPTIMADE compatibility smokes remain separate because they depend on external
services. Those scheduled checks produce retained machine-readable artifacts but are intentionally
not treated as deterministic package acceptance gates.

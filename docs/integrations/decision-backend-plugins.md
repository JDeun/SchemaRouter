# Decision backend plugins

SchemaRouter can load third-party bounded decision backends from installed Python packages without
adding a model-specific integration to SchemaRouter core.

This is intended for decision-model families whose runtime/API is not already covered by a stable
built-in transport such as `SystemOneDecisionBackend`.

## Entry-point contract

A plugin package registers one entry point in `pyproject.toml`:

```toml
[project.entry-points."schemarouter.decision_backends"]
anyjev = "schemarouter_anyjev:create_backend"
```

The entry point may resolve to:

- a backend class;
- a factory callable;
- a preconstructed object exposing `decide(request)`.

A class or factory can receive explicit keyword configuration when loaded.

## Discovery is metadata-only

```python
from schemarouter import discover_decision_backend_plugins

for plugin in discover_decision_backend_plugins():
    print(plugin.name, plugin.distribution, plugin.version)
```

Discovery does **not** import or execute plugin code.

## Explicit loading

```python
from schemarouter import load_decision_backend_plugin

backend = load_decision_backend_plugin(
    "anyjev",
    config={
        "model": "example/model",
        "device": "cuda",
    },
)
```

Only the exact named plugin is imported. Loading a plugin executes trusted installed Python code;
SchemaRouter does not auto-load all installed decision plugins.

The returned backend still participates in the normal bounded-decision contract. Any selected option
ID is validated against the finite IDs offered by SchemaRouter before it can influence planning.

## Benchmark a plugin without editing SchemaRouter

The shared decision benchmark can load the same installed plugin:

```bash
export SCHEMAROUTER_DECISION_PLUGIN_CONFIG='{"model":"example/model","device":"cpu"}'

python scripts/benchmark_decision_routing.py \
  --corpus benchmarks/decision-routing-v1.json \
  --decision-plugin anyjev \
  --decision-recall-on-empty
```

Use `--decision-plugin-config-env NAME` to select a different configuration environment variable.

Benchmark reports record:

- plugin name;
- package distribution/version when discoverable;
- configuration **keys**;
- the name of the environment variable used for configuration.

Configuration values are not written to benchmark output. Plugins that need secrets should preferably
read their provider credential from a dedicated environment variable rather than accepting the raw
secret as ordinary benchmark metadata.

## Which extension path to use

Use the narrowest stable interface that fits the model:

1. **System One wire-compatible model** — use `SystemOneDecisionBackend` and change
   `base_url/model/provider_name`.
2. **One-off research callable** — use `CallableDecisionBackend` or
   `--decision-callable module:function`.
3. **Reusable third-party integration** — publish a
   `schemarouter.decision_backends` entry-point plugin.

This keeps model churn outside SchemaRouter's planning and authority model.

## Quality is separate from compatibility

An installed plugin is not automatically a recommended router. Before replacing a production model,
run the same frozen workload and compare exact routing, unsupported rejection, false-route rate,
latency, errors, and authority violations.

A provider can supply semantic evidence, but registered local schema and SchemaRouter validation
remain the execution authority.

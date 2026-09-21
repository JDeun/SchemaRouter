# Third-party adapter plugins

SchemaRouter supports installed third-party source adapters through Python entry points.

Plugin loading is deliberately **opt-in** because importing an installed entry point executes local
Python code.

## Package an adapter

A third-party package can declare:

```toml
[project.entry-points."schemarouter.adapters"]
graphql = "my_package.adapters:GraphQLAdapter"
```

The resolved object must satisfy the normal `SourceAdapter` contract:

```python
class GraphQLAdapter:
    kind = "graphql"
    priority = 50

    async def load(self, context):
        ...
```

An adapter instance, adapter class, or zero-argument factory is accepted.

## Discover without importing

```python
from schemarouter import discover_adapter_plugins

for plugin in discover_adapter_plugins():
    print(plugin.name, plugin.value, plugin.distribution, plugin.version)
```

Discovery reads entry-point metadata only. It does not call `EntryPoint.load()`.

## Load explicitly

```python
router.load_adapter_plugins(
    allowlist={"graphql"},
)
```

or:

```python
from schemarouter import AdapterRegistry, load_adapter_plugins

registry = AdapterRegistry()
load_adapter_plugins(
    registry,
    allowlist={"graphql"},
)
```

An empty allowlist is rejected. Unknown requested names fail before any plugin is imported.

## Security model

Treat adapter plugins like any other installed application dependency. They execute with the Python
process's privileges once explicitly loaded.

SchemaRouter therefore does not:

- auto-import every plugin it discovers;
- accept a wildcard/implicit allow-all mode;
- let remote schema content request plugin loading;
- let a planner or model choose which installed package to import.

After loading, the adapter still uses the same registry, policy, schema validation, and binding-drift
boundaries as built-in adapters.

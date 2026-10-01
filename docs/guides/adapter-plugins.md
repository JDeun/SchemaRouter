# Third-party adapter plugins

SchemaRouter supports installed third-party source adapters through Python entry points.

Plugin loading is **opt-in** because importing an installed entry point executes local
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

## Runnable external-package example

The repository includes a tiny package that is deliberately separate from the
`schemarouter` distribution:

```bash
python -m pip install -e examples/adapter_plugin_demo
python examples/adapter_plugin_quickstart.py
```

Its package metadata declares a real entry point:

```toml
[project.entry-points."schemarouter.adapters"]
demo_static = "schemarouter_demo_adapter:DemoStaticAdapter"
```

The quickstart checks the trust boundary directly:

1. `discover_adapter_plugins()` sees the entry-point metadata while
   `schemarouter_demo_adapter` is still absent from `sys.modules`;
2. `router.load_adapter_plugins(allowlist={"demo_static"})` explicitly imports and registers it;
3. `router.add_url(..., kind="demo_static")` compiles a normal `ToolSpec` and trusted invoker;
4. normal planning, argument/output validation, field projection, and execution return
   `{"value": 5}`.

The source URL is `example.invalid` and the adapter never performs network I/O. The URL exists only
to demonstrate that a plugin can recognize a structured source identifier while keeping the demo
deterministic.

Source:
[`examples/adapter_plugin_demo/`](https://github.com/JDeun/SchemaRouter/tree/main/examples/adapter_plugin_demo)

## Downstream installed-wheel compatibility smoke

Required package CI also exercises the plugin from a **separate clean virtual environment**:

1. build the SchemaRouter wheel;
2. install that wheel into a fresh venv;
3. install `examples/adapter_plugin_demo` as a separate distribution with its real
   `schemarouter.adapters` entry point;
4. run `scripts/downstream_adapter_plugin_smoke.py`.

The smoke asserts that SchemaRouter was imported from the venv's `site-packages`, not from the
repository source tree. It then proves that metadata discovery does not import plugin code, explicit
allowlisting does import exactly the requested plugin, valid execution succeeds, an input violating
the registered JSON Schema is rejected, and a trusted local deny rule still blocks the
plugin-supplied invoker.

This is a **downstream compatibility and authority-boundary smoke**, not a provider-quality,
routing-accuracy, or performance benchmark. It uses no network access and no credentials.

## Security model

Treat adapter plugins like any other installed application dependency. They execute with the Python
process's privileges once explicitly loaded.

SchemaRouter does not:

- auto-import every plugin it discovers;
- accept a wildcard/implicit allow-all mode;
- let remote schema content request plugin loading;
- let a planner or model choose which installed package to import.

After loading, the adapter still uses the same registry, policy, schema validation, and binding-drift
boundaries as built-in adapters.

## Protocol-specific recipes

For STAC, gRPC/Protobuf, SOAP/WSDL, and bounded AsyncAPI request/reply cases, see
[Protocol plugin recipes](protocol-plugin-recipes.md). The recipes explain when to prefer OpenAPI
or typed Python wrappers, when a SourceAdapter plugin adds real value, and which streaming/event
lifecycles must stay outside the ordinary ToolCall abstraction.

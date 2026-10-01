# LlamaIndex integration

SchemaRouter can expose registered endpoints as LlamaIndex tools while retaining SchemaRouter's
schema validation and execution boundary.

## Install

For consumers, install the published optional extra:

```bash
pip install "schemarouter[llamaindex]"
```

The bridge is included in the published `0.3.0` release.

For repository development:

```bash
pip install -e ".[dev,llamaindex]"
```

## Import existing LlamaIndex tools

LlamaIndex `BaseTool` / `FunctionTool`-like objects can also be registered directly:

```python
router = SchemaRouter()
key = router.add_llamaindex_tool(
    llama_tool,
    provider="scholarly-search",
    read_only=True,
    remote=True,
)
```

SchemaRouter reads `ToolMetadata.get_parameters_dict()` or the declared `fn_schema` for the
input contract. For typed `FunctionTool` objects, a declared return annotation is preserved as an
output JSON Schema when it can be represented safely.

Typed list results use the same record-preserving item-field contract as native adapters. A typed
`results: list[Hit]` return can expose fields such as `results[].title` when the return schema
declares those item properties.

The imported tool remains subject to SchemaRouter policy, fingerprints, validation, fallback,
health, and observability. Tool metadata does not grant execution authority.

## Export registered endpoints

Convert one endpoint or a selected catalog:

```python
from schemarouter.integrations import to_llamaindex_tool, to_llamaindex_tools

tool = to_llamaindex_tool(router, "materials", "search")
tools = to_llamaindex_tools(router)
```

## Runnable example

The repository includes a minimal executable integration example:

```bash
python examples/llamaindex_quickstart.py
```

CI runs this example together with the integration contract tests.

## Execution boundary

The adapter is thin. LlamaIndex is responsible for agent/workflow orchestration;
SchemaRouter is responsible for registered schema identity, policy, validation, binding checks,
and endpoint execution.

The bridge does not grant LlamaIndex metadata authority over SchemaRouter execution policy.

## Packaging

The bridge currently stays in the main distribution behind the `llamaindex` extra. A separate
package should be created only if the integration needs its own release cadence, materially expands
dependency pressure, or upstream maintainers require a dedicated distribution.

See [Compatibility testing](../compatibility.md) for the supported range and maintenance policy.

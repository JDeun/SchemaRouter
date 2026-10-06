# LlamaIndex integration

SchemaRouter can expose registered endpoints as LlamaIndex tools while retaining SchemaRouter's
schema validation and execution boundary.

## Install

For consumers, install the published optional extra:

```bash
pip install "schemarouter[llamaindex]"
```

The bridge ships in the current SchemaRouter distribution behind the optional `llamaindex` extra.

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

With enterprise authorization enabled, export with a trusted principal:

```python
from schemarouter import PrincipalContext, RunConfig

employee = PrincipalContext(
    subject="alice",
    roles=("employee",),
    attributes={"department": "sales"},
)

tools = to_llamaindex_tools(
    router,
    run_config=RunConfig(principal=employee),
)
```

The exported catalog contains only principal-visible endpoints. DataScope projection removes hidden
fields/parameters from the LlamaIndex-visible schema, and calls re-enter
`SchemaRouter.execute(..., config=...)` so authorization and trusted data filters are enforced
again at execution.

## Live export contract

A `FunctionTool` captures the authorized endpoint schema visible at export time. Immediately
before each call, SchemaRouter resolves and authorizes the endpoint again. If the endpoint schema,
tool fingerprint, or authorized DataScope projection changed, invocation fails with
`StaleExportedToolError` before execution.

Re-export with `to_llamaindex_tool(...)` or rebuild the catalog with
`to_llamaindex_tools(...)` after schema refreshes or authorization-policy changes. The exported
LlamaIndex schema is therefore never silently rebound to a different live capability.

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

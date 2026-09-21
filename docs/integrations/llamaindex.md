# LlamaIndex integration

SchemaRouter can expose registered endpoints as LlamaIndex tools while retaining SchemaRouter's
schema validation and execution boundary.

## Install

The LlamaIndex bridge is currently on unreleased `main`. Install it from a repository checkout:

```bash
pip install -e ".[llamaindex]"
```

After the next package release, the packaged extra will be `schemarouter[llamaindex]`.

For repository development:

```bash
pip install -e ".[dev,llamaindex]"
```

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

The adapter is intentionally thin. LlamaIndex remains responsible for agent/workflow orchestration;
SchemaRouter remains responsible for registered schema identity, policy, validation, binding checks,
and endpoint execution.

The bridge does not grant LlamaIndex metadata authority over SchemaRouter execution policy.

## Packaging

The bridge currently stays in the main distribution behind the `llamaindex` extra. A separate
package should be created only if the integration needs its own release cadence, materially expands
dependency pressure, or upstream maintainers require a dedicated distribution.

See [Compatibility testing](../compatibility.md) for the supported range and maintenance policy.

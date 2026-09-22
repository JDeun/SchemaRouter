# LangChain

SchemaRouter integrates with LangChain as an optional boundary, not as a replacement for the
LangChain runtime.

## Install

For consumers:

```bash
pip install --pre "schemarouter[langchain]"
```

For repository development:

```bash
pip install -e ".[dev,langchain]"
```

The core package does not depend on LangChain.

## Export registered endpoints

```python
from schemarouter.integrations import to_langchain_tools

tools = to_langchain_tools(router)
```

Each registered endpoint becomes a LangChain `StructuredTool` with its SchemaRouter input schema.

To expose one endpoint:

```python
from schemarouter.integrations import to_langchain_tool

tool = to_langchain_tool(
    router,
    "weather",
    "current",
)
```

## Runnable example

The repository includes a minimal executable integration example:

```bash
python examples/langchain_quickstart.py
```

CI runs this example in addition to the dedicated integration tests, so the documented bridge is
kept executable.

## Execution still flows through SchemaRouter

The integration does **not** call the original transport directly.

```text
LangChain StructuredTool
 -> SchemaRouter ToolCall
 -> current schema validation
 -> ExecutionPolicy
 -> binding-drift check
 -> trusted invoker
 -> output validation
```

This means a LangChain agent gains the same fail-closed contracts as direct SchemaRouter usage.

## Division of responsibility

A useful composition is:

| Concern | Owner |
| --- | --- |
| Agent graph / conversation | LangChain or LangGraph |
| Model invocation | Surrounding framework/application |
| Tool catalog schema | SchemaRouter |
| Endpoint/argument/field plan | SchemaRouter |
| Side-effect policy | SchemaRouter local policy |
| Tool execution validation | SchemaRouter |
| Checkpointing / memory | Surrounding framework |

SchemaRouter should not duplicate the graph runtime merely to integrate with it.

## Packaging

The bridge currently stays in the main distribution behind the `langchain` extra. A separate
`langchain-schemarouter` package is intentionally deferred until an independent release cadence,
material dependency pressure, or an upstream ecosystem requirement justifies the split.

See [Compatibility testing](../compatibility.md) for the supported range and maintenance policy.

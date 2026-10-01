# LangChain

SchemaRouter integrates with LangChain as an optional boundary, not as a replacement for the
LangChain runtime.

## Install

For consumers:

```bash
pip install "schemarouter[langchain]"
```

For repository development:

```bash
pip install -e ".[dev,langchain]"
```

The core package does not depend on LangChain.

## Import existing LangChain tools

Existing LangChain `BaseTool` / `StructuredTool` objects can be compiled into SchemaRouter's
canonical capability model and bound to the normal execution pipeline:

```python
from langchain_community.tools import DuckDuckGoSearchRun
from schemarouter import SchemaRouter

router = SchemaRouter()
key = router.add_langchain_tool(
    DuckDuckGoSearchRun(),
    provider="duckduckgo",
    read_only=True,
    remote=True,
)
```

The importer reads the tool's declared input schema and, when available, its declared output schema.
Structured result lists keep their record shape: a declared `results: list[{title, url}]` can expose
`results[].title` and `results[].url` rather than collapsing the values into unrelated arrays.
It does **not** infer read/write authority from the tool description. `read_only`, `destructive`,
`remote`, `provider`, and `access_mode` remain trusted local classification.

This makes existing LangChain ecosystem tools usable as SchemaRouter capabilities without creating a
service-specific SchemaRouter adapter for every provider. Examples include web search, scholarly
search, finance, databases, and SaaS tools already represented as LangChain tools.

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

For direct `StateGraph` integration, see [LangGraph](langgraph.md).

## Packaging

The bridge currently stays in the main distribution behind the `langchain` extra. A separate
`langchain-schemarouter` package is deferred until an independent release cadence,
material dependency pressure, or an upstream ecosystem requirement justifies the split.

See [Compatibility testing](../compatibility.md) for the supported range and maintenance policy.

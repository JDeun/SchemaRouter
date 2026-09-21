# LlamaIndex integration

SchemaRouter can expose registered endpoints as LlamaIndex tools while retaining SchemaRouter's
schema validation and execution boundary.

Install the optional integration:

```bash
pip install "schemarouter[llamaindex]"
```

Then convert one endpoint or a selected catalog:

```python
from schemarouter.integrations import to_llamaindex_tool, to_llamaindex_tools

tool = to_llamaindex_tool(router, "materials", "search")
tools = to_llamaindex_tools(router)
```

The adapter is intentionally thin. LlamaIndex remains responsible for agent/workflow orchestration;
SchemaRouter remains responsible for registered schema identity, validation, and endpoint execution.

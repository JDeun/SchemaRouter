# MCP agent boundary

This pattern is useful when an application discovers capabilities from an MCP server but does not
want remote annotations to become authorization.

```python
from schemarouter import ExecutionPolicy, PlanRequest, SchemaRouter

router = await SchemaRouter.from_url(
    "http://localhost:8000/mcp",
    kind="mcp",
    policy=ExecutionPolicy(
        allow_unclassified_remote=True,
    ),
)

results = await router.ainvoke(
    PlanRequest(
        query="add result",
        arguments={"a": 2, "b": 3},
    )
)
```

## Production note

`allow_unclassified_remote=True` is intentionally broad. A production deployment with mixed read and
write MCP tools should prefer a future trusted local classification layer or separate servers by
authority domain.

The current design deliberately refuses to trust a remote server's own annotations as the final
side-effect decision.

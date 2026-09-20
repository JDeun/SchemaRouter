# Quickstart

This page uses the same source file that CI executes. If the public API changes and the example
breaks, the build should fail instead of allowing stale documentation to survive.

## 1. Define a typed tool

--8<-- "examples/quickstart.py"

The function annotation becomes a JSON Schema contract. The decorator adds local execution metadata;
it does not replace runtime validation.

## 2. Register the callable

`router.add_callable(current_weather)` performs four operations:

1. derives the input and output schemas from Python types;
2. creates a `ToolSpec` with one `EndpointSpec`;
3. registers a versioned schema snapshot;
4. binds the original callable as the trusted invoker.

## 3. Invoke through a PlanRequest

```python
from schemarouter import PlanRequest

request = PlanRequest(
    query="city temperature",
    arguments={"city": "Seoul"},
)

results = router.invoke(request)
```

The planner never invents an undeclared argument. Before the callable is invoked, the executor
re-validates required arguments and the effective JSON Schema.

## 4. Use async, batch, or streaming

```python
result = await router.ainvoke(request)

results = await router.abatch([request, request])

async for result in router.astream(request):
    print(result)

async for event in router.astream_events(request):
    print(event.event, event.tool, event.endpoint)
```

Event payloads are redacted by default.

## Next

Choose an ingestion path for your real capability:

- [Python tools](../guides/python-tools.md)
- [OpenAPI](../guides/openapi.md)
- [MCP](../guides/mcp.md)
- [Human-readable documentation](../guides/html-documentation.md)

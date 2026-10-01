# Runtime lifecycle

`SchemaRouter` owns the background tasks it starts for health monitoring and schema watching.
Use `aclose()` during application shutdown, or use the router as an async context manager:

```python
from schemarouter import SchemaRouter

async with SchemaRouter() as router:
    await router.start_health_monitor()
    await router.start_schema_watcher()
    # use the router
```

Leaving the context calls `await router.aclose()`. Shutdown is idempotent and attempts to stop both
background managers even if one shutdown path reports an error.

## Resource ownership

`aclose()` stops only resources owned by the router lifecycle:

- the `AccessHealthMonitor` background task;
- the `SchemaWatchManager` background task.

It deliberately does **not** close caller-owned resources, including:

- an injected `httpx.AsyncClient`;
- an injected registry such as `SQLiteRegistry`;
- SDK clients, MCP factories/transports, subprocess handles, or other trusted invokers;
- caller-owned trace stores.

Applications remain responsible for closing those resources according to their own ownership model.
SchemaRouter adapters that create short-lived HTTP clients internally already close them within the
individual operation that created them.

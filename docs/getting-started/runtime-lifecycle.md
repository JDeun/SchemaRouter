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

Leaving the context calls `await router.aclose()`. Shutdown is idempotent and attempts to stop all
router-owned background tasks even if one shutdown path reports an error.

## Resource ownership

`aclose()` stops only resources owned by the router lifecycle:

- the `AccessHealthMonitor` background task;
- the `SchemaWatchManager` background task;
- the process-local native schema watcher started by `start_native_schema_watcher()`;
- the bounded synchronous offload worker pool used by explicitly offloaded invokers and sync health probes.

It deliberately does **not** close caller-owned resources, including:

- an injected `httpx.AsyncClient`;
- an injected registry such as `SQLiteRegistry`;
- SDK clients, MCP factories/transports, subprocess handles, or other trusted invokers;
- caller-owned trace stores.

Applications remain responsible for closing those resources according to their own ownership model.
SchemaRouter adapters that create short-lived HTTP clients internally already close them within the
individual operation that created them. Closing the router prevents new sync offloads; a Python
thread that was already executing cannot be forcibly stopped and may finish after `aclose()` returns.


## Synchronous and asynchronous loop ownership

Synchronous SchemaRouter wrappers use one long-lived internal event loop instead of creating a new
`asyncio.run()` loop for every call. Reusing one router through synchronous APIs is therefore safe
after internal watcher or health-monitor locks have seen contention, and synchronous calls from
multiple application threads are serialized onto the same loop-affine runtime.

Loop-affine lifecycle state still has one owner. If a health monitor or schema watcher is first used
from an application's async event loop, later routing that same lifecycle state through a synchronous
wrapper is unsupported and raises a clear `RuntimeError`. The reverse mixed-mode transition is
rejected for the same reason. Use the async APIs consistently for async applications, the synchronous
wrappers consistently for synchronous applications, or separate `SchemaRouter` instances when both
ownership models are required.

Synchronous schema-watch registration and removal remain safe while a watcher is running: wake-ups
are marshalled onto the owning event loop instead of mutating an `asyncio.Event` from another thread.


## Native schema watcher failure isolation

Native database/vector/document/graph refreshers are process-local because they retain trusted
client or connection state. When `start_native_schema_watcher()` is running, each registered native
source is refreshed independently. An unexpected exception from one source is recorded for that
source and does not terminate the watcher or prevent other sources from being checked. Cancellation
is never converted into a source failure, so `stop_native_schema_watcher()` and `aclose()` still
stop promptly.

Failed sources retry on the next configured watcher interval. The loop always sleeps between cycles,
so a persistently failing source cannot create a tight retry loop.

Use `native_schema_watch_snapshots()` or `router.inspect().execution.native_schema_watches` to
observe the privacy-safe state. Snapshots contain only the tool key, status, timestamps, last action,
exception **type**, and bounded counters. Exception messages, credentials, client objects, and
connection state are not retained. A deterministic `pending_review` result is reported as a normal
watch result rather than as a refresh failure.

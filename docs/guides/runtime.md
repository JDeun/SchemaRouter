# Batch, streaming, and events

SchemaRouter uses a consistent execution vocabulary across capability sources.

## Invoke

```python
result = router.invoke(request)
result = await router.ainvoke(request)
```

Both paths perform planning and execution.

## Batch

```python
results = router.batch(requests)
results = await router.abatch(
    requests,
    config={"max_concurrency": 8},
)
```

`abatch()` preserves input order.

For completion-order consumption:

```python
async for index, result in router.abatch_as_completed(requests):
    print(index, result)
```

The yielded index always points back to the original input.

## Result streaming

```python
async for result in router.astream(request):
    print(result.tool, result.endpoint)
```

In v0.1, tool calls in one plan execute sequentially. Streaming exposes each `ToolResult` as soon as
that call finishes.

## Typed lifecycle events

```python
from schemarouter import RunConfig

async for event in router.astream_events(
    request,
    config=RunConfig(
        tags=["production"],
        metadata={"service": "research-agent"},
    ),
):
    print(event.sequence, event.event)
```

The lifecycle includes:

```text
run.start
plan.end
tool.start
tool.end | tool.error
run.end  | run.error
```

All events in one invocation share a `run_id` and monotonic `sequence`.

## Payload redaction

Arguments and result payloads are not included by default.

```python
RunConfig(include_payloads=True)
```

Enable this only for trusted trace sinks with appropriate retention controls.

## Bound configuration

```python
configured = router.with_config(
    RunConfig(
        tags=["service-a"],
        max_concurrency=4,
    )
)

await configured.ainvoke(request)
```

This creates a lightweight configured facade without mutating the underlying router.


## OpenTelemetry

The optional OpenTelemetry integration consumes this same typed event stream:

```python
from schemarouter.integrations import OpenTelemetryRunExporter, trace_run_events

async for event in trace_run_events(
    router.astream_events(request),
    exporter=OpenTelemetryRunExporter(),
):
    ...
```

The exporter intentionally omits payload values, RunConfig metadata, tags, and exception messages
even when `include_payloads=True`. See [OpenTelemetry](../integrations/opentelemetry.md).


## Persist and replay event traces

Use `SQLiteRunTraceStore` when the event stream must survive process restarts:

```python
from schemarouter import SQLiteRunTraceStore

with SQLiteRunTraceStore("traces.sqlite3") as store:
    events = [
        event
        async for event in router.astream_events(
            request,
            trace_store=store,
        )
    ]
```

Replay reads historical events only and never re-executes tools. See
[Persistent run traces](run-traces.md) for privacy, corruption handling, and lifecycle details.

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

The default execution mode is sequential, preserving plan order.

For an independent read-only fan-out, opt into `parallel_read_only`:

```python
from schemarouter import RunConfig

config = RunConfig(
    execution_mode="parallel_read_only",
    max_parallel_calls=4,
)

results = await router.ainvoke(request, config=config)
```

Before any parallel task is launched, SchemaRouter preflights every planned call through current
schema, binding, and execution-policy validation and requires `endpoint.read_only is True` for all
calls. Mutating or unclassified calls fail the parallel run before invocation.

`ainvoke()` returns results in plan order. `astream()` and `astream_events()` can expose
completion order so a fast read-only call is not held behind a slower sibling. All parallel calls share the same per-run execution budget. `max_parallel_calls` limits
in-plan fan-out independently from `max_concurrency`, which continues to bound concurrent
inputs in batch APIs.

This is flat fan-out, not a DAG/workflow runtime. Dependencies, branching, checkpoints, and
multi-step orchestration remain the responsibility of LangGraph or another surrounding framework.

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
tool.fallback  # only after an explicitly unavailable precompiled read-only route
run.end  | run.error
```

All events in one invocation share a `run_id` and monotonic `sequence`.

Provider/access fallback uses the same event stream and never performs open-ended replanning. See
[Provider-aware fallback](provider-fallback.md).

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

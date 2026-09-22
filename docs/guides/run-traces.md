# Persistent run traces

SchemaRouter can persist its typed `RunEvent` stream into SQLite for audit, debugging, and replay
without re-executing tool calls.

## Create a trace store

```python
from schemarouter import SQLiteRunTraceStore

store = SQLiteRunTraceStore("schemarouter-traces.sqlite3")
```

The store uses only Python's standard-library `sqlite3` module. No new package dependency is
required.

## Persist directly from the runtime

```python
events = [
    event
    async for event in router.astream_events(
        request,
        trace_store=store,
    )
]

run_id = events[0].run_id
trace = store.trace(run_id)
```

Each event is written before it is yielded to the downstream consumer. Persistence failure therefore
fails the trace-producing stream instead of silently creating an unaudited execution history.

## Replay without execution

```python
from schemarouter import replay_run_events

for event in replay_run_events(store, run_id):
    print(event.sequence, event.event)
```

Replay reads validated historical `RunEvent` objects only. It does **not** call the planner,
executor, network, or registered tool invokers.

## Trace invariants

A persisted run must:

- begin with `run.start` at sequence 0;
- keep one immutable `run_id`;
- use contiguous sequence numbers;
- use monotonic timestamps;
- contain no second `run.start`;
- contain no events after `run.end` or `run.error`.

Corrupt JSON, event identity mismatches, gaps, timestamp regressions, and post-terminal appends fail
closed with `TraceError`.

Incomplete traces are allowed. They are useful when a process stops before a terminal event.

```python
store.run_ids(complete=True)
store.run_ids(complete=False)
```

## Privacy

The trace store persists the exact event envelope it receives.

By default, `SchemaRouter.astream_events()` redacts argument values and result payloads, so the
SQLite trace contains structural data such as argument names, selected fields, tool/endpoint names,
error types, and result counts.

If the caller explicitly sets:

```python
RunConfig(include_payloads=True)
```

then arguments, plans, results, and exception messages may be present in the trace and remain on
disk until deleted by the application. Treat that database as sensitive application data and apply
appropriate access control, encryption-at-rest, backup, and retention policy.

SchemaRouter does not encrypt the SQLite file itself.

## External event streams

The persistence helper can wrap any compatible async `RunEvent` stream:

```python
from schemarouter import record_run_events

async for event in record_run_events(source, store=store):
    consume(event)
```

This keeps storage independent of the high-level runtime facade.

## Deletion and lifecycle

```python
store.delete(run_id)
store.close()
```

The store also supports context-manager usage:

```python
with SQLiteRunTraceStore("traces.sqlite3") as store:
    ...
```

## Scope

Run traces are an observability/audit mechanism, not a checkpoint system for resuming agent control
flow. LangGraph or another orchestration layer should continue to own workflow checkpoints and
memory. SchemaRouter trace replay is deliberately non-executing.

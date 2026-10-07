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

## Retention and pruning

Retention is opt-in so existing applications keep their current persistence behavior. Configure
bounded retention explicitly:

```python
from schemarouter import SQLiteRunTraceStore, TraceRetentionPolicy

store = SQLiteRunTraceStore(
    "schemarouter-traces.sqlite3",
    retention_policy=TraceRetentionPolicy(
        max_age_seconds=30 * 24 * 60 * 60,
        max_runs=10_000,
    ),
)
```

When `prune_on_terminal_append=True` (the default on a configured policy), a terminal append and
its retention cleanup are committed in the same SQLite write transaction. `max_age_seconds` and
`max_runs` apply only to complete runs. Incomplete runs are never removed by those bounds.

Stale incomplete cleanup is deliberately separate and must be enabled explicitly with
`stale_incomplete_after_seconds`. This can remove a crashed or abandoned run, so choose a threshold
that is safely longer than the longest legitimate run.

Operators can also prune deterministically:

```python
result = store.prune(
    policy=TraceRetentionPolicy(max_runs=10_000),
)
print(result.deleted_runs, result.deleted_events)
```

SQLite writers are serialized with `BEGIN IMMEDIATE`; pruning and appending therefore cannot
partially interleave, including when several `SQLiteRunTraceStore` instances point at the same
database file. Retention indexes cover terminal state and last timestamp so bounded cleanup does not
need to deserialize event documents.

Deletion is logical SQLite deletion. With WAL enabled, pruning does **not** promise an immediate
reduction in the database or WAL file size. File-space reclamation is an operational concern:
checkpoint WAL as appropriate and run SQLite `VACUUM` only during a maintenance window when the
application is not using the trace store. SchemaRouter intentionally does not auto-`VACUUM` during
pruning.

## Privacy

The trace store persists the exact event envelope it receives. Runtime-produced events are
structured-redacted **before** they reach the store unless the caller explicitly selects raw tracing.

`RunConfig.metadata` is trusted process-local context. It is never copied into runtime
`RunEvent` envelopes, regardless of `include_payloads`. Use it for tenant routing, host-only
correlation context, credentials required by surrounding application code, or other values that
must not become trace data.

Trace-visible metadata requires a separate, explicit opt-in:

```python
RunConfig(
    tags=["batch-import"],
    trace_metadata={"request_id": "req-123"},
)
```

`tags` are structural labels and remain present on events for filtering. `trace_metadata` is
written only on the `run.start` event so identical run metadata is not duplicated into every
stored event. Replayed older traces that contain metadata on later events remain valid.

By default, request/tool payload values are omitted entirely. With:

```python
RunConfig(include_payloads=True)
```

arguments, plans, results, and exception messages may be included. This setting does **not** make
`RunConfig.metadata` trace-visible. Common credential keys in payloads or `trace_metadata`, plus
configured sensitive paths, are replaced with `[REDACTED]` before emission and persistence.
Heuristic key redaction is defense in depth, not a substitute for keeping sensitive values out of
`trace_metadata`. Secret values discovered under configured keys/paths are also removed from later
string messages in the same run.

Use `TraceRedactionConfig(sensitive_paths={...})` for application-specific personal or regulated
fields. Raw persistence requires the additional explicit escape hatch:

```python
RunConfig(
    include_payloads=True,
    raw_trace_payloads=True,
    trace_metadata={"debug_context": "..."},
)
```

Raw tracing can persist payloads and explicitly opted-in trace metadata verbatim. Treat such
databases as sensitive application data and apply appropriate access control, encryption-at-rest,
backup, and retention policy. SchemaRouter does not encrypt the SQLite file itself.

External producers that call `SQLiteRunTraceStore.append()` directly are responsible for
redacting their own `RunEvent` objects; the store deliberately does not mutate envelopes.

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
memory. SchemaRouter trace replay stays non-executing.

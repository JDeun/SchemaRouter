import asyncio
import sqlite3
import time
from datetime import datetime, timedelta, timezone

import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PlanRequest,
    RunConfig,
    RunEvent,
    RunTrace,
    SchemaRouter,
    SQLiteRunTraceStore,
    ToolSpec,
    TraceError,
    TracePersistenceError,
    TraceRedactionConfig,
    record_run_events,
    replay_run_events,
)
from schemarouter.errors import NonRetryableInvocationError


def event(
    run_id: str,
    sequence: int,
    name: str,
    *,
    seconds: int = 0,
    data: dict | None = None,
) -> RunEvent:
    return RunEvent(
        event=name,
        run_id=run_id,
        sequence=sequence,
        timestamp=datetime(2026, 9, 22, tzinfo=timezone.utc) + timedelta(seconds=seconds),
        data=data or {},
    )


def make_router(counter: dict[str, int] | None = None) -> SchemaRouter:
    router = SchemaRouter()
    router.add_tool(
        ToolSpec(
            name="weather",
            endpoints=[
                EndpointSpec(
                    name="current",
                    parameters=[ParameterSpec(name="city", required=True)],
                    output_fields=[
                        FieldSpec(name="city"),
                        FieldSpec(name="temperature"),
                    ],
                    read_only=True,
                )
            ],
        )
    )

    def invoke(endpoint: str, arguments: dict) -> dict:
        if counter is not None:
            counter["calls"] = counter.get("calls", 0) + 1
        return {
            "city": arguments["city"],
            "temperature": 20,
        }

    router.executor.bind("weather", invoke)
    return router


def make_secret_router(*, fail: bool = False) -> SchemaRouter:
    router = SchemaRouter()
    router.add_tool(
        ToolSpec(
            name="secret_echo",
            endpoints=[
                EndpointSpec(
                    name="echo",
                    parameters=[ParameterSpec(name="token", required=True)],
                    output_fields=[FieldSpec(name="token")],
                    read_only=True,
                )
            ],
        )
    )

    def invoke(endpoint: str, arguments: dict) -> dict:
        del endpoint
        if fail:
            raise NonRetryableInvocationError(
                f"authorization={arguments['token']}"
            )
        return {"token": arguments["token"]}

    router.executor.bind("secret_echo", invoke)
    return router


def test_run_trace_validates_order_identity_and_terminal_boundary() -> None:
    trace = RunTrace(
        run_id="run-1",
        events=[
            event("run-1", 0, "run.start"),
            event("run-1", 1, "plan.end", seconds=1),
            event("run-1", 2, "run.end", seconds=2),
        ],
    )

    assert trace.complete is True
    assert trace.terminal_event is not None
    assert trace.terminal_event.event == "run.end"
    assert [item.sequence for item in trace.replay()] == [0, 1, 2]


@pytest.mark.parametrize(
    "events",
    [
        [event("run-1", 0, "plan.end")],
        [event("run-1", 0, "run.start"), event("run-1", 2, "run.end")],
        [event("run-1", 0, "run.start"), event("run-2", 1, "run.end")],
        [
            event("run-1", 0, "run.start", seconds=2),
            event("run-1", 1, "run.end", seconds=1),
        ],
        [
            event("run-1", 0, "run.start"),
            event("run-1", 1, "run.end", seconds=1),
            event("run-1", 2, "plan.end", seconds=2),
        ],
    ],
)
def test_run_trace_rejects_invalid_history(events: list[RunEvent]) -> None:
    with pytest.raises(ValueError):
        RunTrace(run_id="run-1", events=events)


def test_sqlite_trace_store_persists_and_reopens_complete_and_partial_runs(tmp_path) -> None:
    path = tmp_path / "traces.sqlite3"

    with SQLiteRunTraceStore(path) as store:
        store.append(event("complete", 0, "run.start"))
        store.append(event("complete", 1, "run.end", seconds=1))
        store.append(event("partial", 0, "run.start", seconds=2))

        assert store.run_ids() == ("complete", "partial")
        assert store.run_ids(complete=True) == ("complete",)
        assert store.run_ids(complete=False) == ("partial",)

    with SQLiteRunTraceStore(path) as reopened:
        assert reopened.trace("complete").complete is True
        assert reopened.trace("partial").complete is False


def test_sqlite_trace_store_rejects_gaps_duplicates_and_post_terminal_events(tmp_path) -> None:
    path = tmp_path / "traces.sqlite3"

    with SQLiteRunTraceStore(path) as store:
        with pytest.raises(TraceError, match="first persisted"):
            store.append(event("gap", 1, "plan.end"))

        store.append(event("run-1", 0, "run.start"))

        with pytest.raises(TraceError, match="contiguous"):
            store.append(event("run-1", 2, "plan.end"))

        store.append(event("run-1", 1, "run.end", seconds=1))

        with pytest.raises(TraceError, match="terminal"):
            store.append(event("run-1", 2, "plan.end", seconds=2))


def test_sqlite_trace_store_rejects_timestamp_regression(tmp_path) -> None:
    path = tmp_path / "traces.sqlite3"

    with SQLiteRunTraceStore(path) as store:
        store.append(event("run-1", 0, "run.start", seconds=2))
        with pytest.raises(TraceError, match="timestamps"):
            store.append(event("run-1", 1, "run.end", seconds=1))


def test_sqlite_trace_store_corruption_fails_closed(tmp_path) -> None:
    path = tmp_path / "traces.sqlite3"

    with SQLiteRunTraceStore(path) as store:
        store.append(event("run-1", 0, "run.start"))

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            UPDATE schemarouter_trace_events
            SET document = ?
            WHERE run_id = ? AND sequence = 0
            """,
            ('{"event":"run.end","run_id":"different","sequence":99}', "run-1"),
        )
        connection.commit()
    finally:
        connection.close()

    with SQLiteRunTraceStore(path) as reopened:
        with pytest.raises(TraceError, match="invalid|identity mismatch"):
            reopened.trace("run-1")


@pytest.mark.asyncio
async def test_runtime_can_persist_redacted_trace_directly(tmp_path) -> None:
    path = tmp_path / "traces.sqlite3"
    router = make_router()

    with SQLiteRunTraceStore(path) as store:
        events = [
            item
            async for item in router.astream_events(
                PlanRequest(
                    query="city temperature",
                    arguments={"city": "Seoul"},
                ),
                trace_store=store,
            )
        ]

        trace = store.trace(events[0].run_id)

    assert [item.event for item in trace.events] == [
        "run.start",
        "plan.end",
        "tool.start",
        "tool.end",
        "run.end",
    ]
    tool_start = next(item for item in trace.events if item.event == "tool.start")
    tool_end = next(item for item in trace.events if item.event == "tool.end")
    assert tool_start.data["argument_names"] == ["city"]
    assert "arguments" not in tool_start.data
    assert "result" not in tool_end.data


@pytest.mark.asyncio
async def test_trace_sink_failure_after_tool_success_is_typed_and_nonretryable() -> None:
    counter: dict[str, int] = {}
    router = make_router(counter)

    class FailingStore:
        def append(self, item: RunEvent) -> None:
            if item.event == "tool.end":
                raise OSError("disk full")

    seen: list[RunEvent] = []
    with pytest.raises(TracePersistenceError) as captured:
        async for item in router.astream_events(
            PlanRequest(
                query="city temperature",
                arguments={"city": "Seoul"},
            ),
            trace_store=FailingStore(),
        ):
            seen.append(item)

    assert counter["calls"] == 1
    assert [item.event for item in seen] == [
        "run.start",
        "plan.end",
        "tool.start",
    ]
    assert captured.value.execution_succeeded is True
    assert isinstance(captured.value.event, RunEvent)
    assert captured.value.event.event == "tool.end"
    assert captured.value.event.tool == "weather"


@pytest.mark.asyncio
async def test_runtime_trace_can_explicitly_include_payloads(tmp_path) -> None:
    router = make_router()

    with SQLiteRunTraceStore(tmp_path / "traces.sqlite3") as store:
        events = [
            item
            async for item in router.astream_events(
                PlanRequest(
                    query="city temperature",
                    arguments={"city": "Busan"},
                ),
                config=RunConfig(include_payloads=True),
                trace_store=store,
            )
        ]
        trace = store.trace(events[0].run_id)

    tool_start = next(item for item in trace.events if item.event == "tool.start")
    tool_end = next(item for item in trace.events if item.event == "tool.end")
    assert tool_start.data["arguments"] == {"city": "Busan"}
    assert tool_end.data["result"]["data"]["temperature"] == 20


@pytest.mark.asyncio
async def test_payload_trace_redacts_credentials_before_sqlite_persistence(tmp_path) -> None:
    secret = "sk-super-secret-value"
    router = make_secret_router()

    with SQLiteRunTraceStore(tmp_path / "redacted.sqlite3") as store:
        events = [
            item
            async for item in router.astream_events(
                PlanRequest(
                    query="echo token",
                    arguments={"token": secret},
                ),
                config=RunConfig(
                    run_id="redacted-success",
                    include_payloads=True,
                    metadata={"api_key": secret, "safe": "visible"},
                ),
                trace_store=store,
            )
        ]
        trace = store.trace("redacted-success")

    serialized = "\n".join(event.model_dump_json() for event in trace.events)
    assert secret not in serialized
    assert "[REDACTED]" in serialized
    assert all(event.metadata["api_key"] == "[REDACTED]" for event in events)
    assert all(event.metadata["safe"] == "visible" for event in events)

    tool_start = next(event for event in trace.events if event.event == "tool.start")
    tool_end = next(event for event in trace.events if event.event == "tool.end")
    assert tool_start.data["arguments"]["token"] == "[REDACTED]"
    assert tool_end.data["result"]["data"]["token"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_payload_trace_redacts_exception_message_before_sqlite_persistence(
    tmp_path,
) -> None:
    secret = "runtime-secret-token"
    router = make_secret_router(fail=True)

    with SQLiteRunTraceStore(tmp_path / "redacted-error.sqlite3") as store:
        with pytest.raises(NonRetryableInvocationError, match="authorization="):
            async for _ in router.astream_events(
                PlanRequest(
                    query="echo token",
                    arguments={"token": secret},
                ),
                config=RunConfig(
                    run_id="redacted-error",
                    include_payloads=True,
                ),
                trace_store=store,
            ):
                pass

        trace = store.trace("redacted-error")

    serialized = "\n".join(event.model_dump_json() for event in trace.events)
    assert secret not in serialized
    error_events = [
        event
        for event in trace.events
        if event.event in {"tool.error", "run.error"}
    ]
    assert error_events
    assert all(secret not in str(event.data) for event in error_events)


def test_raw_trace_payloads_require_payload_opt_in() -> None:
    with pytest.raises(ValueError, match="requires include_payloads"):
        RunConfig(raw_trace_payloads=True)


@pytest.mark.asyncio
async def test_raw_trace_payloads_require_explicit_escape_hatch(tmp_path) -> None:
    secret = "raw-debug-secret"
    router = make_secret_router()

    with SQLiteRunTraceStore(tmp_path / "raw.sqlite3") as store:
        events = [
            item
            async for item in router.astream_events(
                PlanRequest(
                    query="echo token",
                    arguments={"token": secret},
                ),
                config=RunConfig(
                    run_id="raw-debug",
                    include_payloads=True,
                    raw_trace_payloads=True,
                    metadata={"api_key": secret},
                ),
                trace_store=store,
            )
        ]
        trace = store.trace("raw-debug")

    serialized = "\n".join(event.model_dump_json() for event in trace.events)
    assert secret in serialized
    assert events[0].metadata["api_key"] == secret


@pytest.mark.asyncio
async def test_trace_redaction_supports_explicit_event_paths(tmp_path) -> None:
    router = make_router()
    policy = TraceRedactionConfig(
        sensitive_paths={
            "data.arguments.city",
            "data.result.data.city",
        }
    )

    with SQLiteRunTraceStore(tmp_path / "path-redacted.sqlite3") as store:
        events = [
            item
            async for item in router.astream_events(
                PlanRequest(
                    query="city temperature",
                    arguments={"city": "Seoul"},
                ),
                config=RunConfig(
                    run_id="path-redacted",
                    include_payloads=True,
                    trace_redaction=policy,
                ),
                trace_store=store,
            )
        ]

    tool_start = next(event for event in events if event.event == "tool.start")
    tool_end = next(event for event in events if event.event == "tool.end")
    assert tool_start.data["arguments"]["city"] == "[REDACTED]"
    assert tool_end.data["result"]["data"]["city"] == "[REDACTED]"


@pytest.mark.asyncio
async def test_replay_never_reexecutes_tools(tmp_path) -> None:
    counter: dict[str, int] = {}
    router = make_router(counter)

    with SQLiteRunTraceStore(tmp_path / "traces.sqlite3") as store:
        events = [
            item
            async for item in router.astream_events(
                PlanRequest(
                    query="city temperature",
                    arguments={"city": "Seoul"},
                ),
                trace_store=store,
            )
        ]
        assert counter["calls"] == 1

        replayed = list(replay_run_events(store, events[0].run_id))
        assert counter["calls"] == 1

    assert [item.event for item in replayed] == [
        "run.start",
        "plan.end",
        "tool.start",
        "tool.end",
        "run.end",
    ]


@pytest.mark.asyncio
async def test_record_run_events_helper_persists_before_yield(tmp_path) -> None:
    async def source():
        yield event("run-1", 0, "run.start")
        yield event("run-1", 1, "run.end", seconds=1)

    with SQLiteRunTraceStore(tmp_path / "traces.sqlite3") as store:
        captured = [
            item
            async for item in record_run_events(
                source(),
                store=store,
            )
        ]

        assert store.trace("run-1").complete is True

    assert [item.sequence for item in captured] == [0, 1]



def test_sqlite_trace_store_summary_corruption_fails_closed(tmp_path) -> None:
    path = tmp_path / "traces.sqlite3"

    with SQLiteRunTraceStore(path) as store:
        store.append(event("run-1", 0, "run.start"))
        store.append(event("run-1", 1, "run.end", seconds=1))

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            UPDATE schemarouter_trace_runs
            SET last_sequence = 99, terminal = 0
            WHERE run_id = ?
            """,
            ("run-1",),
        )
        connection.commit()
    finally:
        connection.close()

    with SQLiteRunTraceStore(path) as reopened:
        with pytest.raises(TraceError, match="summary"):
            reopened.trace("run-1")


def test_replayed_events_are_detached_from_persistent_state(tmp_path) -> None:
    path = tmp_path / "traces.sqlite3"

    with SQLiteRunTraceStore(path) as store:
        store.append(event("run-1", 0, "run.start", data={"safe": True}))
        store.append(event("run-1", 1, "run.end", seconds=1))

        replayed = list(replay_run_events(store, "run-1"))
        replayed[0].data["safe"] = False

        assert store.trace("run-1").events[0].data["safe"] is True

def test_trace_store_delete_and_closed_state(tmp_path) -> None:
    store = SQLiteRunTraceStore(tmp_path / "traces.sqlite3")
    store.append(event("run-1", 0, "run.start"))
    store.delete("run-1")
    with pytest.raises(KeyError):
        store.trace("run-1")
    with pytest.raises(KeyError):
        store.delete("run-1")

    store.close()
    store.close()
    with pytest.raises(RuntimeError, match="closed"):
        store.run_ids()


@pytest.mark.asyncio
async def test_slow_sync_trace_sink_does_not_block_event_loop() -> None:
    router = make_router()
    loop_progressed = asyncio.Event()

    class SlowStore:
        def append(self, item: RunEvent) -> None:
            del item
            time.sleep(0.05)

    async def ticker() -> None:
        await asyncio.sleep(0.01)
        loop_progressed.set()

    stream = router.astream_events(
        PlanRequest(
            query="city temperature",
            arguments={"city": "Seoul"},
        ),
        trace_store=SlowStore(),
    )
    ticker_task = asyncio.create_task(ticker())
    first_event_task = asyncio.create_task(anext(stream))
    try:
        await asyncio.wait_for(loop_progressed.wait(), timeout=0.04)
        first_event = await asyncio.wait_for(first_event_task, timeout=0.2)
    finally:
        await ticker_task
        if not first_event_task.done():
            first_event_task.cancel()
            await asyncio.gather(first_event_task, return_exceptions=True)
        await stream.aclose()

    assert first_event.event == "run.start"


@pytest.mark.asyncio
async def test_record_run_events_offloads_sync_store_and_preserves_order() -> None:
    persisted: list[int] = []
    loop_progressed = asyncio.Event()

    class SlowStore:
        def append(self, item: RunEvent) -> None:
            time.sleep(0.03)
            persisted.append(item.sequence)

    async def source():
        yield event("run-offload", 0, "run.start")
        yield event("run-offload", 1, "run.end", seconds=1)

    async def ticker() -> None:
        await asyncio.sleep(0.005)
        loop_progressed.set()

    ticker_task = asyncio.create_task(ticker())
    captured = [
        item
        async for item in record_run_events(
            source(),
            store=SlowStore(),
        )
    ]
    await ticker_task

    assert loop_progressed.is_set()
    assert persisted == [0, 1]
    assert [item.sequence for item in captured] == [0, 1]


@pytest.mark.asyncio
async def test_record_run_events_closes_upstream_generator_promptly() -> None:
    closed = asyncio.Event()
    persisted: list[int] = []

    class Store:
        def append(self, item: RunEvent) -> None:
            persisted.append(item.sequence)

    async def source():
        try:
            yield event("upstream-close", 0, "run.start")
            await asyncio.Event().wait()
        finally:
            closed.set()

    wrapped = record_run_events(source(), store=Store())
    first = await anext(wrapped)
    await wrapped.aclose()

    assert first.sequence == 0
    assert persisted == [0]
    assert closed.is_set()

import sqlite3
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
    SQLiteRunTraceStore,
    SchemaRouter,
    ToolSpec,
    TraceError,
    record_run_events,
    replay_run_events,
)


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

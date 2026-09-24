from __future__ import annotations

import argparse
import asyncio
import json
import platform
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Awaitable, Callable

from pydantic import BaseModel

from schemarouter import (
    ApprovalDeniedError,
    BindingDriftError,
    ExecutionBudget,
    ExecutionBudgetExceededError,
    ExecutionPolicy,
    PlanRequest,
    PolicyViolationError,
    RetryPolicy,
    RunConfig,
    SQLiteRegistry,
    SQLiteRunTraceStore,
    SchemaDriftError,
    SchemaRouter,
    SchemaValidationError,
    __version__,
    inspect_registry,
    inspect_traces,
    schema_tool,
    write_dashboard,
)


class Weather(BaseModel):
    city: str
    temperature: float


@schema_tool(read_only=True)
def current_weather(city: str) -> Weather:
    """Return a deterministic observation for consumer acceptance validation."""
    return Weather(city=city, temperature=20.5)


@schema_tool(read_only=False)
def update_profile(value: int) -> int:
    """Represent a local mutating operation."""
    return value + 1


@schema_tool(read_only=True)
def lookup_value(key: str) -> str:
    """Return a deterministic lookup value."""
    return f"value:{key}"


@schema_tool(read_only=True)
def invalid_output(value: int) -> int:
    """Return a deliberately invalid runtime value for schema enforcement validation."""
    return "not-an-int"  # type: ignore[return-value]


async def _expect(
    error_type: type[BaseException],
    awaitable: Awaitable[object],
) -> BaseException:
    try:
        await awaitable
    except error_type as exc:
        return exc
    raise AssertionError(f"expected {error_type.__name__}")


async def scenario_happy_path() -> dict[str, object]:
    router = SchemaRouter()
    key = router.add_callable(current_weather)

    results = await router.ainvoke(
        PlanRequest(
            query="city temperature",
            preferred_tools=[key],
            arguments={"city": "Seoul"},
        )
    )

    assert len(results) == 1
    assert results[0].tool == key
    assert results[0].endpoint == "call"
    assert results[0].data == {"city": "Seoul", "temperature": 20.5}
    assert router.inspect().execution.bound_tools == [key]
    return {"tool": key, "result": results[0].data}


async def scenario_policy_and_approval() -> dict[str, object]:
    denied_router = SchemaRouter()
    denied_key = denied_router.add_callable(update_profile)
    denied_request = PlanRequest(
        query="update profile value",
        preferred_tools=[denied_key],
        arguments={"value": 2},
    )
    await _expect(PolicyViolationError, denied_router.ainvoke(denied_request))

    approval_required = SchemaRouter(
        policy=ExecutionPolicy(
            allow_mutations=True,
            approval_mode="non_read_only",
        )
    )
    required_key = approval_required.add_callable(update_profile)
    required_request = PlanRequest(
        query="update profile value",
        preferred_tools=[required_key],
        arguments={"value": 3},
    )
    await _expect(ApprovalDeniedError, approval_required.ainvoke(required_request))

    approvals: list[str] = []

    def approve(tool, endpoint, call) -> bool:
        approvals.append(f"{tool.key}.{endpoint.name}")
        assert call.arguments == {"value": 4}
        return True

    approved_router = SchemaRouter(
        policy=ExecutionPolicy(
            allow_mutations=True,
            approval_mode="non_read_only",
        ),
        approval_callback=approve,
    )
    approved_key = approved_router.add_callable(update_profile)
    approved = await approved_router.ainvoke(
        PlanRequest(
            query="update profile value",
            preferred_tools=[approved_key],
            arguments={"value": 4},
        )
    )
    assert approved[0].data == 5
    assert approvals == [f"{approved_key}.call"]
    return {
        "default_policy": "denied",
        "missing_approval": "denied",
        "trusted_approval": "executed",
    }


async def scenario_schema_drift() -> dict[str, object]:
    router = SchemaRouter()
    key = router.add_callable(lookup_value)
    plan = await router.aplan(
        PlanRequest(
            query="lookup value key",
            preferred_tools=[key],
            arguments={"key": "alpha"},
        )
    )
    assert plan.executable

    original = router.registry.get(key)
    changed_endpoint = original.endpoints[0].model_copy(
        update={"description": "changed after planning"},
        deep=True,
    )
    changed = original.model_copy(
        update={"endpoints": [changed_endpoint]},
        deep=True,
    )
    router.registry.register(changed, replace=True)

    await _expect(SchemaDriftError, router.execute(plan))
    return {"stale_plan": "blocked"}


async def scenario_binding_drift() -> dict[str, object]:
    router = SchemaRouter()
    key = router.add_callable(lookup_value)
    plan = await router.aplan(
        PlanRequest(
            query="lookup value key",
            preferred_tools=[key],
            arguments={"key": "beta"},
        )
    )
    assert plan.executable

    original = router.registry.get(key)
    changed = original.model_copy(
        update={"description": "tool metadata changed without rebinding"},
        deep=True,
    )
    router.registry.register(changed, replace=True)

    await _expect(BindingDriftError, router.execute(plan))
    return {"stale_binding": "blocked"}


async def scenario_output_validation() -> dict[str, object]:
    router = SchemaRouter()
    key = router.add_callable(invalid_output)
    await _expect(
        SchemaValidationError,
        router.ainvoke(
            PlanRequest(
                query="invalid output value",
                preferred_tools=[key],
                arguments={"value": 7},
            )
        ),
    )
    return {"invalid_runtime_output": "blocked"}


async def scenario_retry_and_budget() -> dict[str, object]:
    attempts = 0

    @schema_tool(read_only=True)
    async def flaky(value: int) -> int:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("transient")
        return value

    retry_router = SchemaRouter()
    retry_key = retry_router.add_callable(flaky)
    result = await retry_router.ainvoke(
        PlanRequest(
            query="flaky value",
            preferred_tools=[retry_key],
            arguments={"value": 9},
        ),
        config=RunConfig(
            retry=RetryPolicy(
                max_attempts=2,
                initial_backoff_seconds=0,
            )
        ),
    )
    assert result[0].data == 9
    assert attempts == 2

    @schema_tool(read_only=True)
    async def slow(value: int) -> int:
        await asyncio.sleep(0.05)
        return value

    budget_router = SchemaRouter()
    budget_key = budget_router.add_callable(slow)
    await _expect(
        ExecutionBudgetExceededError,
        budget_router.ainvoke(
            PlanRequest(
                query="slow value",
                preferred_tools=[budget_key],
                arguments={"value": 1},
            ),
            config=RunConfig(
                budget=ExecutionBudget(max_elapsed_seconds=0.01),
            ),
        ),
    )
    return {"retry_attempts": attempts, "elapsed_budget": "enforced"}


async def scenario_persistence_traces_and_dashboard() -> dict[str, object]:
    with TemporaryDirectory(prefix="schemarouter-acceptance-") as temp:
        root = Path(temp)
        registry_path = root / "registry.sqlite3"
        trace_path = root / "traces.sqlite3"
        dashboard_path = root / "dashboard.html"

        with SQLiteRegistry(registry_path) as registry:
            router = SchemaRouter(registry=registry)
            key = router.add_callable(current_weather)

            with SQLiteRunTraceStore(trace_path) as traces:
                events = [
                    event
                    async for event in router.astream_events(
                        PlanRequest(
                            query="city temperature",
                            preferred_tools=[key],
                            arguments={"city": "Seoul"},
                        ),
                        config=RunConfig(tags=["consumer-acceptance"]),
                        trace_store=traces,
                    )
                ]
                assert [event.event for event in events] == [
                    "run.start",
                    "plan.end",
                    "tool.start",
                    "tool.end",
                    "run.end",
                ]
                snapshots = inspect_traces(traces, complete=True)
                assert len(snapshots) == 1
                assert snapshots[0].terminal_event is not None
                assert snapshots[0].terminal_event.event == "run.end"
                trace_json = snapshots[0].model_dump_json()
                assert "Seoul" not in trace_json

                dashboard = write_dashboard(
                    inspect_registry(registry),
                    dashboard_path,
                    traces=snapshots,
                    live=router.inspect(),
                )
                assert dashboard == dashboard_path
                html = dashboard_path.read_text(encoding="utf-8")
                assert "SchemaRouter inspection dashboard" in html
                assert key in html
                assert "Seoul" not in html

        with SQLiteRegistry(registry_path) as reopened:
            assert reopened.keys() == (key,)
            assert reopened.version >= 1

        return {
            "registry_reopen": "success",
            "trace_events": len(events),
            "dashboard_bytes": dashboard_path.stat().st_size,
        }


Scenario = Callable[[], Awaitable[dict[str, object]]]

SCENARIOS: tuple[tuple[str, Scenario], ...] = (
    ("happy_path", scenario_happy_path),
    ("policy_and_approval", scenario_policy_and_approval),
    ("schema_drift", scenario_schema_drift),
    ("binding_drift", scenario_binding_drift),
    ("output_validation", scenario_output_validation),
    ("retry_and_budget", scenario_retry_and_budget),
    ("persistence_traces_dashboard", scenario_persistence_traces_and_dashboard),
)


async def run_all() -> dict[str, object]:
    report: dict[str, object] = {
        "schema_version": 1,
        "schemarouter_version": __version__,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "scenarios": [],
    }
    scenarios: list[dict[str, object]] = []

    for name, scenario in SCENARIOS:
        started = time.perf_counter()
        details = await scenario()
        scenarios.append(
            {
                "name": name,
                "status": "success",
                "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                "details": details,
            }
        )

    report["scenarios"] = scenarios
    report["status"] = "success"
    report["scenario_count"] = len(scenarios)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run dependency-free consumer acceptance scenarios against an installed SchemaRouter."
    )
    parser.add_argument("--json-out", type=Path, default=None)
    args = parser.parse_args()

    report = asyncio.run(run_all())
    document = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(document + "\n", encoding="utf-8")
    print(document)


if __name__ == "__main__":
    main()

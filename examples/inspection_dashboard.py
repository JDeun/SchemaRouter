from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from pydantic import BaseModel

from schemarouter import (
    PlanRequest,
    RunConfig,
    SchemaRouter,
    SQLiteRegistry,
    SQLiteRunTraceStore,
    inspect_registry,
    inspect_router,
    inspect_traces,
    schema_tool,
    write_dashboard,
)


class Weather(BaseModel):
    city: str
    temperature: float
    unit: str


@schema_tool(read_only=True)
def current_weather(city: str) -> Weather:
    return Weather(city=city, temperature=20.5, unit="celsius")


async def build_demo(
    *,
    registry_path: Path,
    trace_path: Path,
    output_path: Path,
) -> None:
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    for path in (registry_path, trace_path):
        if path.exists():
            path.unlink()

    with SQLiteRegistry(registry_path) as registry:
        router = SchemaRouter(registry=registry)
        router.add_callable(current_weather)

        print("=== live router.inspect() ===")
        print(inspect_router(router).model_dump_json(indent=2))

        with SQLiteRunTraceStore(trace_path) as traces:
            request = PlanRequest(
                query="city temperature unit",
                arguments={"city": "Seoul"},
            )
            async for _event in router.astream_events(
                request,
                config=RunConfig(tags=["inspection-demo"]),
                trace_store=traces,
            ):
                pass

            registry_snapshot = inspect_registry(registry)
            trace_snapshots = inspect_traces(traces)

        destination = write_dashboard(
            registry_snapshot,
            output_path,
            traces=trace_snapshots,
            live=router.inspect(),
        )

    print(f"\nDashboard written to: {destination}")
    print(f"Registry DB: {registry_path}")
    print(f"Trace DB: {trace_path}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--registry",
        type=Path,
        default=Path("artifacts/inspection-demo/registry.sqlite3"),
    )
    parser.add_argument(
        "--traces",
        type=Path,
        default=Path("artifacts/inspection-demo/traces.sqlite3"),
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/inspection-demo/dashboard.html"),
    )
    args = parser.parse_args()

    asyncio.run(
        build_demo(
            registry_path=args.registry,
            trace_path=args.traces,
            output_path=args.output,
        )
    )


if __name__ == "__main__":
    main()

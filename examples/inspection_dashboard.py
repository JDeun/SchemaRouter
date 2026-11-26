from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from pydantic import BaseModel

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperNativeRankPolicy,
    PaperPlanRequest,
    PrincipalContext,
    RunConfig,
    SchemaRouter,
    SQLiteRegistry,
    SQLiteRunTraceStore,
    inspect_registry,
    inspect_router,
    inspect_traces,
    tool_from_callable,
    write_dashboard,
)


class Weather(BaseModel):
    city: str
    temperature: float
    unit: str


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
        principal = PrincipalContext(subject="inspection-demo", roles=("reader",))
        router = SchemaRouter(
            registry=registry,
            authorization_policy=AuthorizationPolicy(
                default_effect="deny",
                rules=(AuthorizationRule(
                    effect="allow", operation="current_weather.call", roles_any=("reader",),
                ),),
            ),
        )

        # Review the local fixture's source and output contracts before binding.
        tool = tool_from_callable(current_weather, read_only=True)
        tool.source_type = "python"
        tool.license = "MIT"
        endpoint = tool.endpoint("call")
        endpoint.output_fields = [
            field.model_copy(update={
                "semantic_id": f"weather.{field.name}",
                "identifier": field.name == "city",
            })
            for field in endpoint.output_fields
        ]

        def invoke(endpoint_name, arguments):
            assert endpoint_name == "call"
            return current_weather(**arguments).model_dump(mode="json")

        router.add_bound_tool(tool, invoke)
        session = router.prepare_field_routing(catalog=NativeConceptCatalog(concepts=(
            NativeDeclaredConcept(
                concept_id="weather.temperature", aliases=("temperature",),
                required_fields=(CapabilityFieldContract(
                    semantic_id="weather.temperature", json_schema={"type": "number"},
                ),),
                source_type="python", license="MIT",
            ),
        )))
        intents = PaperIntentRegistry(
            intents=(PaperIntentDeclaration(
                intent_id="weather.read", required_concept_ids=("weather.temperature",),
                recall_group_ids=("weather",),
            ),),
            projection_snapshot_id=session.snapshot_id,
            route_field_groups={
                "current_weather.call": {"weather": ("temperature", "unit")},
            },
            approved_direct_parameter_routes=("current_weather.call",),
        )

        def owner_model(payload):
            # Deterministic Understand fixture, not a real model evaluation.
            assert "schema_catalog" not in payload
            return {
                "intent_id": "weather.read",
                "needs": [{
                    "concept": "temperature", "unit": None,
                    "source_type": "python", "qualifiers": {},
                }],
                "needs_truncated": False, "excluded_concepts": [],
                "named_tools": ["current_weather"], "parameter_hints": {},
                "source_type": "python",
            }

        router.configure_field_routing(
            session, model=owner_model, intent_registry=intents,
            rank_policy=PaperNativeRankPolicy(
                snapshot_id=session.snapshot_id, direct_score_mode="paper_v1", focus_direct=True,
            ),
            model_visible_intent_ids=("weather.read",),
        )

        print("=== live router.inspect() ===")
        print(inspect_router(router).model_dump_json(indent=2))

        with SQLiteRunTraceStore(trace_path) as traces:
            request = PaperPlanRequest(
                query="city temperature unit from current_weather",
                host_source_arguments={"current_weather.call": {"city": "Seoul"}},
            )
            events = []
            async for event in router.astream_events(
                request,
                config=RunConfig(tags=["inspection-demo"], principal=principal),
                trace_store=traces,
            ):
                events.append(event.event)
            assert "tool.end" in events and events[-1] == "run.end"

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

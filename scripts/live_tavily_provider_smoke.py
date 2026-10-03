from __future__ import annotations

import argparse
import asyncio
import json
import os
from time import perf_counter

from compatibility_report import new_report, write_report

from schemarouter import PlanRequest, SchemaRouter

PROVIDER_ID = "tavily"
BASE_URL = "https://api.tavily.com"


async def run_smoke() -> dict[str, object]:
    router = SchemaRouter()
    resolution = router.resolve_provider(PROVIDER_ID, methods={"rest"})
    assert resolution.provider_id == PROVIDER_ID
    assert resolution.methods[0].status == "available"
    assert resolution.methods[0].credential_names == ("Authorization",)

    api_key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not api_key:
        registration = await router.add_provider(PROVIDER_ID, methods={"rest"})
        assert registration.registered_tool_keys == ()
        assert registration.methods[0].status == "auth_required"
        return {
            "evidence_kind": "auth_contract",
            "provider": "Tavily",
            "provider_id": PROVIDER_ID,
            "provider_resolution_success": True,
            "auth_requirement_success": True,
            "live_execution": "not_run_missing_TAVILY_API_KEY",
            "source": BASE_URL,
        }

    started = perf_counter()
    registration = await router.add_provider(
        PROVIDER_ID,
        methods={"rest"},
        trusted_headers_by_method={
            "rest": {"Authorization": f"Bearer {api_key}"}
        },
    )
    registration_ms = round((perf_counter() - started) * 1000, 2)

    assert len(registration.registered_tool_keys) == 1
    assert registration.methods[0].status == "registered"
    tool_key = registration.registered_tool_keys[0]
    tool = router.registry.get(tool_key)
    assert api_key not in tool.model_dump_json()
    assert tool.provider == PROVIDER_ID
    assert tool.access_mode == "http_json"

    plan = router.plan_executable(
        PlanRequest(
            query="search Tavily web",
            preferred_tools=[tool_key],
            arguments={
                "query": "SchemaRouter GitHub",
                "max_results": 1,
                "search_depth": "basic",
            },
        )
    )
    assert plan.executable
    assert plan.calls[0].endpoint == "search"
    plan.calls[0].fields = ["results", "response_time"]

    execution_started = perf_counter()
    results = await router.execute(plan)
    execution_ms = round((perf_counter() - execution_started) * 1000, 2)

    assert len(results) == 1
    items = results[0].data["results"]
    assert isinstance(items, list)
    assert items
    assert isinstance(items[0], dict)
    assert items[0].get("url")

    return {
        "evidence_kind": "live_authenticated_provider",
        "provider": "Tavily",
        "provider_id": PROVIDER_ID,
        "provider_resolution_success": True,
        "auth_requirement_success": True,
        "registration_success": True,
        "execution_success": True,
        "registered_access_mode": tool.access_mode,
        "source": BASE_URL,
        "tool": tool_key,
        "safe_endpoint": plan.calls[0].endpoint,
        "first_url": items[0]["url"],
        "registration_latency_ms": registration_ms,
        "execution_latency_ms": execution_ms,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    report = new_report(adapter="provider-profile", source=BASE_URL)
    report["details"] = {
        "provider": "Tavily",
        "provider_id": PROVIDER_ID,
    }

    try:
        report["details"].update(await run_smoke())
        report["status"] = "success"
    except Exception as exc:
        report["status"] = "failure"
        report["error_type"] = type(exc).__name__
        write_report(args.json_out, report)
        raise

    write_report(args.json_out, report)
    print(json.dumps(report, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    asyncio.run(main())

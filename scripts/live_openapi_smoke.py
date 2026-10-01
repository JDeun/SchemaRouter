from __future__ import annotations

import argparse
import asyncio
import json
import os
from time import perf_counter

from compatibility_report import new_report, write_report

from schemarouter import PlanRequest, SchemaRouter

DEFAULT_OPENAPI_URL = "https://api.apis.guru/v2/openapi.yaml"


async def run_smoke(
    url: str,
    report: dict[str, object],
) -> dict[str, object]:
    started = perf_counter()
    router = await SchemaRouter.from_url(url, kind="openapi")
    report["discovery"] = {
        "success": True,
        "tool_count": len(router.registry.keys()),
        "endpoint_count": sum(
            len(tool.endpoints) for tool in router.registry.tools()
        ),
        "execution_bound": all(
            router.executor.binding_status_for_contract(
                tool.key,
                tool.fingerprint,
            )
            == "ready"
            for tool in router.registry.tools()
        ),
        "latency_ms": round((perf_counter() - started) * 1000, 2),
    }

    endpoint_name = "getMetrics"
    tools = router.registry.tools()
    tool = next(
        candidate
        for candidate in tools
        if any(endpoint.name == endpoint_name for endpoint in candidate.endpoints)
    )
    endpoint = tool.endpoint(endpoint_name)

    assert endpoint.read_only is True
    assert tool.metadata["execution_bound"] is True

    plan = router.plan(
        PlanRequest(
            query="api directory metrics",
            preferred_tools=[tool.key],
            max_calls=32,
        )
    )
    call = next(candidate for candidate in plan.calls if candidate.endpoint == endpoint_name)
    assert call.executable
    selected_plan = plan.model_copy(update={"calls": [call]}, deep=True)

    execution_started = perf_counter()
    results = await router.execute(selected_plan)
    assert len(results) == 1
    assert isinstance(results[0].data, dict)
    assert isinstance(results[0].data.get("numAPIs"), int)
    assert results[0].data["numAPIs"] > 0
    report["execution"] = {
        "attempted": True,
        "safe_read_only": endpoint.read_only is True,
        "endpoint": call.endpoint,
        "success": True,
        "latency_ms": round(
            (perf_counter() - execution_started) * 1000,
            2,
        ),
        "result_shape": "object",
    }

    return {
        "tool": tool.key,
        "endpoint": call.endpoint,
        "numAPIs": results[0].data["numAPIs"],
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()
    url = os.environ.get("SCHEMAROUTER_LIVE_OPENAPI_URL", DEFAULT_OPENAPI_URL)
    report = new_report(
        adapter="openapi",
        source=url,
        provider="APIs.guru",
        authentication="none",
    )
    report["known_quirks"] = [
        "Public external service; availability is not a release blocker.",
    ]

    try:
        report["details"] = await run_smoke(url, report)
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

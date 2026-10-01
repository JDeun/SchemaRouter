from __future__ import annotations

import argparse
import asyncio
import json
import os
from time import perf_counter

from compatibility_report import new_report, write_report

from schemarouter import PlanRequest, SchemaRouter

DEFAULT_OPENAPI_URL = "https://api.apis.guru/v2/openapi.yaml"


async def run_smoke(url: str) -> dict[str, object]:
    discovery_started = perf_counter()
    router = await SchemaRouter.from_url(url, kind="openapi")
    discovery_ms = round((perf_counter() - discovery_started) * 1000, 2)

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
    execution_ms = round((perf_counter() - execution_started) * 1000, 2)
    assert len(results) == 1
    assert isinstance(results[0].data, dict)
    assert isinstance(results[0].data.get("numAPIs"), int)
    assert results[0].data["numAPIs"] > 0

    return {
        "evidence_kind": "live_public_provider",
        "provider": "APIs.guru",
        "discovery_success": True,
        "tool_count": len(tools),
        "endpoint_count": sum(len(candidate.endpoints) for candidate in tools),
        "execution_bound": router.executor.is_binding_ready_for_contract(
            tool.key,
            tool.fingerprint,
        ),
        "execution_success": True,
        "safe_endpoint": call.endpoint,
        "returned_shape": "object",
        "discovery_latency_ms": discovery_ms,
        "execution_latency_ms": execution_ms,
        "auth_required": endpoint.auth_required,
        "known_quirks": [
            "Public provider availability is external infrastructure state."
        ],
        "tool": tool.key,
        "numAPIs": results[0].data["numAPIs"],
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()
    url = os.environ.get("SCHEMAROUTER_LIVE_OPENAPI_URL", DEFAULT_OPENAPI_URL)
    report = new_report(adapter="openapi", source=url)
    report["details"] = {
        "evidence_kind": "live_public_provider",
        "provider": "APIs.guru",
    }

    try:
        report["details"].update(await run_smoke(url))
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

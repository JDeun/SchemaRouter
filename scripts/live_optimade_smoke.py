from __future__ import annotations

import argparse
import asyncio
import json
import os
from time import perf_counter

from compatibility_report import new_report, write_report

from schemarouter import PlanRequest, SchemaRouter

DEFAULT_URL = "https://www.crystallography.net/cod/optimade"


async def run_smoke(
    url: str,
    report: dict[str, object],
) -> dict[str, object]:
    started = perf_counter()
    router = await SchemaRouter.from_url(url, kind="optimade")
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

    keys = router.registry.keys()
    assert len(keys) == 1
    tool_key = keys[0]
    tool = router.registry.get(tool_key)
    assert tool.metadata["adapter"] == "optimade"
    assert tool.metadata["api_version"]

    endpoint_names = {endpoint.name for endpoint in tool.endpoints}
    assert "search_structures" in endpoint_names

    plan = router.plan(
        PlanRequest(
            query="chemical formula descriptive nelements",
            preferred_tools=[tool_key],
            arguments={
                "filter": 'elements HAS ALL "Si","O" AND nelements=2',
                "page_limit": 1,
            },
        )
    )
    assert plan.executable
    assert plan.calls[0].endpoint == "search_structures"
    assert "chemical_formula_descriptive" in plan.calls[0].fields
    assert "nelements" in plan.calls[0].fields

    execution_started = perf_counter()
    results = await router.execute(plan)
    assert len(results) == 1
    assert isinstance(results[0].data, list)
    assert results[0].data
    first = results[0].data[0]
    assert first["id"]
    assert "chemical_formula_descriptive" in first
    assert "nelements" in first
    # Final ToolResult projection is field-first: OPTIMADE's raw JSON:API
    # identity envelope is schema-validated before projection, but unselected
    # non-identifier fields such as "type" are intentionally not retained.
    assert "type" not in first
    report["execution"] = {
        "attempted": True,
        "safe_read_only": tool.endpoint("search_structures").read_only is True,
        "endpoint": plan.calls[0].endpoint,
        "success": True,
        "latency_ms": round(
            (perf_counter() - execution_started) * 1000,
            2,
        ),
        "result_shape": "array",
    }

    return {
        "tool": tool_key,
        "endpoint": plan.calls[0].endpoint,
        "api_version": tool.metadata["api_version"],
        "result_count": len(results[0].data),
        "first_id": first["id"],
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()
    url = os.environ.get("SCHEMAROUTER_LIVE_OPTIMADE_URL", DEFAULT_URL)
    report = new_report(
        adapter="optimade",
        source=url,
        provider="Crystallography Open Database OPTIMADE",
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

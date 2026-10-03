from __future__ import annotations

import argparse
import asyncio
import json
from time import perf_counter

from compatibility_report import new_report, write_report

from schemarouter import PlanRequest, SchemaRouter

PROVIDER_ID = "materials-project"
EXPECTED_OPTIMADE_URL = "https://optimade.materialsproject.org"


async def run_smoke() -> dict[str, object]:
    router = SchemaRouter()

    resolution = router.resolve_provider(PROVIDER_ID)
    methods = {method.method_id: method for method in resolution.methods}
    assert methods["optimade"].url == EXPECTED_OPTIMADE_URL
    assert methods["optimade"].status == "available"
    assert methods["openapi"].credential_names == ("X-API-KEY",)
    assert methods["python-sdk"].status in {
        "dependency_missing",
        "manual_binding_required",
    }

    discovery_started = perf_counter()
    registration = await router.add_provider(
        PROVIDER_ID,
        methods={"optimade"},
        timeout=30.0,
    )
    discovery_ms = round((perf_counter() - discovery_started) * 1000, 2)

    registration_status = {
        method.method_id: method.status for method in registration.methods
    }
    if len(registration.registered_tool_keys) != 1:
        safe_diagnostics = [
            {
                "method_id": method.method_id,
                "status": method.status,
                "error_type": method.error_type,
                "detail": method.detail,
            }
            for method in registration.methods
        ]
        raise RuntimeError(
            "Materials Project provider registration did not yield one live tool: "
            + json.dumps(safe_diagnostics, sort_keys=True)
        )
    assert registration_status == {"optimade": "registered"}

    tool_key = registration.registered_tool_keys[0]
    tool = router.registry.get(tool_key)
    assert tool.provider == PROVIDER_ID
    assert tool.access_mode == "optimade"
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
    execution_ms = round((perf_counter() - execution_started) * 1000, 2)

    assert len(results) == 1
    assert isinstance(results[0].data, list)
    assert results[0].data
    first = results[0].data[0]
    assert first["id"]
    assert "chemical_formula_descriptive" in first
    assert "nelements" in first

    return {
        "evidence_kind": "live_public_provider",
        "provider": "Materials Project",
        "provider_id": PROVIDER_ID,
        "provider_resolution_success": True,
        "registration_success": True,
        "registered_access_mode": tool.access_mode,
        "source": EXPECTED_OPTIMADE_URL,
        "tool": tool_key,
        "endpoint_count": len(tool.endpoints),
        "execution_bound": router.executor.is_binding_ready_for_contract(
            tool.key,
            tool.fingerprint,
        ),
        "execution_success": True,
        "safe_endpoint": plan.calls[0].endpoint,
        "result_count": len(results[0].data),
        "first_id": first["id"],
        "discovery_latency_ms": discovery_ms,
        "execution_latency_ms": execution_ms,
        "api_version": tool.metadata["api_version"],
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    report = new_report(
        adapter="provider-profile",
        source=EXPECTED_OPTIMADE_URL,
    )
    report["details"] = {
        "evidence_kind": "live_public_provider",
        "provider": "Materials Project",
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

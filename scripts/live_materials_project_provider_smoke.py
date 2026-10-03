from __future__ import annotations

import argparse
import asyncio
import json
from time import perf_counter

import httpx
from compatibility_report import new_report, write_report

from schemarouter import PlanRequest, SchemaRouter
from schemarouter.adapters.optimade import _base_info_attributes, _bounded_get

PROVIDER_ID = "materials-project"
EXPECTED_OPTIMADE_URL = "https://optimade.materialsproject.org/v1"


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
        probe_diagnostic = None
        try:
            await router.probe_url(
                EXPECTED_OPTIMADE_URL,
                kind="optimade",
                timeout=30.0,
            )
        except Exception as exc:  # noqa: BLE001
            chain: list[str] = []
            current: BaseException | None = exc
            while current is not None and len(chain) < 4:
                chain.append(f"{type(current).__name__}: {current}")
                current = current.__cause__
            probe_diagnostic = " <- ".join(chain)
        raw_shape = None
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(f"{EXPECTED_OPTIMADE_URL}/info")
                document = response.json()
                data = document.get("data") if isinstance(document, dict) else None
                attributes = data.get("attributes") if isinstance(data, dict) else None
                raw_shape = {
                    "status_code": response.status_code,
                    "final_url": str(response.url),
                    "redirects": [
                        {
                            "status": item.status_code,
                            "url": str(item.url),
                            "location": item.headers.get("location"),
                        }
                        for item in response.history
                    ],
                    "data_type": data.get("type") if isinstance(data, dict) else None,
                    "data_id": data.get("id") if isinstance(data, dict) else None,
                    "attribute_keys": (
                        sorted(attributes) if isinstance(attributes, dict) else None
                    ),
                    "api_version_type": (
                        type(attributes.get("api_version")).__name__
                        if isinstance(attributes, dict)
                        else None
                    ),
                    "available_endpoints_type": (
                        type(attributes.get("available_endpoints")).__name__
                        if isinstance(attributes, dict)
                        else None
                    ),
                    "entry_types_by_format_type": (
                        type(attributes.get("entry_types_by_format")).__name__
                        if isinstance(attributes, dict)
                        else None
                    ),
                    "normal_parser_recognized": _base_info_attributes(document) is not None,
                }
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
                bounded = await _bounded_get(
                    client,
                    f"{EXPECTED_OPTIMADE_URL}/info",
                    headers=None,
                    max_bytes=2 * 1024 * 1024,
                )
                bounded_document = bounded.json()
                raw_shape["bounded_status_code"] = bounded.status_code
                raw_shape["bounded_final_url"] = str(bounded.url)
                raw_shape["bounded_parser_recognized"] = (
                    _base_info_attributes(bounded_document) is not None
                )
        except Exception as exc:  # noqa: BLE001
            raw_shape = {
                **(raw_shape or {}),
                "diagnostic_error": f"{type(exc).__name__}: {exc}",
            }
        raise RuntimeError(
            "Materials Project provider registration did not yield one live tool: "
            + json.dumps(safe_diagnostics, sort_keys=True)
            + f"; probe={probe_diagnostic}; raw_shape="
            + json.dumps(raw_shape, sort_keys=True)
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

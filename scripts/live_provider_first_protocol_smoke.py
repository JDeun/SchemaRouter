from __future__ import annotations

import argparse
import asyncio
import json
from time import perf_counter
from typing import Any

from compatibility_report import new_report, write_report

from schemarouter import ExecutionPlan, SchemaRouter, ToolCall


async def _execute_apis_guru(
    router: SchemaRouter,
    tool_key: str,
) -> tuple[str, str, bool, object]:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint("getMetrics")
    call = ToolCall(
        tool=tool.key,
        endpoint=endpoint.name,
        arguments={},
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    plan = ExecutionPlan(
        query="APIs.guru directory metrics",
        registry_version=router.registry.version,
        calls=[call],
    )
    results = await router.execute(plan)
    assert len(results) == 1
    assert isinstance(results[0].data, dict)
    assert isinstance(results[0].data.get("numAPIs"), int)
    assert results[0].data["numAPIs"] > 0
    return endpoint.name, "object", endpoint.auth_required, results[0].data["numAPIs"]


async def _execute_rick_and_morty(
    router: SchemaRouter,
    tool_key: str,
) -> tuple[str, str, bool, object]:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint("location")
    available_fields = {field.name for field in endpoint.output_fields}
    fields = [
        field
        for field in ("id", "name", "type", "dimension")
        if field in available_fields
    ]
    assert {"id", "name"} <= set(fields)
    call = ToolCall(
        tool=tool.key,
        endpoint=endpoint.name,
        arguments={"id": "1"},
        fields=fields,
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    plan = ExecutionPlan(
        query="Rick and Morty location identity",
        registry_version=router.registry.version,
        calls=[call],
    )
    results = await router.execute(plan)
    assert len(results) == 1
    assert isinstance(results[0].data, dict)
    assert str(results[0].data.get("id")) == "1"
    assert isinstance(results[0].data.get("name"), str)
    return endpoint.name, "object", endpoint.auth_required, fields


async def _execute_odata_reference(
    router: SchemaRouter,
    tool_key: str,
) -> tuple[str, str, bool, object]:
    tool = router.registry.get(tool_key)
    endpoint = tool.endpoint("list_products")
    available_fields = {field.name for field in endpoint.output_fields}
    fields = [
        field
        for field in ("ID", "Name", "Description", "ReleaseDate")
        if field in available_fields
    ]
    assert {"ID", "Name"} <= set(fields)
    call = ToolCall(
        tool=tool.key,
        endpoint=endpoint.name,
        arguments={"top": 1},
        fields=fields,
        schema_fingerprint=endpoint.fingerprint,
        tool_fingerprint=tool.fingerprint,
    )
    plan = ExecutionPlan(
        query="one OData reference product",
        registry_version=router.registry.version,
        calls=[call],
    )
    results = await router.execute(plan)
    assert len(results) == 1
    assert isinstance(results[0].data, list)
    assert results[0].data
    assert isinstance(results[0].data[0], dict)
    assert results[0].data[0].get("ID") is not None
    assert isinstance(results[0].data[0].get("Name"), str)
    return endpoint.name, "array<object>", endpoint.auth_required, fields


_EXECUTORS = {
    "apis-guru": _execute_apis_guru,
    "rick-and-morty-api": _execute_rick_and_morty,
    "odata-v4-reference": _execute_odata_reference,
}


async def run_smoke(provider: str) -> dict[str, Any]:
    router = SchemaRouter()
    try:
        resolution = router.resolve_provider(provider)
        assert len(resolution.methods) == 1
        method = resolution.methods[0]
        assert method.status == "available"
        assert method.url is not None

        started = perf_counter()
        registration = await router.add_provider(provider)
        discovery_ms = round((perf_counter() - started) * 1000, 2)

        assert registration.provider_id == resolution.provider_id
        assert len(registration.registered_tool_keys) == 1
        assert len(registration.methods) == 1
        assert registration.methods[0].status == "registered"

        tool_key = registration.registered_tool_keys[0]
        tool = router.registry.get(tool_key)
        assert tool.provider == resolution.provider_id
        assert tool.access_mode == method.access_mode

        started = perf_counter()
        endpoint_name, returned_shape, auth_required, selected = await _EXECUTORS[
            provider
        ](router, tool_key)
        execution_ms = round((perf_counter() - started) * 1000, 2)

        return {
            "evidence_kind": "live_public_provider",
            "provider": resolution.display_name,
            "provider_id": resolution.provider_id,
            "provider_first": True,
            "method_id": method.method_id,
            "method_kind": method.kind,
            "access_mode": method.access_mode,
            "source": method.url,
            "discovery_success": True,
            "tool_count": 1,
            "endpoint_count": len(tool.endpoints),
            "execution_bound": router.executor.is_binding_ready_for_contract(
                tool.key,
                tool.fingerprint,
            ),
            "execution_success": True,
            "safe_endpoint": endpoint_name,
            "returned_shape": returned_shape,
            "selected_evidence": selected,
            "discovery_latency_ms": discovery_ms,
            "execution_latency_ms": execution_ms,
            "auth_required": auth_required,
            "known_quirks": [
                "Public provider availability is external infrastructure state."
            ],
        }
    finally:
        await router.aclose()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--provider", choices=sorted(_EXECUTORS), required=True)
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    router = SchemaRouter()
    resolution = router.resolve_provider(args.provider)
    await router.aclose()
    source = resolution.methods[0].url or "provider-profile"

    report = new_report(
        adapter=(
            f"provider-profile:{args.provider}:{resolution.methods[0].kind}"
        ),
        source=source,
    )
    report["details"] = {
        "evidence_kind": "live_public_provider",
        "provider": resolution.display_name,
        "provider_id": resolution.provider_id,
        "provider_first": True,
    }

    try:
        report["details"].update(await run_smoke(args.provider))
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

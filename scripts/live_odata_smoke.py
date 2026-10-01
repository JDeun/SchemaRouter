from __future__ import annotations

import argparse
import asyncio
import json
import os
from time import perf_counter

from compatibility_report import new_report, write_report

from schemarouter import ExecutionPlan, SchemaRouter, ToolCall

DEFAULT_URL = "https://services.odata.org/V4/OData/OData.svc/"


async def run_smoke(url: str) -> dict[str, object]:
    started = perf_counter()
    router = await SchemaRouter.from_url(url, kind="odata")
    discovery_ms = round((perf_counter() - started) * 1000, 2)

    tools = router.registry.tools()
    assert len(tools) == 1
    tool = tools[0]
    endpoint = tool.endpoint("list_products")
    assert endpoint.read_only is True

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
        query="one OData product",
        registry_version=router.registry.version,
        calls=[call],
    )

    started = perf_counter()
    results = await router.execute(plan)
    execution_ms = round((perf_counter() - started) * 1000, 2)

    assert len(results) == 1
    assert isinstance(results[0].data, list)
    assert results[0].data
    assert isinstance(results[0].data[0], dict)
    assert results[0].data[0].get("ID") is not None
    assert isinstance(results[0].data[0].get("Name"), str)

    return {
        "evidence_kind": "live_public_provider",
        "provider": "OData.org V4 reference service",
        "discovery_success": True,
        "tool_count": len(tools),
        "endpoint_count": len(tool.endpoints),
        "execution_bound": router.executor.is_binding_ready_for_contract(
            tool.key,
            tool.fingerprint,
        ),
        "execution_success": True,
        "safe_endpoint": endpoint.name,
        "returned_shape": "array<object>",
        "selected_fields": fields,
        "discovery_latency_ms": discovery_ms,
        "execution_latency_ms": execution_ms,
        "auth_required": endpoint.auth_required,
        "known_quirks": [
            "Only a read-only Products GET with $top=1 is exercised.",
        ],
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()
    url = os.environ.get("SCHEMAROUTER_LIVE_ODATA_URL", DEFAULT_URL)
    report = new_report(adapter="odata", source=url)
    report["details"] = {
        "evidence_kind": "live_public_provider",
        "provider": "OData.org V4 reference service",
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

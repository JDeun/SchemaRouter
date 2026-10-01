from __future__ import annotations

import argparse
import asyncio
import json
import os
from time import perf_counter

from compatibility_report import new_report, write_report

from schemarouter import ExecutionPlan, SchemaRouter, ToolCall

DEFAULT_URL = "https://countries.trevorblades.com/"


def _shape(value: object) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "null"
    return type(value).__name__


async def run_smoke(url: str, report: dict[str, object]) -> dict[str, object]:
    started = perf_counter()
    router = await SchemaRouter.from_url(url, kind="graphql")
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

    try:
        tool = router.registry.tools()[0]
        endpoint = tool.endpoint("country")
        available = {field.name for field in endpoint.output_fields}
        fields = [field for field in ("code", "name") if field in available]
        if not fields:
            raise AssertionError(
                "Countries GraphQL country query exposes no expected scalar fields"
            )

        call = ToolCall(
            tool=tool.key,
            endpoint=endpoint.name,
            arguments={"code": "KR"},
            fields=fields,
            schema_fingerprint=endpoint.fingerprint,
            tool_fingerprint=tool.fingerprint,
        )
        plan = ExecutionPlan(
            query="South Korea country code and name",
            registry_version=router.registry.version,
            calls=[call],
        )

        execution_started = perf_counter()
        result = (await router.execute(plan))[0]
        report["execution"] = {
            "attempted": True,
            "safe_read_only": endpoint.read_only is True,
            "endpoint": endpoint.name,
            "success": True,
            "latency_ms": round(
                (perf_counter() - execution_started) * 1000,
                2,
            ),
            "result_shape": _shape(result.data),
        }

        return {
            "tool": tool.key,
            "endpoint": endpoint.name,
            "fields": fields,
            "result": result.data,
        }
    finally:
        await router.aclose()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    url = os.environ.get("SCHEMAROUTER_LIVE_GRAPHQL_URL", DEFAULT_URL)
    report = new_report(
        adapter="graphql",
        source=url,
        provider="Countries GraphQL API",
        authentication="none",
    )
    report["known_quirks"] = [
        "Public introspection and query endpoint; availability is externally owned.",
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

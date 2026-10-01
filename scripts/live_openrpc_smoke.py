from __future__ import annotations

import argparse
import asyncio
import json
import os
from time import perf_counter

from compatibility_report import new_report, write_report

from schemarouter import SchemaRouter

DEFAULT_URL = (
    "https://raw.githubusercontent.com/open-rpc/examples/"
    "dce69463ba9a3ca2232506b734606fa97f25dd45/"
    "service-descriptions/petstore-openrpc.json"
)


async def run_smoke(url: str, report: dict[str, object]) -> dict[str, object]:
    started = perf_counter()
    router = await SchemaRouter.from_url(url, kind="openrpc")

    try:
        tools = router.registry.tools()
        if len(tools) != 1:
            raise AssertionError("OpenRPC reference document should produce one tool")

        tool = tools[0]
        report["protocol_version"] = tool.metadata.get("openrpc_version")
        report["discovery"] = {
            "success": True,
            "tool_count": 1,
            "endpoint_count": len(tool.endpoints),
            "execution_bound": (
                router.executor.binding_status_for_contract(
                    tool.key,
                    tool.fingerprint,
                )
                == "ready"
            ),
            "latency_ms": round((perf_counter() - started) * 1000, 2),
        }

        # The official example advertises localhost as its JSON-RPC server.
        # SchemaRouter intentionally refuses to turn that cross-origin suggestion
        # into execution authority, so this is schema compatibility evidence only.
        report["execution"] = {
            "attempted": False,
            "safe_read_only": None,
            "endpoint": None,
            "success": False,
            "latency_ms": None,
            "result_shape": None,
        }

        expected = {"list_pets", "create_pet", "get_pet"}
        discovered = {endpoint.name for endpoint in tool.endpoints}
        if not expected <= discovered:
            raise AssertionError(
                "OpenRPC reference document is missing expected petstore methods"
            )
        if tool.execution_metadata.get("execution_bound") is not False:
            raise AssertionError(
                "cross-origin localhost OpenRPC server must remain unbound"
            )

        return {
            "tool": tool.key,
            "openrpc_version": tool.metadata.get("openrpc_version"),
            "api_version": tool.metadata.get("api_version"),
            "methods": sorted(discovered),
            "execution_bound": False,
        }
    finally:
        await router.aclose()


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    url = os.environ.get("SCHEMAROUTER_LIVE_OPENRPC_URL", DEFAULT_URL)
    report = new_report(
        adapter="openrpc",
        source=url,
        provider="OpenRPC examples repository",
        evidence_mode="public-reference-document",
        authentication="none",
    )
    report["known_quirks"] = [
        (
            "The pinned official Petstore OpenRPC document advertises localhost "
            "for execution, so scheduled evidence validates discovery only."
        ),
        (
            "A public JSON-RPC endpoint is not fabricated or trusted merely "
            "because a public OpenRPC document exists."
        ),
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

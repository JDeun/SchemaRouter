from __future__ import annotations

import argparse
import asyncio
import json
from time import perf_counter

from compatibility_report import new_report, write_report

from schemarouter import PlanRequest, SchemaRouter

PROVIDER_ID = "crossref"
BASE_URL = "https://api.crossref.org/v1"


async def run_smoke() -> dict[str, object]:
    router = SchemaRouter()
    resolution = router.resolve_provider(PROVIDER_ID)
    assert resolution.provider_id == PROVIDER_ID
    assert len(resolution.methods) == 1
    assert resolution.methods[0].status == "available"
    assert resolution.methods[0].url == BASE_URL

    started = perf_counter()
    registration = await router.add_provider(
        PROVIDER_ID,
        trusted_headers_by_method={
            "rest": {
                "User-Agent": (
                    "SchemaRouter compatibility smoke "
                    "(https://github.com/JDeun/SchemaRouter)"
                )
            }
        },
    )
    registration_ms = round((perf_counter() - started) * 1000, 2)

    assert registration.registered_tool_keys
    assert registration.methods[0].status == "registered"
    tool_key = registration.registered_tool_keys[0]
    tool = router.registry.get(tool_key)
    assert tool.provider == PROVIDER_ID
    assert tool.access_mode == "http_json"

    plan = router.plan_executable(
        PlanRequest(
            query="search Crossref works metadata",
            preferred_tools=[tool_key],
            arguments={"query": "materials science", "rows": 1},
        )
    )
    assert plan.executable
    assert plan.calls[0].endpoint == "search_works"
    plan.calls[0].fields = ["message"]

    execution_started = perf_counter()
    results = await router.execute(plan)
    execution_ms = round((perf_counter() - execution_started) * 1000, 2)

    assert len(results) == 1
    message = results[0].data["message"]
    assert isinstance(message, dict)
    items = message.get("items")
    assert isinstance(items, list)
    assert items
    first = items[0]
    assert isinstance(first, dict)
    assert first.get("DOI")

    return {
        "evidence_kind": "live_public_provider",
        "provider": "Crossref",
        "provider_id": PROVIDER_ID,
        "provider_resolution_success": True,
        "registration_success": True,
        "execution_success": True,
        "registered_access_mode": tool.access_mode,
        "source": BASE_URL,
        "tool": tool_key,
        "safe_endpoint": plan.calls[0].endpoint,
        "first_doi": first["DOI"],
        "registration_latency_ms": registration_ms,
        "execution_latency_ms": execution_ms,
    }


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    report = new_report(adapter="provider-profile", source=BASE_URL)
    report["details"] = {
        "evidence_kind": "live_public_provider",
        "provider": "Crossref",
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

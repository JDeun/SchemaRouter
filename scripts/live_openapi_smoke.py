from __future__ import annotations

import asyncio
import os

from schemarouter import PlanRequest, SchemaRouter

DEFAULT_OPENAPI_URL = "https://petstore3.swagger.io/api/v3/openapi.json"


async def main() -> None:
    url = os.environ.get("SCHEMAROUTER_LIVE_OPENAPI_URL", DEFAULT_OPENAPI_URL)
    router = await SchemaRouter.from_url(url, kind="openapi")

    tools = router.registry.tools()
    tool = next(
        candidate
        for candidate in tools
        if any(endpoint.name == "getInventory" for endpoint in candidate.endpoints)
    )
    endpoint = tool.endpoint("getInventory")

    assert endpoint.read_only is True
    assert endpoint.output_schema.get("type") == "object"

    plan = router.plan(
        PlanRequest(
            query="store inventory pet status counts",
            preferred_tools=[tool.key],
            max_calls=32,
        )
    )
    call = next(candidate for candidate in plan.calls if candidate.endpoint == "getInventory")
    assert call.executable
    selected_plan = plan.model_copy(update={"calls": [call]}, deep=True)

    results = await router.execute(selected_plan)
    assert len(results) == 1
    assert isinstance(results[0].data, dict)

    print(
        {
            "source": url,
            "tool": tool.key,
            "endpoint": call.endpoint,
            "keys": sorted(results[0].data)[:10],
        }
    )


if __name__ == "__main__":
    asyncio.run(main())

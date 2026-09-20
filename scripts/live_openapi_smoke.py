from __future__ import annotations

import asyncio
import os

from schemarouter import PlanRequest, SchemaRouter

DEFAULT_OPENAPI_URL = "https://api.apis.guru/v2/openapi.yaml"


async def main() -> None:
    url = os.environ.get("SCHEMAROUTER_LIVE_OPENAPI_URL", DEFAULT_OPENAPI_URL)
    router = await SchemaRouter.from_url(url, kind="openapi")

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

    results = await router.execute(selected_plan)
    assert len(results) == 1
    assert isinstance(results[0].data, dict)
    assert isinstance(results[0].data.get("numAPIs"), int)
    assert results[0].data["numAPIs"] > 0

    print(
        {
            "source": url,
            "tool": tool.key,
            "endpoint": call.endpoint,
            "numAPIs": results[0].data["numAPIs"],
        }
    )


if __name__ == "__main__":
    asyncio.run(main())

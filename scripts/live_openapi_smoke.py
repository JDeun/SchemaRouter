from __future__ import annotations

import asyncio
import os

from schemarouter import PlanRequest, SchemaRouter

DEFAULT_OPENAPI_URL = "https://cjav.dev/openapi.json"


async def main() -> None:
    url = os.environ.get("SCHEMAROUTER_LIVE_OPENAPI_URL", DEFAULT_OPENAPI_URL)
    router = await SchemaRouter.from_url(url, kind="openapi")

    endpoint_name = "get_api_v1_articles"
    tools = router.registry.tools()
    tool = next(
        candidate
        for candidate in tools
        if any(endpoint.name == endpoint_name for endpoint in candidate.endpoints)
    )
    endpoint = tool.endpoint(endpoint_name)

    assert endpoint.read_only is True
    assert endpoint.output_schema.get("type") == "object"

    plan = router.plan(
        PlanRequest(
            query="list published articles",
            preferred_tools=[tool.key],
            arguments={"page": 1},
            max_calls=32,
        )
    )
    call = next(candidate for candidate in plan.calls if candidate.endpoint == endpoint_name)
    assert call.executable
    selected_plan = plan.model_copy(update={"calls": [call]}, deep=True)

    results = await router.execute(selected_plan)
    assert len(results) == 1
    assert isinstance(results[0].data, dict)
    assert "data" in results[0].data
    assert "meta" in results[0].data

    print(
        {
            "source": url,
            "tool": tool.key,
            "endpoint": call.endpoint,
            "result_count": len(results[0].data.get("data", [])),
        }
    )


if __name__ == "__main__":
    asyncio.run(main())

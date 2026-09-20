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
        if any(endpoint.name == "findPetsByStatus" for endpoint in candidate.endpoints)
    )
    endpoint = tool.endpoint("findPetsByStatus")

    assert endpoint.read_only is True
    assert endpoint.output_schema.get("type") == "array"
    assert "components" in endpoint.output_schema

    plan = router.plan(
        PlanRequest(
            query="find pets by status",
            preferred_tools=[tool.key],
            arguments={"status": "available"},
        )
    )
    assert plan.executable
    assert plan.calls[0].endpoint == "findPetsByStatus"

    results = await router.execute(plan)
    assert len(results) == 1
    assert isinstance(results[0].data, list)

    print(
        {
            "source": url,
            "tool": tool.key,
            "endpoint": plan.calls[0].endpoint,
            "result_count": len(results[0].data),
        }
    )


if __name__ == "__main__":
    asyncio.run(main())

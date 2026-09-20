from __future__ import annotations

import asyncio
import os

from schemarouter import PlanRequest, SchemaRouter

DEFAULT_OPENAPI_URL = "https://hopinjobs.com/openapi.json"
DEFAULT_BASE_URL = "https://api.hopinjobs.com"


async def main() -> None:
    url = os.environ.get("SCHEMAROUTER_LIVE_OPENAPI_URL", DEFAULT_OPENAPI_URL)
    base_url = os.environ.get("SCHEMAROUTER_LIVE_OPENAPI_BASE_URL", DEFAULT_BASE_URL)
    router = await SchemaRouter.from_url(
        url,
        kind="openapi",
        base_url=base_url,
    )

    endpoint_name = "getHealth"
    tools = router.registry.tools()
    tool = next(
        candidate
        for candidate in tools
        if any(endpoint.name == endpoint_name for endpoint in candidate.endpoints)
    )
    endpoint = tool.endpoint(endpoint_name)

    assert endpoint.read_only is True
    assert tool.metadata["execution_bound"] is True
    assert tool.metadata["approved_base_url"] == base_url

    plan = router.plan(
        PlanRequest(
            query="api service health",
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
    assert results[0].data.get("status") == "ok"

    print(
        {
            "source": url,
            "base_url": base_url,
            "tool": tool.key,
            "endpoint": call.endpoint,
            "status": results[0].data.get("status"),
        }
    )


if __name__ == "__main__":
    asyncio.run(main())

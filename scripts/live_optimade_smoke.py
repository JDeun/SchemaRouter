from __future__ import annotations

import asyncio
import os

from schemarouter import PlanRequest, SchemaRouter

DEFAULT_URL = "https://www.crystallography.net/cod/optimade"


async def main() -> None:
    url = os.environ.get("SCHEMAROUTER_LIVE_OPTIMADE_URL", DEFAULT_URL)
    router = await SchemaRouter.from_url(url, kind="optimade")

    keys = router.registry.keys()
    assert len(keys) == 1
    tool_key = keys[0]
    tool = router.registry.get(tool_key)
    assert tool.metadata["adapter"] == "optimade"
    assert tool.metadata["api_version"]

    endpoint_names = {endpoint.name for endpoint in tool.endpoints}
    assert "search_structures" in endpoint_names

    plan = router.plan(
        PlanRequest(
            query="chemical formula descriptive nelements",
            preferred_tools=[tool_key],
            arguments={
                "filter": 'elements HAS ALL "Si","O" AND nelements=2',
                "page_limit": 1,
            },
        )
    )
    assert plan.executable
    assert plan.calls[0].endpoint == "search_structures"
    assert "chemical_formula_descriptive" in plan.calls[0].fields
    assert "nelements" in plan.calls[0].fields

    results = await router.execute(plan)
    assert len(results) == 1
    assert isinstance(results[0].data, list)
    assert results[0].data
    first = results[0].data[0]
    assert first["id"]
    assert first["type"] == "structures"
    assert "chemical_formula_descriptive" in first
    assert "nelements" in first


if __name__ == "__main__":
    asyncio.run(main())

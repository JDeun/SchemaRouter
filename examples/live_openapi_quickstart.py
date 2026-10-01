"""Five-minute live quickstart using the public APIs.guru OpenAPI contract."""

from __future__ import annotations

import asyncio

import httpx

from schemarouter import PlanRequest, SchemaRouter, ToolResult

DEFAULT_SOURCE = "https://api.apis.guru/v2/openapi.yaml"
METRICS_ENDPOINT = "getMetrics"


async def run_quickstart(
    source: str = DEFAULT_SOURCE,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> ToolResult:
    """Discover, select, execute, and validate one real provider capability."""

    router = await SchemaRouter.from_url(
        source,
        kind="openapi",
        http_client=http_client,
    )
    async with router:
        tool = next(
            candidate
            for candidate in router.registry.tools()
            if any(
                endpoint.name == METRICS_ENDPOINT
                for endpoint in candidate.endpoints
            )
        )
        print(f"source: {source}")
        print(
            "discovered: "
            f"{tool.key}:{METRICS_ENDPOINT} "
            f"({len(tool.endpoints)} endpoints on this tool)"
        )

        plan = router.plan(
            PlanRequest(
                query="API directory metrics total number of APIs",
                preferred_tools=[tool.key],
                max_calls=1,
            )
        )
        if len(plan.calls) != 1 or plan.calls[0].endpoint != METRICS_ENDPOINT:
            raise RuntimeError("planner did not select the APIs.guru metrics route")
        call = plan.calls[0]
        print(f"selected: {call.tool}:{call.endpoint}")

        result = (await router.execute(plan))[0]
        if not isinstance(result.data, dict):
            raise RuntimeError("APIs.guru metrics result was not an object")
        num_apis = result.data.get("numAPIs")
        if not isinstance(num_apis, int) or num_apis <= 0:
            raise RuntimeError("APIs.guru did not return a positive numAPIs")

        print(f"current numAPIs: {num_apis}")
        return result


def main() -> None:
    asyncio.run(run_quickstart())


if __name__ == "__main__":
    main()

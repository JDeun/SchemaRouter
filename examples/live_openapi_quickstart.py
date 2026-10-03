"""Five-minute live quickstart using provider-first APIs.guru registration."""

from __future__ import annotations

import asyncio

import httpx

from schemarouter import (
    PlanRequest,
    ProviderAccessMethod,
    ProviderProfile,
    SchemaRouter,
    ToolResult,
)

DEFAULT_PROVIDER = "apis-guru"
DEFAULT_SOURCE = "https://api.apis.guru/v2/openapi.yaml"
METRICS_ENDPOINT = "getMetrics"


async def run_quickstart(
    source: str = DEFAULT_SOURCE,
    *,
    http_client: httpx.AsyncClient | None = None,
) -> ToolResult:
    """Resolve a provider, register its adapter path, and execute one live capability."""

    router = SchemaRouter(http_client=http_client)
    provider_id = DEFAULT_PROVIDER

    if source != DEFAULT_SOURCE:
        provider_id = "quickstart-openapi"
        router.register_provider_profile(
            ProviderProfile(
                provider_id=provider_id,
                display_name="Quickstart OpenAPI fixture",
                methods=(
                    ProviderAccessMethod(
                        method_id="openapi",
                        kind="openapi",
                        access_mode="openapi",
                        url=source,
                    ),
                ),
            )
        )

    async with router:
        registration = await router.add_provider(provider_id)
        if len(registration.registered_tool_keys) != 1:
            raise RuntimeError(
                f"expected one registered tool for {provider_id}, "
                f"got {registration.registered_tool_keys!r}"
            )

        tool = router.registry.get(registration.registered_tool_keys[0])
        if not any(endpoint.name == METRICS_ENDPOINT for endpoint in tool.endpoints):
            raise RuntimeError("provider registration did not expose APIs.guru metrics")

        print(f"provider: {provider_id}")
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

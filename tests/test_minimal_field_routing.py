import httpx
import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    InvocationUnavailableError,
    ParameterSpec,
    PlanRequest,
    SchemaRouter,
    ServerProjectionSpec,
    ToolSpec,
)
from schemarouter.adapters import OpenAPIRemoteInvoker


@pytest.mark.asyncio
async def test_elastic_modulus_query_uses_only_healthy_minimal_access_path() -> None:
    router = SchemaRouter(unavailable_cooldown_seconds=60)

    optimade = ToolSpec(
        name="provider_b_optimade",
        provider="provider_b",
        access_mode="optimade",
        endpoints=[
            EndpointSpec(
                name="search",
                description="Search elastic properties",
                read_only=True,
                parameters=[
                    ParameterSpec(
                        name="formula",
                        required=True,
                        location="query",
                    )
                ],
                output_fields=[
                    FieldSpec(
                        name="elastic_modulus",
                        aliases=["탄성계수", "elastic modulus"],
                    ),
                    FieldSpec(
                        name="density",
                        aliases=["밀도", "density"],
                    ),
                ],
                output_schema={
                    "type": "object",
                    "properties": {
                        "elastic_modulus": {"type": "number"},
                        "density": {"type": "number"},
                    },
                },
            )
        ],
    )
    rest = ToolSpec(
        name="provider_a_rest",
        provider="provider_a",
        access_mode="openapi",
        remote=True,
        execution_metadata={"adapter": "openapi"},
        endpoints=[
            EndpointSpec(
                name="search",
                description="Search elastic properties",
                method="GET",
                path="/materials",
                read_only=True,
                parameters=[
                    ParameterSpec(
                        name="formula",
                        required=True,
                        location="query",
                    )
                ],
                output_fields=[
                    FieldSpec(
                        name="elastic_modulus",
                        aliases=["탄성계수", "elastic modulus"],
                    ),
                    FieldSpec(
                        name="density",
                        aliases=["밀도", "density"],
                    ),
                ],
                output_schema={
                    "type": "object",
                    "properties": {
                        "elastic_modulus": {"type": "number"},
                        "density": {"type": "number"},
                    },
                },
                server_projection=ServerProjectionSpec(parameter="fields"),
            )
        ],
    )

    router.add_tool(optimade)
    router.add_tool(rest)

    optimade_calls = 0
    rest_queries: list[dict[str, str]] = []

    def unavailable_optimade(endpoint: str, arguments: dict) -> dict:
        nonlocal optimade_calls
        optimade_calls += 1
        raise InvocationUnavailableError("OPTIMADE temporarily unavailable")

    def rest_handler(request: httpx.Request) -> httpx.Response:
        rest_queries.append(dict(request.url.params))
        return httpx.Response(
            200,
            json={
                "elastic_modulus": 130.0,
                # Even if a provider ignores the selector, local projection must remove this.
                "density": 2.33,
            },
            request=request,
        )

    router.executor.bind("provider_b_optimade", unavailable_optimade)

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(rest_handler)
    ) as client:
        router.executor.bind(
            "provider_a_rest",
            OpenAPIRemoteInvoker(
                rest,
                "https://provider-a.example",
                http_client=client,
            ),
        )

        request = PlanRequest(
            query="Si의 탄성계수를 알려줘",
            arguments={"formula": "Si"},
            preferred_tools=["provider_b_optimade"],
            fallback_scope="cross_provider",
            max_fallbacks=2,
        )

        first_plan = router.plan(request)
        assert first_plan.calls[0].tool == "provider_b_optimade"
        assert first_plan.calls[0].fields == ["elastic_modulus"]
        assert first_plan.calls[0].required_fields == ["elastic_modulus"]
        first_route = first_plan.fallback_route(0)
        assert first_route is not None
        assert [call.tool for call in first_route.alternatives] == [
            "provider_a_rest"
        ]
        assert first_route.alternatives[0].required_fields == ["elastic_modulus"]

        first_result = (await router.execute(first_plan))[0]

        assert first_result.tool == "provider_a_rest"
        assert first_result.data == {"elastic_modulus": 130.0}
        assert optimade_calls == 1
        assert rest_queries == [
            {
                "formula": "Si",
                "fields": "elastic_modulus",
            }
        ]
        assert router.unavailable_access_paths() == (
            ("provider_b_optimade", "search"),
        )

        # The second question is replanned with live local availability. The known-down
        # OPTIMADE route is not selected as primary again.
        second_plan = router.plan(request)
        assert second_plan.calls[0].tool == "provider_a_rest"
        assert second_plan.calls[0].required_fields == ["elastic_modulus"]
        second_result = (await router.execute(second_plan))[0]

        assert second_result.data == {"elastic_modulus": 130.0}
        assert optimade_calls == 1
        assert rest_queries[-1] == {
            "formula": "Si",
            "fields": "elastic_modulus",
        }

        # A trusted health signal can reopen the path; planning can prefer it again.
        router.mark_access_available("provider_b_optimade", "search")
        router.executor.bind(
            "provider_b_optimade",
            lambda endpoint, arguments: {"elastic_modulus": 145.0},
        )
        third_plan = router.plan(request)
        assert third_plan.calls[0].tool == "provider_b_optimade"
        third_result = (await router.execute(third_plan))[0]

    assert third_result.data == {"elastic_modulus": 145.0}

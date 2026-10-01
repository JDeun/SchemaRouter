"""Offline example: satisfy one request with complementary providers."""

from __future__ import annotations

import asyncio

from schemarouter import EndpointSpec, FieldSpec, PlanRequest, SchemaRouter, ToolSpec


def _tool(
    *,
    name: str,
    provider: str,
    field: FieldSpec,
    output_schema: dict[str, object],
) -> ToolSpec:
    return ToolSpec(
        name=name,
        provider=provider,
        access_mode="sdk",
        endpoints=[
            EndpointSpec(
                name="lookup",
                read_only=True,
                destructive=False,
                output_schema=output_schema,
                output_fields=[
                    FieldSpec(
                        name="customer_id",
                        identifier=True,
                        json_schema={"type": "string"},
                    ),
                    field,
                ],
            )
        ],
    )


async def crm_invoker(
    endpoint: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    del arguments
    assert endpoint == "lookup"
    return {"customer_id": "C-42", "customer_name": "Ada Lovelace"}


async def billing_invoker(
    endpoint: str,
    arguments: dict[str, object],
) -> dict[str, object]:
    del arguments
    assert endpoint == "lookup"
    return {"customer_id": "C-42", "balance_usd": 19.75}


async def main() -> None:
    router = SchemaRouter()
    crm = _tool(
        name="customer_profile",
        provider="example-crm",
        field=FieldSpec(
            name="customer_name",
            semantic_id="customer.name",
            aliases=["customer name"],
            json_schema={"type": "string"},
        ),
        output_schema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "customer_name": {"type": "string"},
            },
            "required": ["customer_id", "customer_name"],
        },
    )
    billing = _tool(
        name="account_balance",
        provider="example-billing",
        field=FieldSpec(
            name="balance_usd",
            semantic_id="billing.account_balance",
            aliases=["account balance", "balance"],
            json_schema={"type": "number"},
            unit="USD",
        ),
        output_schema={
            "type": "object",
            "properties": {
                "customer_id": {"type": "string"},
                "balance_usd": {"type": "number"},
            },
            "required": ["customer_id", "balance_usd"],
        },
    )

    router.add_bound_tool(crm, crm_invoker)
    router.add_bound_tool(billing, billing_invoker)

    plan = router.plan_executable(
        PlanRequest(
            query="customer name and account balance",
            max_calls=2,
        )
    )
    assert {call.tool for call in plan.calls} == {
        "customer_profile",
        "account_balance",
    }
    assert plan.coverage is not None and plan.coverage.complete

    results = await router.execute(plan)
    for result in results:
        tool = router.registry.get(result.tool)
        print(f"{tool.provider}: {result.data}")


if __name__ == "__main__":
    asyncio.run(main())

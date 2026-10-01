"""Offline example: bind an SDK/client behind an explicit trusted ToolSpec."""

from __future__ import annotations

import asyncio

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PlanRequest,
    SchemaRouter,
    ToolSpec,
)


class MarketSDK:
    """Small deterministic stand-in for an application-owned SDK client."""

    async def __call__(self, endpoint: str, arguments: dict[str, object]) -> dict[str, object]:
        if endpoint != "quote":
            raise ValueError(f"unexpected endpoint: {endpoint}")
        symbol = str(arguments["symbol"])
        return {"symbol": symbol, "price": 123.45, "internal_note": "not declared"}


def market_tool() -> ToolSpec:
    return ToolSpec(
        name="market_lookup",
        provider="example-market-sdk",
        access_mode="sdk",
        description="Read a market quote from an application-owned SDK client.",
        endpoints=[
            EndpointSpec(
                name="quote",
                description="Get the current quote for one symbol.",
                read_only=True,
                destructive=False,
                parameters=[
                    ParameterSpec(
                        name="symbol",
                        required=True,
                        location="argument",
                        json_schema={"type": "string"},
                    )
                ],
                output_schema={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "price": {"type": "number"},
                        "internal_note": {"type": "string"},
                    },
                    "required": ["symbol", "price"],
                },
                output_fields=[
                    FieldSpec(
                        name="symbol",
                        identifier=True,
                        json_schema={"type": "string"},
                    ),
                    FieldSpec(
                        name="price",
                        semantic_id="finance.market_price",
                        aliases=["market price", "quote price"],
                        json_schema={"type": "number"},
                        unit="USD",
                    ),
                ],
            )
        ],
    )


async def main() -> None:
    router = SchemaRouter()
    key = router.add_bound_tool(market_tool(), MarketSDK())

    results = await router.ainvoke(
        PlanRequest(
            query="market price",
            preferred_tools=[key],
            arguments={"symbol": "AAPL"},
        )
    )

    result = results[0]
    assert result.data == {"symbol": "AAPL", "price": 123.45}
    assert "internal_note" not in result.data

    print(f"provider: {router.registry.get(key).provider}")
    print(f"access mode: {router.registry.get(key).access_mode}")
    print(f"projected result: {result.data}")


if __name__ == "__main__":
    asyncio.run(main())

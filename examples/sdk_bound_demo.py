"""Deterministic example of binding an opaque SDK behind an explicit ToolSpec."""

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
    async def quote(self, symbol: str) -> dict[str, object]:
        prices = {"AAPL": 123.45, "MSFT": 234.56}
        return {"symbol": symbol, "price": prices[symbol]}


class MarketInvoker:
    def __init__(self, client: MarketSDK) -> None:
        self.client = client

    async def __call__(
        self,
        endpoint: str,
        arguments: dict[str, object],
    ) -> dict[str, object]:
        if endpoint != "quote":
            raise KeyError(endpoint)
        return await self.client.quote(str(arguments["symbol"]))


async def main() -> None:
    router = SchemaRouter()
    tool = ToolSpec(
        name="market_lookup",
        provider="example-finance",
        access_mode="sdk",
        description="Explicit contract around an SDK that is not introspected.",
        endpoints=[
            EndpointSpec(
                name="quote",
                description="Return one current example quote.",
                read_only=True,
                destructive=False,
                parameters=[
                    ParameterSpec(
                        name="symbol",
                        required=True,
                        json_schema={"type": "string"},
                    )
                ],
                input_schema={
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                    "additionalProperties": False,
                },
                output_schema={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "price": {"type": "number"},
                    },
                    "required": ["symbol", "price"],
                    "additionalProperties": False,
                },
                output_fields=[
                    FieldSpec(
                        name="symbol",
                        identifier=True,
                        json_schema={"type": "string"},
                    ),
                    FieldSpec(
                        name="price",
                        semantic_id="finance.price",
                        aliases=["quote price", "stock price"],
                        json_schema={"type": "number"},
                    ),
                ],
            )
        ],
    )
    router.add_bound_tool(tool, MarketInvoker(MarketSDK()))

    results = await router.ainvoke(
        PlanRequest(
            query="stock quote price",
            preferred_tools=[tool.key],
            arguments={"symbol": "AAPL"},
        )
    )

    assert results[0].data["price"] == 123.45
    print(results[0].data)


if __name__ == "__main__":
    asyncio.run(main())

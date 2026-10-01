from __future__ import annotations

from dataclasses import dataclass

import pytest

from schemarouter import (
    EndpointSpec,
    FieldSpec,
    PlanRequest,
    RegistrationError,
    SchemaRouter,
    ToolCall,
    ToolSpec,
)


def _finance_tool() -> ToolSpec:
    return ToolSpec(
        name="market_lookup",
        provider="yahoo-finance",
        access_mode="sdk",
        description="Trusted SDK-backed market lookup",
        endpoints=[
            EndpointSpec(
                name="quote",
                read_only=True,
                destructive=False,
                parameters=[],
                output_schema={
                    "type": "object",
                    "properties": {
                        "symbol": {"type": "string"},
                        "price": {"type": "number"},
                    },
                    "required": ["symbol", "price"],
                },
                output_fields=[
                    FieldSpec(name="symbol", json_schema={"type": "string"}),
                    FieldSpec(name="price", json_schema={"type": "number"}),
                ],
            )
        ],
    )


class SDKInvoker:
    async def __call__(self, endpoint: str, arguments: dict) -> dict:
        assert endpoint == "quote"
        assert arguments == {}
        return {"symbol": "AAPL", "price": 123.45}


@pytest.mark.asyncio
async def test_add_bound_tool_runs_arbitrary_sdk_through_normal_contract() -> None:
    router = SchemaRouter()
    tool = _finance_tool()

    key = router.add_bound_tool(tool, SDKInvoker())

    assert key == tool.key
    assert router.executor.binding_states()[key] == "ready"

    result = await router.ainvoke(
        PlanRequest(
            query="market quote price",
            preferred_tools=[key],
        )
    )

    assert result[0].data == {"price": 123.45}
    assert result[0].projected_fields == ["price"]


@dataclass
class CallAwareSDKInvoker:
    seen_fields: list[str] | None = None

    async def invoke_call(self, call: ToolCall) -> dict:
        self.seen_fields = list(call.fields)
        return {"symbol": "AAPL", "price": 123.45}


@pytest.mark.asyncio
async def test_add_bound_tool_accepts_call_aware_invoker() -> None:
    router = SchemaRouter()
    tool = _finance_tool()
    invoker = CallAwareSDKInvoker()

    key = router.add_bound_tool(tool, invoker)
    plan = router.plan_executable(
        PlanRequest(
            query="price",
            preferred_tools=[key],
        )
    )
    assert plan.executable

    await router.execute(plan)

    assert invoker.seen_fields is not None
    assert "price" in invoker.seen_fields


def test_add_bound_tool_replacement_rebinds_exact_new_fingerprint() -> None:
    router = SchemaRouter()
    original = _finance_tool()
    router.add_bound_tool(original, SDKInvoker())

    payload = original.model_dump(mode="python")
    payload["description"] = "Updated trusted SDK-backed market lookup"
    replacement = ToolSpec.model_validate(payload)

    key = router.add_bound_tool(
        replacement,
        SDKInvoker(),
        replace=True,
    )

    assert key == original.key
    assert router.registry.get(key).fingerprint == replacement.fingerprint
    assert router.executor.binding_states()[key] == "ready"


def test_add_bound_tool_rejects_duplicate_without_replace() -> None:
    router = SchemaRouter()
    tool = _finance_tool()
    router.add_bound_tool(tool, SDKInvoker())

    with pytest.raises(RegistrationError, match="already registered"):
        router.add_bound_tool(tool, SDKInvoker())

import pytest

from schemarouter import (
    AdapterContext,
    AdapterLoadResult,
    AdapterRegistry,
    EndpointSpec,
    SchemaRouter,
    ToolSpec,
)


class DummyAdapter:
    def __init__(self, kind: str, priority: int, *, matches: bool = True) -> None:
        self.kind = kind
        self.priority = priority
        self.matches = matches
        self.calls: list[str] = []

    async def load(self, context: AdapterContext) -> AdapterLoadResult | None:
        self.calls.append(context.url)
        if not self.matches:
            return None
        return AdapterLoadResult(
            tool=ToolSpec(
                name=self.kind,
                endpoints=[
                    EndpointSpec(
                        name="read",
                        read_only=True,
                    )
                ],
                metadata={"adapter": self.kind},
            )
        )


def test_adapter_registry_orders_by_priority_and_rejects_collisions() -> None:
    low = DummyAdapter("low", 10)
    high = DummyAdapter("high", 50)
    registry = AdapterRegistry([low, high])

    assert registry.kinds() == ("high", "low")
    assert [adapter.kind for adapter in registry.ordered()] == ["high", "low"]

    with pytest.raises(ValueError, match="already registered"):
        registry.register(DummyAdapter("high", 100))


@pytest.mark.asyncio
async def test_router_can_register_and_explicitly_use_custom_adapter() -> None:
    adapter = DummyAdapter("custom", 10)
    router = SchemaRouter()
    router.register_adapter(adapter)

    tool = await router.add_url(
        "https://example.com/capability",
        kind="custom",
    )

    assert tool.key == "custom"
    assert adapter.calls == ["https://example.com/capability"]


@pytest.mark.asyncio
async def test_auto_discovery_uses_adapter_priority() -> None:
    low = DummyAdapter("low", 10)
    high = DummyAdapter("high", 50)
    registry = AdapterRegistry([low, high])
    router = SchemaRouter(adapter_registry=registry)

    tool = await router.add_url("https://example.com/capability")

    assert tool.key == "high"
    assert high.calls == ["https://example.com/capability"]
    assert low.calls == []

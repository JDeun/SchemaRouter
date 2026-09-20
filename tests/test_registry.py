import pytest

from schemarouter import EndpointSpec, InMemoryRegistry, RegistrationError, ToolSpec


def test_registry_rejects_collisions_without_replace() -> None:
    reg = InMemoryRegistry()
    tool = ToolSpec(name="demo", endpoints=[EndpointSpec(name="run")])
    reg.register(tool)
    with pytest.raises(RegistrationError):
        reg.register(tool)


def test_namespace_disambiguates_tools() -> None:
    reg = InMemoryRegistry()
    reg.register(ToolSpec(name="search", namespace="a", endpoints=[EndpointSpec(name="run")]))
    reg.register(ToolSpec(name="search", namespace="b", endpoints=[EndpointSpec(name="run")]))
    assert reg.keys() == ("a.search", "b.search")


def test_schema_router_accepts_structural_registry_implementation() -> None:
    from schemarouter import SchemaRouter

    class ProxyRegistry:
        def __init__(self) -> None:
            self.inner = InMemoryRegistry()

        @property
        def version(self) -> int:
            return self.inner.version

        def register(self, tool: ToolSpec, *, replace: bool = False) -> str:
            return self.inner.register(tool, replace=replace)

        def get(self, key: str) -> ToolSpec:
            return self.inner.get(key)

        def tools(self) -> tuple[ToolSpec, ...]:
            return self.inner.tools()

        def keys(self) -> tuple[str, ...]:
            return self.inner.keys()

        def endpoint(self, tool_key: str, endpoint_name: str) -> EndpointSpec:
            return self.inner.endpoint(tool_key, endpoint_name)

    registry = ProxyRegistry()
    router = SchemaRouter(registry=registry)
    router.add_tool(
        ToolSpec(
            name="custom",
            endpoints=[EndpointSpec(name="ping")],
        )
    )

    assert router.registry is registry
    assert registry.keys() == ("custom",)

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

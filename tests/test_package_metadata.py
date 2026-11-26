from importlib.metadata import distribution, version

from schemarouter import __version__


def test_installed_version_is_exposed() -> None:
    assert __version__ == version("schemarouter")


def test_retired_decision_providers_are_not_package_extras() -> None:
    package = distribution("schemarouter")
    extras = set(package.metadata.get_all("Provides-Extra") or [])
    assert {"jev", "systemone", "laya"}.isdisjoint(extras)
    assert {"mcp", "langchain", "langgraph", "llamaindex", "otel", "database"} <= extras
    for requirement in package.requires or []:
        assert not requirement.lower().startswith(("typesafe-sdk", "laya"))

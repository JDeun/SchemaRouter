from types import SimpleNamespace

import pytest

from schemarouter import AdapterRegistry, SchemaRouter
from schemarouter.adapters import plugins


class DemoAdapter:
    kind = "demo"
    priority = 42

    async def load(self, context):
        return None


class FakeEntryPoint:
    def __init__(self, name, value, loaded):
        self.name = name
        self.value = value
        self.dist = SimpleNamespace(
            metadata={"Name": f"dist-{name}"},
            version="1.2.3",
        )
        self._loaded = loaded

    def load(self):
        self._loaded.append(self.name)
        return DemoAdapter


class FakeEntryPoints(tuple):
    def select(self, *, group):
        if group == plugins.ADAPTER_ENTRY_POINT_GROUP:
            return self
        return ()


def _install_fake_entry_points(monkeypatch, *names):
    loaded = []
    entries = FakeEntryPoints(
        FakeEntryPoint(name, f"package_{name}:Adapter", loaded)
        for name in names
    )
    monkeypatch.setattr(plugins.metadata, "entry_points", lambda: entries)
    return loaded


def test_plugin_discovery_reads_metadata_without_importing_code(monkeypatch) -> None:
    loaded = _install_fake_entry_points(monkeypatch, "demo", "other")

    found = plugins.discover_adapter_plugins()

    assert [item.name for item in found] == ["demo", "other"]
    assert found[0].distribution == "dist-demo"
    assert found[0].version == "1.2.3"
    assert loaded == []


def test_plugin_loading_requires_explicit_non_empty_allowlist(monkeypatch) -> None:
    loaded = _install_fake_entry_points(monkeypatch, "demo")

    with pytest.raises(ValueError, match="non-empty explicit allowlist"):
        plugins.load_adapter_plugins(AdapterRegistry(), allowlist=[])

    assert loaded == []


def test_only_allowlisted_plugin_is_imported(monkeypatch) -> None:
    loaded = _install_fake_entry_points(monkeypatch, "demo", "other")
    registry = AdapterRegistry()

    kinds = plugins.load_adapter_plugins(registry, allowlist={"demo"})

    assert kinds == ("demo",)
    assert registry.kinds() == ("demo",)
    assert loaded == ["demo"]


def test_unknown_allowlisted_plugin_fails_before_import(monkeypatch) -> None:
    loaded = _install_fake_entry_points(monkeypatch, "demo")

    with pytest.raises(KeyError, match="missing"):
        plugins.load_adapter_plugins(AdapterRegistry(), allowlist={"demo", "missing"})

    assert loaded == []


def test_router_exposes_explicit_plugin_loader(monkeypatch) -> None:
    loaded = _install_fake_entry_points(monkeypatch, "demo")
    router = SchemaRouter()

    assert router.load_adapter_plugins(allowlist={"demo"}) == ("demo",)
    assert "demo" in router.adapter_registry.kinds()
    assert loaded == ["demo"]


def test_duplicate_plugin_names_fail_before_import(monkeypatch) -> None:
    loaded = []
    entries = FakeEntryPoints(
        [
            FakeEntryPoint("demo", "package_a:Adapter", loaded),
            FakeEntryPoint("demo", "package_b:Adapter", loaded),
        ]
    )
    monkeypatch.setattr(plugins.metadata, "entry_points", lambda: entries)

    with pytest.raises(RuntimeError, match="ambiguous adapter plugin"):
        plugins.load_adapter_plugins(AdapterRegistry(), allowlist={"demo"})

    assert loaded == []



def test_duplicate_adapter_kinds_fail_without_partial_registry_mutation(monkeypatch) -> None:
    loaded = _install_fake_entry_points(monkeypatch, "demo", "other")
    registry = AdapterRegistry()

    with pytest.raises(ValueError, match="duplicate adapter kinds"):
        plugins.load_adapter_plugins(
            registry,
            allowlist={"demo", "other"},
        )

    assert loaded == ["demo", "other"]
    assert registry.kinds() == ()

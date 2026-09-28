from __future__ import annotations

from types import SimpleNamespace

import pytest

from schemarouter import (
    DecisionOption,
    DecisionRequest,
    DecisionResult,
    DecisionSelection,
    choose_sync,
    discover_decision_backend_plugins,
    load_decision_backend_plugin,
)
from schemarouter import decision_plugins


class DemoBackend:
    def __init__(self, *, selected: str = "a") -> None:
        self.selected = selected

    def decide(self, request: DecisionRequest) -> DecisionResult:
        return DecisionResult(
            selections=[DecisionSelection(option_id=self.selected, score=1.0)]
        )


class FakeEntryPoint:
    def __init__(self, name: str, value: str, loaded, result) -> None:
        self.name = name
        self.value = value
        self.dist = SimpleNamespace(
            metadata={"Name": f"dist-{name}"},
            version="1.2.3",
        )
        self._loaded = loaded
        self._result = result

    def load(self):
        self._loaded.append(self.name)
        return self._result


class FakeEntryPoints(tuple):
    def select(self, *, group):
        if group == decision_plugins.DECISION_BACKEND_ENTRY_POINT_GROUP:
            return self
        return ()


def _install(monkeypatch, *entries):
    monkeypatch.setattr(
        decision_plugins.metadata,
        "entry_points",
        lambda: FakeEntryPoints(entries),
    )


def _request() -> DecisionRequest:
    return DecisionRequest(
        query="pick",
        options=[
            DecisionOption(id="a", label="A"),
            DecisionOption(id="b", label="B"),
        ],
    )


def test_discovery_reads_metadata_without_importing_plugins(monkeypatch) -> None:
    loaded: list[str] = []
    _install(
        monkeypatch,
        FakeEntryPoint("demo", "pkg_demo:create_backend", loaded, DemoBackend),
    )

    found = discover_decision_backend_plugins()

    assert [plugin.name for plugin in found] == ["demo"]
    assert found[0].value == "pkg_demo:create_backend"
    assert found[0].distribution == "dist-demo"
    assert found[0].version == "1.2.3"
    assert loaded == []


def test_load_class_plugin_with_explicit_config(monkeypatch) -> None:
    loaded: list[str] = []
    _install(
        monkeypatch,
        FakeEntryPoint("demo", "pkg_demo:Backend", loaded, DemoBackend),
    )

    backend = load_decision_backend_plugin(
        "demo",
        config={"selected": "b"},
    )
    result = choose_sync(backend, _request())

    assert result.selections[0].option_id == "b"
    assert loaded == ["demo"]


def test_load_factory_plugin(monkeypatch) -> None:
    loaded: list[str] = []

    def factory(*, selected: str):
        return DemoBackend(selected=selected)

    _install(
        monkeypatch,
        FakeEntryPoint("demo", "pkg_demo:create_backend", loaded, factory),
    )

    backend = load_decision_backend_plugin(
        "demo",
        config={"selected": "a"},
    )

    assert choose_sync(backend, _request()).selections[0].option_id == "a"


def test_preconstructed_backend_rejects_config(monkeypatch) -> None:
    loaded: list[str] = []
    _install(
        monkeypatch,
        FakeEntryPoint("demo", "pkg_demo:backend", loaded, DemoBackend()),
    )

    with pytest.raises(TypeError, match="does not accept configuration"):
        load_decision_backend_plugin("demo", config={"selected": "b"})


def test_invalid_plugin_result_fails_closed(monkeypatch) -> None:
    loaded: list[str] = []
    _install(
        monkeypatch,
        FakeEntryPoint("demo", "pkg_demo:not_backend", loaded, object()),
    )

    with pytest.raises(TypeError, match="callable decide"):
        load_decision_backend_plugin("demo")


def test_unknown_plugin_fails_before_import(monkeypatch) -> None:
    loaded: list[str] = []
    _install(
        monkeypatch,
        FakeEntryPoint("demo", "pkg_demo:Backend", loaded, DemoBackend),
    )

    with pytest.raises(KeyError, match="unknown decision backend plugin"):
        load_decision_backend_plugin("missing")

    assert loaded == []


def test_duplicate_plugin_names_fail_before_import(monkeypatch) -> None:
    loaded: list[str] = []
    _install(
        monkeypatch,
        FakeEntryPoint("demo", "pkg_a:Backend", loaded, DemoBackend),
        FakeEntryPoint("demo", "pkg_b:Backend", loaded, DemoBackend),
    )

    with pytest.raises(RuntimeError, match="ambiguous decision backend plugin"):
        load_decision_backend_plugin("demo")

    assert loaded == []


def test_plugin_output_remains_locally_bounded(monkeypatch) -> None:
    loaded: list[str] = []
    _install(
        monkeypatch,
        FakeEntryPoint(
            "demo",
            "pkg_demo:Backend",
            loaded,
            lambda: DemoBackend(selected="unregistered"),
        ),
    )

    backend = load_decision_backend_plugin("demo")
    with pytest.raises(Exception, match="unknown option"):
        choose_sync(backend, _request())

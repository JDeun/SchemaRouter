"""Concurrency-integrity contracts for issue #514."""
from __future__ import annotations

import pytest

from schemarouter import (
    BindingDriftError,
    EndpointSpec,
    InMemoryRegistry,
    RegistrationError,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.executor import RegistryExecutor
from schemarouter.registry import replace_if_current


def _tool(*, description: str, path: str = "/run") -> ToolSpec:
    return ToolSpec(
        name="demo",
        description=description,
        endpoints=[
            EndpointSpec(
                name="run",
                method="GET",
                path=path,
                read_only=True,
            )
        ],
    )


def test_bind_refuses_an_invoker_built_for_an_older_contract() -> None:
    registry = InMemoryRegistry()
    original = _tool(description="original")
    registry.register(original)
    expected = registry.get("demo").fingerprint

    registry.register(
        _tool(description="newer", path="/newer"),
        replace=True,
    )
    executor = RegistryExecutor(registry)

    with pytest.raises(BindingDriftError, match="registry contract changed"):
        executor.bind(
            "demo",
            lambda endpoint, arguments: {"ok": True},
            expected_fingerprint=expected,
        )

    assert "demo" not in executor.bound_keys()


def test_bind_pins_the_exact_expected_fingerprint() -> None:
    registry = InMemoryRegistry()
    tool = _tool(description="original")
    registry.register(tool)
    expected = registry.get("demo").fingerprint
    executor = RegistryExecutor(registry)

    executor.bind(
        "demo",
        lambda endpoint, arguments: {"ok": True},
        expected_fingerprint=expected,
    )

    assert executor.is_binding_ready_for_contract("demo", expected)


def test_atomic_operations_fail_closed_for_a_legacy_registry() -> None:
    class LegacyRegistry:
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

    registry = LegacyRegistry()
    original = _tool(description="original")
    registry.register(original)

    with pytest.raises(RegistrationError, match="atomic replace-if-fingerprint"):
        replace_if_current(
            registry,
            _tool(description="amended"),
            expected_fingerprint=original.fingerprint,
            expected_version=registry.version,
        )

    assert registry.get("demo").description == "original"


def test_amendment_cannot_overwrite_a_writer_that_lands_after_validation() -> None:
    class RacingRegistry(InMemoryRegistry):
        raced = False

        def replace_if_fingerprint(
            self,
            tool: ToolSpec,
            *,
            expected_fingerprint: str,
            expected_version: int,
        ) -> str:
            if not self.raced:
                self.raced = True
                current = self.get(tool.key)
                interloper = current.model_copy(deep=True)
                interloper.metadata["writer"] = "concurrent"
                assert interloper.fingerprint == current.fingerprint
                self.register(interloper, replace=True)
            return super().replace_if_fingerprint(
                tool,
                expected_fingerprint=expected_fingerprint,
                expected_version=expected_version,
            )

    registry = RacingRegistry()
    router = SchemaRouter(registry=registry)
    original = _tool(description="original")
    router.add_tool(original)
    amended_endpoint = original.endpoints[0].model_copy(
        update={"description": "trusted annotation"}
    )
    amended = original.model_copy(update={"endpoints": [amended_endpoint]})

    with pytest.raises(RegistrationError, match="registry changed concurrently"):
        router.amend_capability("demo", amended)

    assert registry.get("demo").metadata["writer"] == "concurrent"

def test_add_bound_tool_rolls_back_new_registration_when_bind_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter()
    tool = _tool(description="new")

    def fail_bind(*args, **kwargs) -> None:
        raise RuntimeError("injected bind failure")

    monkeypatch.setattr(router.executor, "bind", fail_bind)

    with pytest.raises(RuntimeError, match="injected bind failure"):
        router.add_bound_tool(
            tool,
            lambda endpoint, arguments: {"ok": True},
        )

    assert "demo" not in router.registry.keys()
    assert "demo" not in router.executor.bound_keys()


def test_add_bound_tool_failed_replacement_restores_contract_and_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter()
    original = _tool(description="original")
    original_invoker = lambda endpoint, arguments: {"version": "original"}
    router.add_bound_tool(original, original_invoker)
    original_fingerprint = router.registry.get("demo").fingerprint

    replacement = _tool(description="replacement", path="/replacement")

    def fail_bind(*args, **kwargs) -> None:
        raise RuntimeError("injected replacement bind failure")

    monkeypatch.setattr(router.executor, "bind", fail_bind)

    with pytest.raises(RuntimeError, match="injected replacement bind failure"):
        router.add_bound_tool(
            replacement,
            lambda endpoint, arguments: {"version": "replacement"},
            replace=True,
        )

    restored = router.registry.get("demo")
    assert restored.fingerprint == original_fingerprint
    assert restored.description == "original"
    assert router.executor.is_binding_ready_for_contract(
        "demo",
        original_fingerprint,
    )
    assert (
        router.executor._bound_invoker_for_contract(
            "demo",
            original_fingerprint,
        )
        is original_invoker
    )


def test_bound_publication_does_not_rollback_across_concurrent_writer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter()
    original = _tool(description="original")
    router.add_bound_tool(
        original,
        lambda endpoint, arguments: {"version": "original"},
    )
    replacement = _tool(description="replacement", path="/replacement")
    concurrent = ToolSpec(
        name="other",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    )

    def race_then_fail(*args, **kwargs) -> None:
        router.registry.register(concurrent)
        raise RuntimeError("injected bind failure after concurrent write")

    monkeypatch.setattr(router.executor, "bind", race_then_fail)

    with pytest.raises(
        BindingDriftError,
        match="rollback could not be completed without overwriting concurrent state",
    ):
        router.add_bound_tool(
            replacement,
            lambda endpoint, arguments: {"version": "replacement"},
            replace=True,
        )

    assert router.registry.get("other").fingerprint == concurrent.fingerprint
    assert router.registry.get("demo").fingerprint == replacement.fingerprint
    assert not router.executor.is_binding_ready_for_contract(
        "demo",
        replacement.fingerprint,
    )


from __future__ import annotations

from types import SimpleNamespace

import pytest

from schemarouter import (
    ProviderAccessMethod,
    ProviderProfile,
    ProviderProfileRegistry,
    SchemaRouter,
)


def test_materials_project_profile_resolves_provider_first() -> None:
    router = SchemaRouter()

    resolution = router.resolve_provider("mp")
    assert resolution.provider_id == "materials-project"
    by_id = {method.method_id: method for method in resolution.methods}

    assert by_id["optimade"].status == "available"
    assert by_id["optimade"].url == "https://optimade.materialsproject.org"
    assert by_id["openapi"].credential_names == ("X-API-KEY",)
    assert by_id["python-sdk"].status in {
        "dependency_missing",
        "manual_binding_required",
    }


@pytest.mark.asyncio
async def test_add_provider_registers_usable_methods_and_reports_skips(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter()
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_add_url(url: str, **kwargs: object) -> SimpleNamespace:
        calls.append((url, kwargs))
        return SimpleNamespace(key="materials-project-optimade")

    monkeypatch.setattr(router, "add_url", fake_add_url)

    result = await router.add_provider("materials-project")
    by_id = {method.method_id: method for method in result.methods}

    assert result.registered_tool_keys == ("materials-project-optimade",)
    assert by_id["optimade"].status == "registered"
    assert by_id["openapi"].status == "auth_required"
    assert by_id["python-sdk"].status in {
        "dependency_missing",
        "manual_binding_required",
    }

    assert calls == [
        (
            "https://optimade.materialsproject.org",
            {
                "kind": "optimade",
                "provider": "materials-project",
                "access_mode": "optimade",
                "trusted_headers": None,
                "replace": False,
                "timeout": 20.0,
            },
        )
    ]


@pytest.mark.asyncio
async def test_add_provider_never_echoes_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter()
    seen_headers: dict[str, str] = {}

    async def fake_add_url(url: str, **kwargs: object) -> SimpleNamespace:
        del url
        raw = kwargs["trusted_headers"]
        assert isinstance(raw, dict)
        seen_headers.update(raw)
        return SimpleNamespace(key="materials-project-openapi")

    monkeypatch.setattr(router, "add_url", fake_add_url)

    result = await router.add_provider(
        "materials-project",
        methods={"openapi"},
        trusted_headers_by_method={
            "openapi": {"X-API-KEY": "test-secret-that-must-not-leak"}
        },
    )

    assert seen_headers["X-API-KEY"] == "test-secret-that-must-not-leak"
    assert result.registered_tool_keys == ("materials-project-openapi",)
    assert "test-secret-that-must-not-leak" not in result.model_dump_json()


def test_provider_registry_rejects_alias_collision() -> None:
    registry = ProviderProfileRegistry()
    registry.register(
        ProviderProfile(
            provider_id="alpha",
            display_name="Alpha",
            aliases=("shared",),
            methods=(
                ProviderAccessMethod(
                    method_id="api",
                    kind="openapi",
                    access_mode="openapi",
                    url="https://example.test/openapi.json",
                ),
            ),
        )
    )

    with pytest.raises(ValueError, match="aliases collide"):
        registry.register(
            ProviderProfile(
                provider_id="beta",
                display_name="Beta",
                aliases=("shared",),
            )
        )


def test_provider_resolution_rejects_unknown_method() -> None:
    router = SchemaRouter()

    with pytest.raises(KeyError, match="unknown access method"):
        router.resolve_provider("materials-project", methods={"not-a-method"})

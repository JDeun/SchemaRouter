from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

import schemarouter.provider_profiles as provider_profiles
from schemarouter import (
    PlanRequest,
    ProviderAccessMethod,
    ProviderProfile,
    ProviderProfileRegistry,
    SchemaRouter,
)


def test_builtin_profiles_resolve_provider_first() -> None:
    router = SchemaRouter()

    materials = router.resolve_provider("mp")
    assert materials.provider_id == "materials-project"
    material_methods = {method.method_id: method for method in materials.methods}
    assert material_methods["optimade"].status == "available"
    assert material_methods["optimade"].url == "https://optimade.materialsproject.org/v1"
    assert material_methods["openapi"].credential_names == ("X-API-KEY",)
    assert material_methods["python-sdk"].status in {
        "dependency_missing",
        "manual_binding_required",
    }

    crossref = router.resolve_provider("crossref")
    assert crossref.provider_id == "crossref"
    assert [(method.method_id, method.status) for method in crossref.methods] == [
        ("rest", "available")
    ]

    tavily = router.resolve_provider("tavily", methods={"rest"})
    assert tavily.provider_id == "tavily"
    assert tavily.methods[0].status == "available"
    assert tavily.methods[0].credential_names == ("Authorization",)

    protocol_profiles = {
        "apis-guru": ("openapi", "openapi", "https://api.apis.guru/v2/openapi.yaml"),
        "rick-and-morty-api": (
            "graphql",
            "graphql",
            "https://rickandmortyapi.com/graphql",
        ),
        "odata-v4-reference": (
            "odata",
            "odata",
            "https://services.odata.org/V4/OData/OData.svc/",
        ),
    }
    for provider_id, expected in protocol_profiles.items():
        resolved = router.resolve_provider(provider_id)
        assert resolved.provider_id == provider_id
        assert len(resolved.methods) == 1
        method = resolved.methods[0]
        assert (method.method_id, method.kind, method.url) == expected
        assert method.status == "available"


@pytest.mark.asyncio
async def test_add_materials_project_registers_usable_methods_and_reports_skips(
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
            "https://optimade.materialsproject.org/v1",
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
@pytest.mark.parametrize(
    ("kind", "provider_id"),
    [
        ("openapi", "example-openapi"),
        ("optimade", "example-optimade"),
        ("graphql", "example-graphql"),
        ("odata", "example-odata"),
        ("openrpc", "example-openrpc"),
        ("mcp", "example-mcp"),
    ],
)
async def test_provider_first_forwards_every_url_adapter_kind(
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
    provider_id: str,
) -> None:
    router = SchemaRouter()
    source = f"https://example.test/{kind}"
    router.register_provider_profile(
        ProviderProfile(
            provider_id=provider_id,
            display_name=provider_id,
            methods=(
                ProviderAccessMethod(
                    method_id=kind,
                    kind=kind,
                    access_mode=kind,
                    url=source,
                ),
            ),
        )
    )
    calls: list[tuple[str, dict[str, object]]] = []

    async def fake_add_url(url: str, **kwargs: object) -> SimpleNamespace:
        calls.append((url, kwargs))
        return SimpleNamespace(key=f"{provider_id}-{kind}")

    monkeypatch.setattr(router, "add_url", fake_add_url)

    result = await router.add_provider(provider_id)

    assert result.registered_tool_keys == (f"{provider_id}-{kind}",)
    assert result.methods[0].status == "registered"
    assert calls == [
        (
            source,
            {
                "kind": kind,
                "provider": provider_id,
                "access_mode": kind,
                "trusted_headers": None,
                "replace": False,
                "timeout": 20.0,
            },
        )
    ]


@pytest.mark.asyncio
async def test_provider_registration_never_echoes_credentials(
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


@pytest.mark.asyncio
async def test_crossref_provider_first_registration_and_execution() -> None:
    seen_urls: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "status": "ok",
                "message": {
                    "items": [
                        {
                            "DOI": "10.1234/example",
                            "title": ["Example work"],
                        }
                    ]
                },
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        registration = await router.add_provider("crossref")

        assert registration.provider_id == "crossref"
        assert len(registration.registered_tool_keys) == 1
        assert registration.methods[0].status == "registered"

        key = registration.registered_tool_keys[0]
        plan = router.plan_executable(
            PlanRequest(
                query="search Crossref works metadata",
                preferred_tools=[key],
                arguments={"query": "SchemaRouter", "rows": 1},
            )
        )
        assert plan.executable
        assert plan.calls[0].endpoint == "search_works"
        results = await router.execute(plan)

    assert results[0].data["message"]["items"][0]["DOI"] == "10.1234/example"
    assert "query=SchemaRouter" in seen_urls[0]
    assert "rows=1" in seen_urls[0]


@pytest.mark.asyncio
async def test_tavily_provider_reports_auth_then_executes_with_trusted_header() -> None:
    router = SchemaRouter()
    missing = await router.add_provider("tavily", methods={"rest"})
    assert missing.registered_tool_keys == ()
    assert missing.methods[0].status == "auth_required"
    assert "Authorization" in missing.methods[0].detail

    seen_headers: list[dict[str, str]] = []
    seen_bodies: list[dict[str, object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_headers.append(dict(request.headers))
        seen_bodies.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "SchemaRouter",
                        "url": "https://example.test",
                        "content": "Typed capability routing",
                    }
                ],
                "response_time": "0.1",
            },
            request=request,
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(http_client=client)
        registration = await router.add_provider(
            "tavily",
            methods={"rest"},
            trusted_headers_by_method={
                "rest": {"Authorization": "Bearer test-token"}
            },
        )
        assert len(registration.registered_tool_keys) == 1
        assert registration.methods[0].status == "registered"

        key = registration.registered_tool_keys[0]
        plan = router.plan_executable(
            PlanRequest(
                query="search Tavily web",
                preferred_tools=[key],
                arguments={
                    "query": "SchemaRouter",
                    "max_results": 1,
                    "search_depth": "basic",
                },
            )
        )
        assert plan.executable
        assert plan.calls[0].endpoint == "search"
        results = await router.execute(plan)

    assert results[0].data["results"][0]["title"] == "SchemaRouter"
    assert seen_headers[0]["authorization"] == "Bearer test-token"
    assert seen_bodies == [
        {
            "query": "SchemaRouter",
            "max_results": 1,
            "search_depth": "basic",
        }
    ]


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


class _FakeProviderEntryPoint:
    def __init__(self, name: str, loaded: list[str]) -> None:
        self.name = name
        self.value = f"package_{name}:profiles"
        self.dist = SimpleNamespace(
            metadata={"Name": f"dist-{name}"},
            version="1.0",
        )
        self._loaded = loaded

    def load(self) -> object:
        self._loaded.append(self.name)
        return ProviderProfile(
            provider_id=f"plugin-{self.name}",
            display_name=f"Plugin {self.name}",
        )


class _FakeProviderEntryPoints(tuple[object, ...]):
    def select(self, *, group: str) -> tuple[object, ...]:
        if group == provider_profiles.PROVIDER_PROFILE_ENTRY_POINT_GROUP:
            return tuple(self)
        return ()


def test_provider_plugin_discovery_does_not_import_code(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded: list[str] = []
    entries = _FakeProviderEntryPoints(
        [_FakeProviderEntryPoint("demo", loaded)]
    )
    monkeypatch.setattr(provider_profiles.metadata, "entry_points", lambda: entries)

    found = provider_profiles.discover_provider_profile_plugins()

    assert [item.name for item in found] == ["demo"]
    assert found[0].distribution == "dist-demo"
    assert loaded == []


def test_provider_plugin_loading_requires_explicit_allowlist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded: list[str] = []
    entries = _FakeProviderEntryPoints(
        [_FakeProviderEntryPoint("demo", loaded)]
    )
    monkeypatch.setattr(provider_profiles.metadata, "entry_points", lambda: entries)
    router = SchemaRouter()

    with pytest.raises(ValueError, match="non-empty explicit allowlist"):
        router.load_provider_profile_plugins(allowlist=[])

    assert loaded == []

    assert router.load_provider_profile_plugins(allowlist={"demo"}) == (
        "plugin-demo",
    )
    assert router.resolve_provider("plugin-demo").provider_id == "plugin-demo"
    assert loaded == ["demo"]

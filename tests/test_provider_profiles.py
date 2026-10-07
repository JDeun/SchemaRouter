from __future__ import annotations

import json
from types import SimpleNamespace

import httpx
import pytest

import schemarouter.provider_profiles as provider_profiles
from schemarouter import (
    EndpointSpec,
    FieldSpec,
    PlanRequest,
    ProviderAccessMethod,
    ProviderDiscoveryCandidate,
    ProviderProfile,
    ProviderProfileRegistry,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.errors import RegistrationError


def test_unknown_provider_discovery_is_non_authoritative_and_ambiguous() -> None:
    router = SchemaRouter()

    proposal = router.discover_provider("google")

    assert proposal.status == "ambiguous"
    assert [candidate.candidate_id for candidate in proposal.candidates] == [
        "google-drive",
        "google-calendar",
        "google-maps",
        "google-gemini",
        "google-bigquery",
    ]
    assert all(not candidate.registrable for candidate in proposal.candidates)
    assert "google" not in router.provider_profile_registry.provider_ids()


def test_external_provider_discovery_requires_digest_approval() -> None:
    router = SchemaRouter()
    profile = ProviderProfile(
        provider_id="internal-catalog-service",
        display_name="Internal Catalog Service",
        profile_source="host:catalog",
        methods=(
            ProviderAccessMethod(
                method_id="openapi",
                kind="openapi",
                access_mode="openapi",
                url="https://catalog.example.test/openapi.json",
            ),
        ),
    )

    def backend(query: str) -> tuple[ProviderDiscoveryCandidate, ...]:
        assert query == "catalog"
        return (
            ProviderDiscoveryCandidate(
                candidate_id=profile.provider_id,
                display_name=profile.display_name,
                source="host:catalog",
                reason="trusted enterprise service catalog match",
                profile=profile,
            ),
        )

    proposal = router.discover_provider("catalog", backend=backend)
    assert proposal.status == "resolved"
    candidate = proposal.candidates[0]
    assert candidate.registrable is True
    digest = candidate.approval_digest
    assert digest is not None

    with pytest.raises(ValueError, match="changed before approval"):
        router.approve_provider_candidate(
            candidate,
            expected_digest="0" * 64,
        )

    registered = router.approve_provider_candidate(
        candidate,
        expected_digest=digest,
    )
    assert registered == "internal-catalog-service"
    assert router.resolve_provider("internal-catalog-service").provider_id == registered


def test_unknown_provider_discovery_without_backend_stays_unknown() -> None:
    router = SchemaRouter()
    proposal = router.discover_provider("provider-that-does-not-exist")

    assert proposal.status == "unknown"
    assert proposal.candidates == ()

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
    assert result.status == "partial"
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
        assert registration.status == "complete"
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
    assert missing.status == "failed"
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


class _StaticProviderEntryPoint:
    def __init__(self, name: str, loaded: list[str], value: object) -> None:
        self.name = name
        self.value = f"package_{name}:profiles"
        self.dist = SimpleNamespace(
            metadata={"Name": f"dist-{name}"},
            version="1.0",
        )
        self._loaded = loaded
        self._value = value

    def load(self) -> object:
        self._loaded.append(self.name)
        if isinstance(self._value, BaseException):
            raise self._value
        return self._value


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


def test_provider_plugin_batch_is_atomic_when_later_plugin_load_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded: list[str] = []
    registry = ProviderProfileRegistry()
    baseline = ProviderProfile(
        provider_id="baseline",
        display_name="Baseline",
        aliases=("baseline-alias",),
    )
    registry.register(baseline)
    before = registry.profiles()

    entries = _FakeProviderEntryPoints(
        [
            _StaticProviderEntryPoint(
                "alpha",
                loaded,
                ProviderProfile(
                    provider_id="plugin-alpha",
                    display_name="Plugin Alpha",
                ),
            ),
            _StaticProviderEntryPoint(
                "beta",
                loaded,
                RuntimeError("plugin import failed"),
            ),
        ]
    )
    monkeypatch.setattr(provider_profiles.metadata, "entry_points", lambda: entries)

    with pytest.raises(RuntimeError, match="plugin import failed"):
        provider_profiles.load_provider_profile_plugins(
            registry,
            allowlist={"alpha", "beta"},
        )

    assert loaded == ["alpha", "beta"]
    assert registry.profiles() == before
    assert registry.provider_ids() == ("baseline",)


def test_provider_plugin_batch_is_atomic_when_second_profile_is_invalid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded: list[str] = []
    registry = ProviderProfileRegistry()
    entries = _FakeProviderEntryPoints(
        [
            _StaticProviderEntryPoint(
                "batch",
                loaded,
                (
                    ProviderProfile(
                        provider_id="first",
                        display_name="First",
                        aliases=("shared",),
                    ),
                    ProviderProfile(
                        provider_id="second",
                        display_name="Second",
                        aliases=("shared",),
                    ),
                ),
            )
        ]
    )
    monkeypatch.setattr(provider_profiles.metadata, "entry_points", lambda: entries)

    with pytest.raises(ValueError, match="aliases collide"):
        provider_profiles.load_provider_profile_plugins(
            registry,
            allowlist={"batch"},
        )

    assert loaded == ["batch"]
    assert registry.provider_ids() == ()


def test_provider_plugin_batch_rejects_cross_plugin_alias_collision_atomically(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded: list[str] = []
    registry = ProviderProfileRegistry()
    entries = _FakeProviderEntryPoints(
        [
            _StaticProviderEntryPoint(
                "alpha",
                loaded,
                ProviderProfile(
                    provider_id="plugin-alpha",
                    display_name="Plugin Alpha",
                    aliases=("shared",),
                ),
            ),
            _StaticProviderEntryPoint(
                "beta",
                loaded,
                ProviderProfile(
                    provider_id="plugin-beta",
                    display_name="Plugin Beta",
                    aliases=("shared",),
                ),
            ),
        ]
    )
    monkeypatch.setattr(provider_profiles.metadata, "entry_points", lambda: entries)

    with pytest.raises(ValueError, match="aliases collide"):
        provider_profiles.load_provider_profile_plugins(
            registry,
            allowlist={"alpha", "beta"},
        )

    assert loaded == ["alpha", "beta"]
    assert registry.provider_ids() == ()


def test_provider_plugin_replace_batch_rolls_back_on_late_collision(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded: list[str] = []
    registry = ProviderProfileRegistry()
    registry.register(
        ProviderProfile(
            provider_id="alpha",
            display_name="Original Alpha",
            aliases=("old-alpha",),
        )
    )
    registry.register(
        ProviderProfile(
            provider_id="owner",
            display_name="Alias Owner",
            aliases=("shared",),
        )
    )
    before = registry.profiles()

    entries = _FakeProviderEntryPoints(
        [
            _StaticProviderEntryPoint(
                "alpha-replacement",
                loaded,
                ProviderProfile(
                    provider_id="alpha",
                    display_name="Replacement Alpha",
                    aliases=("new-alpha",),
                ),
            ),
            _StaticProviderEntryPoint(
                "beta",
                loaded,
                ProviderProfile(
                    provider_id="beta",
                    display_name="Beta",
                    aliases=("shared",),
                ),
            ),
        ]
    )
    monkeypatch.setattr(provider_profiles.metadata, "entry_points", lambda: entries)

    with pytest.raises(ValueError, match="aliases collide"):
        provider_profiles.load_provider_profile_plugins(
            registry,
            allowlist={"alpha-replacement", "beta"},
            replace=True,
        )

    assert loaded == ["alpha-replacement", "beta"]
    assert registry.profiles() == before
    assert registry.get("old-alpha").display_name == "Original Alpha"
    with pytest.raises(KeyError, match="unknown provider profile"):
        registry.get("new-alpha")



def _atomic_provider_profile() -> ProviderProfile:
    return ProviderProfile(
        provider_id="atomic-example",
        display_name="Atomic Example",
        methods=(
            ProviderAccessMethod(
                method_id="alpha",
                kind="openapi",
                access_mode="alpha",
                url="https://example.test/alpha.json",
            ),
            ProviderAccessMethod(
                method_id="beta",
                kind="openapi",
                access_mode="beta",
                url="https://example.test/beta.json",
            ),
        ),
    )


def _atomic_tool(name: str, version: str) -> ToolSpec:
    return ToolSpec(
        name=name,
        description=f"{name}-{version}",
        endpoints=(
            EndpointSpec(
                name="read",
                output_fields=(FieldSpec(name="value"),),
                read_only=True,
            ),
        ),
    )


def _atomic_invoker(label: str):
    async def invoke(endpoint: str, arguments: dict[str, object]) -> dict[str, object]:
        del endpoint, arguments
        return {"value": label}

    return invoke


@pytest.mark.asyncio
async def test_provider_require_all_publishes_prepared_methods_as_one_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter()
    router.register_provider_profile(_atomic_provider_profile())

    async def fake_inspect(url: str, **kwargs: object) -> SimpleNamespace:
        del kwargs
        method = "alpha" if "alpha" in url else "beta"
        return SimpleNamespace(
            tool=_atomic_tool(f"atomic-{method}", "new"),
            invoker=_atomic_invoker(method),
        )

    monkeypatch.setattr(router.loader, "inspect", fake_inspect)
    result = await router.add_provider("atomic-example", require_all=True)

    assert result.status == "complete"
    assert result.registered_tool_keys == ("atomic-alpha", "atomic-beta")
    assert [method.status for method in result.methods] == [
        "registered",
        "registered",
    ]
    assert set(router.registry.keys()) == {"atomic-alpha", "atomic-beta"}


@pytest.mark.asyncio
@pytest.mark.parametrize("failing_method", ["alpha", "beta"])
async def test_provider_require_all_preparation_failure_leaves_no_partial_topology(
    monkeypatch: pytest.MonkeyPatch,
    failing_method: str,
) -> None:
    router = SchemaRouter()
    router.register_provider_profile(_atomic_provider_profile())

    async def fake_inspect(url: str, **kwargs: object) -> SimpleNamespace:
        del kwargs
        method = "alpha" if "alpha" in url else "beta"
        if method == failing_method:
            raise RuntimeError("synthetic preparation failure")
        return SimpleNamespace(
            tool=_atomic_tool(f"atomic-{method}", "new"),
            invoker=_atomic_invoker(method),
        )

    monkeypatch.setattr(router.loader, "inspect", fake_inspect)
    result = await router.add_provider("atomic-example", require_all=True)

    assert result.status == "failed"
    assert result.registered_tool_keys == ()
    by_id = {method.method_id: method for method in result.methods}
    assert by_id[failing_method].status == "unavailable"
    other = "beta" if failing_method == "alpha" else "alpha"
    assert by_id[other].status == "aborted"
    assert router.registry.keys() == ()



@pytest.mark.asyncio
async def test_provider_require_all_binding_failure_restores_replace_topology(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter()
    router.register_provider_profile(_atomic_provider_profile())

    old_alpha = _atomic_tool("atomic-alpha", "old")
    old_beta = _atomic_tool("atomic-beta", "old")
    old_alpha_invoker = _atomic_invoker("old-alpha")
    old_beta_invoker = _atomic_invoker("old-beta")
    router.add_bound_tool(old_alpha, old_alpha_invoker)
    router.add_bound_tool(old_beta, old_beta_invoker)

    async def fake_inspect(url: str, **kwargs: object) -> SimpleNamespace:
        del kwargs
        method = "alpha" if "alpha" in url else "beta"
        return SimpleNamespace(
            tool=_atomic_tool(f"atomic-{method}", "new"),
            invoker=_atomic_invoker(f"new-{method}"),
        )

    monkeypatch.setattr(router.loader, "inspect", fake_inspect)
    original_bind = router.executor.bind

    def fail_second_binding(tool_key: str, invoker, **kwargs: object) -> int:
        if tool_key == "atomic-beta":
            raise RuntimeError("synthetic binding failure")
        return original_bind(tool_key, invoker, **kwargs)

    monkeypatch.setattr(router.executor, "bind", fail_second_binding)

    with pytest.raises(RuntimeError, match="synthetic binding failure"):
        await router.add_provider(
            "atomic-example",
            require_all=True,
            replace=True,
        )

    restored_alpha = router.registry.get("atomic-alpha")
    restored_beta = router.registry.get("atomic-beta")
    assert restored_alpha.fingerprint == old_alpha.fingerprint
    assert restored_beta.fingerprint == old_beta.fingerprint
    assert (
        router.executor._bound_invoker_for_contract(
            "atomic-alpha",
            old_alpha.fingerprint,
        )
        is old_alpha_invoker
    )
    assert (
        router.executor._bound_invoker_for_contract(
            "atomic-beta",
            old_beta.fingerprint,
        )
        is old_beta_invoker
    )


@pytest.mark.asyncio
async def test_provider_require_all_rejects_concurrent_registry_mutation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    router = SchemaRouter()
    router.register_provider_profile(_atomic_provider_profile())
    calls = 0

    async def fake_inspect(url: str, **kwargs: object) -> SimpleNamespace:
        nonlocal calls
        del kwargs
        calls += 1
        method = "alpha" if "alpha" in url else "beta"
        if calls == 1:
            router.add_tool(_atomic_tool("concurrent-tool", "external"))
        return SimpleNamespace(
            tool=_atomic_tool(f"atomic-{method}", "new"),
            invoker=_atomic_invoker(method),
        )

    monkeypatch.setattr(router.loader, "inspect", fake_inspect)

    with pytest.raises(RegistrationError, match="changed concurrently"):
        await router.add_provider("atomic-example", require_all=True)

    assert router.registry.keys() == ("concurrent-tool",)
    assert "atomic-alpha" not in router.registry.keys()
    assert "atomic-beta" not in router.registry.keys()


@pytest.mark.asyncio
async def test_provider_require_all_rejects_non_boolean_mode() -> None:
    router = SchemaRouter()
    with pytest.raises(TypeError, match="require_all"):
        await router.add_provider("crossref", require_all=1)  # type: ignore[arg-type]

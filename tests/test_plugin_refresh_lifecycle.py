from __future__ import annotations

from typing import Any

import httpx
import pytest

from schemarouter import (
    AdapterLoadResult,
    AdapterRegistry,
    DiscoveryProfile,
    EndpointSpec,
    ParameterSpec,
    RefreshProfile,
    SchemaRouter,
    SchemaSourceError,
    ToolSpec,
)
from schemarouter._url_safety import safe_provenance_url


class RefreshableFixtureAdapter:
    kind = "fixture_refresh"
    priority = 50
    discovery = DiscoveryProfile(
        activity="passive",
        http_methods=("GET",),
    )
    refresh = RefreshProfile(
        mode="url",
        source_key="source_url",
        source_location="metadata",
    )

    async def load(self, context) -> AdapterLoadResult | None:
        client = context.http_client
        owns_client = client is None
        client = client or httpx.AsyncClient(timeout=context.timeout)
        try:
            response = await client.get(context.url)
            response.raise_for_status()
            document = response.json()
        finally:
            if owns_client:
                await client.aclose()

        if not isinstance(document, dict) or document.get("kind") != "fixture":
            return None

        parameters = []
        if bool(document.get("required_query")):
            parameters.append(
                ParameterSpec(
                    name="q",
                    location="query",
                    required=True,
                    json_schema={"type": "string"},
                )
            )

        tool = ToolSpec(
            name=context.name or "fixture",
            namespace=context.namespace,
            provider=context.provider,
            access_mode=context.access_mode or self.kind,
            source_type=self.kind,
            remote=True,
            execution_metadata={"adapter": self.kind},
            metadata={
                "adapter": self.kind,
                "source_url": safe_provenance_url(context.url),
            },
            endpoints=[
                EndpointSpec(
                    name="read",
                    description=str(document.get("description") or ""),
                    parameters=parameters,
                    read_only=True,
                    output_schema={
                        "type": "object",
                        "properties": {"ok": {"type": "boolean"}},
                    },
                )
            ],
        )
        return AdapterLoadResult(tool=tool)


class NonRefreshableFixtureAdapter:
    kind = "fixture_static"
    priority = 40
    discovery = DiscoveryProfile(
        activity="passive",
        http_methods=("GET",),
    )
    refresh = RefreshProfile()

    async def load(self, context) -> AdapterLoadResult | None:
        del context
        return AdapterLoadResult(
            tool=ToolSpec(
                name="static",
                remote=True,
                execution_metadata={"adapter": self.kind},
                metadata={
                    "adapter": self.kind,
                    "source_url": "https://fixture.example.test/static",
                },
                endpoints=[
                    EndpointSpec(
                        name="read",
                        read_only=True,
                        output_schema={"type": "object"},
                    )
                ],
            )
        )


class LegacyFixtureAdapter:
    kind = "fixture_legacy"
    priority = 30
    discovery = DiscoveryProfile(
        activity="passive",
        http_methods=("GET",),
    )

    async def load(self, context) -> AdapterLoadResult | None:
        del context
        return AdapterLoadResult(
            tool=ToolSpec(
                name="legacy",
                remote=True,
                execution_metadata={"adapter": self.kind},
                metadata={
                    "adapter": self.kind,
                    "source_url": "https://fixture.example.test/legacy",
                },
                endpoints=[
                    EndpointSpec(
                        name="read",
                        read_only=True,
                        output_schema={"type": "object"},
                    )
                ],
            )
        )


@pytest.mark.asyncio
async def test_plugin_refresh_and_watch_use_declared_refresh_profile() -> None:
    state: dict[str, Any] = {
        "kind": "fixture",
        "description": "v1",
        "required_query": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url == httpx.URL("https://fixture.example.test/schema")
        return httpx.Response(200, json=state, request=request)

    adapter = RefreshableFixtureAdapter()
    registry = AdapterRegistry([adapter])

    assert registry.refresh_profile(adapter.kind) == adapter.refresh
    assert registry.is_refreshable(adapter.kind) is True

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        router = SchemaRouter(
            http_client=client,
            adapter_registry=registry,
        )
        tool = await router.add_url(
            "https://fixture.example.test/schema",
            kind=adapter.kind,
            name="fixture",
        )

        state["description"] = "v2"
        refreshed = await router.arefresh_schema(tool.key)

        assert refreshed.action == "applied"
        assert refreshed.compatibility == "compatible"
        assert (
            router.registry.get(tool.key).endpoint("read").description
            == "v2"
        )

        router.register_schema_watch(
            tool.key,
            interval_seconds=60,
        )
        state["description"] = "v3"

        applied = await router.check_schema_watches_once()

        assert applied[0].status == "applied"
        assert (
            router.registry.get(tool.key).endpoint("read").description
            == "v3"
        )

        state["required_query"] = True
        pending = await router.check_schema_watches_once()

    assert pending[0].status == "pending_review"
    assert pending[0].last_compatibility == "breaking"
    assert (
        router.registry.get(tool.key).endpoint("read").parameters
        == []
    )


@pytest.mark.asyncio
async def test_plugin_without_refresh_declaration_is_blocked() -> None:
    adapter = NonRefreshableFixtureAdapter()
    registry = AdapterRegistry([adapter])
    router = SchemaRouter(adapter_registry=registry)

    tool = await router.add_url(
        "https://fixture.example.test/static",
        kind=adapter.kind,
    )

    assert registry.is_refreshable(adapter.kind) is False

    with pytest.raises(
        SchemaSourceError,
        match="does not have a refreshable",
    ):
        await router.arefresh_schema(tool.key)

    with pytest.raises(
        SchemaSourceError,
        match="does not have a refreshable",
    ):
        router.register_schema_watch(tool.key)


@pytest.mark.asyncio
async def test_legacy_plugin_without_refresh_profile_remains_ingestible_only() -> None:
    adapter = LegacyFixtureAdapter()
    registry = AdapterRegistry([adapter])
    router = SchemaRouter(adapter_registry=registry)

    tool = await router.add_url(
        "https://fixture.example.test/legacy",
        kind=adapter.kind,
    )

    assert tool.key == "legacy"
    assert registry.refresh_profile(adapter.kind) == RefreshProfile()
    assert registry.is_refreshable(adapter.kind) is False

    with pytest.raises(SchemaSourceError):
        await router.arefresh_schema(tool.key)


def test_refresh_profile_rejects_credential_identity_keys() -> None:
    with pytest.raises(ValueError, match="credential-bearing"):
        RefreshProfile(
            mode="url",
            source_key="source_url",
            identity_metadata_keys=("authorization_token",),
        )


def test_http_validators_require_url_refresh() -> None:
    with pytest.raises(ValueError, match="HTTP validators require URL"):
        RefreshProfile(
            mode="url_or_bound_mcp",
            source_key="source_url",
            http_validators=True,
        )


def test_refresh_profile_rejects_invalid_source_location() -> None:
    with pytest.raises(ValueError, match="source_location"):
        RefreshProfile(
            mode="url",
            source_key="source_url",
            source_location="unknown",  # type: ignore[arg-type]
        )


def test_plugin_identity_qualifier_values_are_hashed() -> None:
    from schemarouter.source_identity import structured_source_identity

    profile = RefreshProfile(
        mode="url",
        source_key="source_url",
        identity_metadata_keys=("representation",),
    )
    tool = ToolSpec(
        name="identity",
        execution_metadata={"adapter": "fixture_refresh"},
        metadata={
            "adapter": "fixture_refresh",
            "source_url": "https://fixture.example.test/schema",
            "representation": {"channel": "private-marker"},
        },
        endpoints=[
            EndpointSpec(
                name="read",
                read_only=True,
                output_schema={"type": "object"},
            )
        ],
    )

    identity = structured_source_identity(tool, profile)

    assert identity is not None
    assert identity.qualifiers
    assert "private-marker" not in repr(identity)
    assert len(identity.qualifiers[0][1]) == 64

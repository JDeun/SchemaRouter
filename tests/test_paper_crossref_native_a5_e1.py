"""Crossref's real-shape nested response wired into original A5 P2/native E1."""

from __future__ import annotations

import json
from urllib.parse import unquote

import httpx
import pytest

import schemarouter.paper_crossref_registration as crossref_registration
from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPlan,
    ExecutionPolicy,
    PrincipalContext,
    SchemaRouter,
    ToolCall,
    inspect_crossref_paper_source,
    register_reviewed_crossref_paper_source,
)
from schemarouter.errors import NonRetryableInvocationError, SchemaSourceError
from schemarouter.network_policy import NetworkPolicy
from schemarouter.provider_profiles import built_in_provider_profile_registry
from scripts.research_paper_crossref_native_e1 import (
    CROSSREF_DOI,
    probe_crossref_paper_a5,
    run_crossref_paper_a5,
)


class FakeCrossref:
    def __init__(
        self,
        *,
        response_doi: str = CROSSREF_DOI,
        publisher: object = "Nature Publishing Group",
        missing_publisher: bool = False,
        status: str = "ok",
        message_type: str | None = "work",
    ) -> None:
        self.requests: list[httpx.Request] = []
        self.response_doi = response_doi
        self.publisher = publisher
        self.missing_publisher = missing_publisher
        self.status = status
        self.message_type = message_type

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert request.method == "GET"
        assert unquote(request.url.path) == f"/v1/works/{CROSSREF_DOI}"
        assert not request.url.params
        message: dict[str, object] = {
            "DOI": self.response_doi,
            "type": "journal-article",
            "title": ["Source-owned title, not a declared selected field"],
        }
        if not self.missing_publisher:
            message["publisher"] = self.publisher
        envelope: dict[str, object] = {"status": self.status, "message": message}
        if self.message_type is not None:
            envelope["message-type"] = self.message_type
        return httpx.Response(
            200,
            json=envelope,
            headers={"content-type": "application/json"},
        )


def _router(*, http_client: httpx.AsyncClient | None = None) -> SchemaRouter:
    return SchemaRouter(
        http_client=http_client,
        network_policy=NetworkPolicy.trusted_internal(),
        policy=ExecutionPolicy(allow_unclassified_remote=True),
        authorization_policy=AuthorizationPolicy(default_effect="deny", rules=(
            AuthorizationRule(effect="allow", operation="crossref.get_work",
                              roles_any=("reader",)),
        )),
    )


def test_curated_crossref_get_work_exposes_existing_nested_scalar_paths() -> None:
    method = built_in_provider_profile_registry().get("crossref").methods[0]
    assert method.url == "https://api.crossref.org/v1"
    assert method.tool is not None
    get = method.tool.endpoint("get_work")
    fields = {f.name: f for f in get.output_fields}
    assert fields["message.DOI"].path == ["message", "DOI"]
    assert fields["message.DOI"].result_path == ["message.DOI"]
    assert fields["message.DOI"].identifier is True
    assert fields["message.DOI"].json_schema == {"type": "string"}
    assert fields["message.publisher"].path == ["message", "publisher"]
    assert fields["message.publisher"].json_schema == {"type": "string"}
    assert get.input_schema == {
        "type": "object",
        "properties": {"doi": {"type": "string"}},
        "required": ["doi"],
        "additionalProperties": False,
    }
    assert get.output_schema["properties"]["message"]["properties"]["DOI"] == {
        "type": "string",
    }


@pytest.mark.asyncio
async def test_pinned_crossref_native_registration_projects_only_typed_source_fields() -> None:
    fake = FakeCrossref()
    probe = inspect_crossref_paper_source()
    assert probe.source_fingerprint
    assert set(probe.available_fields) >= {"message.DOI", "message.publisher"}
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        router = _router(http_client=client)
        tool = register_reviewed_crossref_paper_source(
            router, expected_source_fingerprint=probe.source_fingerprint,
            expected_base_url=probe.base_url,
            license="source-license-unverified-research-only",
            reviewed_by="owner-manual-reviewed-crossref-pilot",
        )
        get = tool.endpoint("get_work")
        assert {f.semantic_id for f in get.output_fields if f.semantic_id} >= {
            "paper.doi", "paper.publisher",
        }
        result = await router.execute(ExecutionPlan(
            query="host-scoped Crossref paper",
            registry_version=router.registry.version,
            calls=[ToolCall(tool=tool.key, endpoint=get.name,
                            arguments={"doi": CROSSREF_DOI},
                            fields=["message.DOI", "message.publisher"],
                            schema_fingerprint=get.fingerprint,
                            tool_fingerprint=tool.fingerprint)],
        ), config={"principal": PrincipalContext(
            subject="crossref-a5", roles=("reader",),
        ).model_dump()})

    assert result[0].data == {
        "message.DOI": CROSSREF_DOI,
        "message.publisher": "Nature Publishing Group",
    }
    assert len(fake.requests) == 1
    assert str(fake.requests[0].url) == (
        "https://api.crossref.org/v1/works/10%2E1038%2Fnature12373"
    )


@pytest.mark.asyncio
async def test_original_a5_executes_host_doi_not_agent_forged_doi() -> None:
    fake = FakeCrossref()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        probe = await probe_crossref_paper_a5()
        assert not fake.requests  # inspection is static; no provider I/O
        result = await run_crossref_paper_a5(
            expected_source_fingerprint=probe.source_fingerprint,
            host_doi=CROSSREF_DOI, http_client=client,
            network_policy=NetworkPolicy.trusted_internal(),
        )
    assert result.doi == CROSSREF_DOI
    assert result.publisher == "Nature Publishing Group"
    assert result.route_id == "crossref.get_work"
    assert result.host_bound_tool_calls == 1
    assert result.independent_e2 is False
    assert len(fake.requests) == 1
    assert "agent-forged" not in str(fake.requests[0].url)


@pytest.mark.asyncio
async def test_stale_fingerprint_refuses_publish_without_provider_request() -> None:
    fake = FakeCrossref()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        router = _router(http_client=client)
        with pytest.raises(SchemaSourceError, match="fingerprint"):
            register_reviewed_crossref_paper_source(
                router,
                expected_source_fingerprint="0" * 64,
                expected_base_url="https://api.crossref.org/v1",
                license="source-license-unverified-research-only",
                reviewed_by="host",
            )
        assert router.registry.keys() == ()
        assert fake.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"response_doi": "10.1234/other"}, "identity"),
        ({"publisher": None}, "publisher"),
        ({"publisher": 42}, "publisher"),
        ({"missing_publisher": True}, "publisher"),
        ({"status": "error"}, "status"),
        ({"message_type": "work-list"}, "message-type"),
        ({"message_type": None}, "message-type"),
        ({"response_doi": CROSSREF_DOI + " "}, "identity"),
    ],
)
async def test_crossref_native_rejects_mismatching_identity_or_incomplete_source(
    change: dict, message: str,
) -> None:
    fake = FakeCrossref(**change)
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        with pytest.raises(NonRetryableInvocationError, match=message):
            await run_crossref_paper_a5(
                expected_source_fingerprint=(await probe_crossref_paper_a5()).source_fingerprint,
                host_doi=CROSSREF_DOI, http_client=client,
                network_policy=NetworkPolicy.trusted_internal(),
            )
    assert len(fake.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("host_doi", [
    "https://internal.invalid/secret",
    "10.١٢٣٤/forged-unicode-digits",
    "10.1234/invalid\u0080control",
])
async def test_invalid_host_doi_fails_before_any_crossref_http(host_doi: str) -> None:
    fake = FakeCrossref()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        with pytest.raises(SchemaSourceError, match="DOI"):
            await run_crossref_paper_a5(
                expected_source_fingerprint=(await probe_crossref_paper_a5()).source_fingerprint,
                host_doi=host_doi,
                http_client=client,
                network_policy=NetworkPolicy.trusted_internal(),
            )
    assert fake.requests == []


@pytest.mark.asyncio
async def test_native_rejects_unapproved_principal_without_provider_call() -> None:
    fake = FakeCrossref()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        router = _router(http_client=client)
        probe = inspect_crossref_paper_source()
        tool = register_reviewed_crossref_paper_source(
            router, expected_source_fingerprint=probe.source_fingerprint,
            expected_base_url=probe.base_url,
            license="source-license-unverified-research-only",
            reviewed_by="owner-manual-review",
        )
        get = tool.endpoint("get_work")
        from schemarouter import PolicyViolationError

        with pytest.raises(PolicyViolationError):
            await router.execute(ExecutionPlan(
                query="forbidden Crossref call",
                registry_version=router.registry.version,
                calls=[ToolCall(tool=tool.key, endpoint="get_work",
                                arguments={"doi": CROSSREF_DOI},
                                fields=["message.DOI", "message.publisher"],
                                tool_fingerprint=tool.fingerprint,
                                schema_fingerprint=get.fingerprint)],
            ), config={"principal": PrincipalContext(
                subject="no-reader", roles=("other",),
            ).model_dump()})
    assert fake.requests == []


def test_probe_is_serializable_for_keyless_two_phase_review() -> None:
    probe = inspect_crossref_paper_source()
    assert json.dumps({"fingerprint": probe.source_fingerprint})


@pytest.mark.parametrize("mutation", ["field_path", "open_input", "parameter_type"])
def test_newly_inspected_but_semantically_changed_manifest_refuses_registration(
    monkeypatch: pytest.MonkeyPatch, mutation: str,
) -> None:
    source, base_url = crossref_registration._curated_crossref_source()
    endpoint = source.endpoint("get_work")
    if mutation == "field_path":
        next(f for f in endpoint.output_fields if f.name == "message.DOI").path = [
            "message", "title",
        ]
    elif mutation == "open_input":
        endpoint.input_schema = {"type": "object"}
    else:
        endpoint.parameters[0].json_schema = {"type": "integer"}
    monkeypatch.setattr(
        crossref_registration, "_curated_crossref_source",
        lambda: (source.model_copy(deep=True), base_url),
    )
    probe = inspect_crossref_paper_source()
    router = _router()
    with pytest.raises(SchemaSourceError, match="contract"):
        register_reviewed_crossref_paper_source(
            router, expected_source_fingerprint=probe.source_fingerprint,
            expected_base_url=probe.base_url,
            license="source-license-unverified-research-only", reviewed_by="host",
        )
    assert router.registry.keys() == ()

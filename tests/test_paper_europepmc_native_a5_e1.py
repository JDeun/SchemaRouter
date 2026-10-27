"""Source-shaped Europe PMC REST DOI match through original native P2/A5."""

from __future__ import annotations

from copy import deepcopy

import httpx
import pytest

import schemarouter.paper_europepmc_registration as europepmc_registration
from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPlan,
    ExecutionPolicy,
    PrincipalContext,
    SchemaRouter,
    ToolCall,
    inspect_europepmc_paper_source,
    register_reviewed_europepmc_paper_source,
)
from schemarouter.errors import (
    NonRetryableInvocationError,
    PolicyViolationError,
    SchemaSourceError,
    SchemaValidationError,
)
from schemarouter.network_policy import NetworkPolicy
from schemarouter.paper_europepmc_registration import validate_host_europepmc_query
from schemarouter.provider_profiles import built_in_provider_profile_registry
from scripts.research_paper_europepmc_native_e1 import (
    EUROPEPMC_DOI,
    probe_europepmc_paper_a5,
    run_europepmc_paper_a5,
)


class FakeEuropePMC:
    def __init__(self) -> None:
        self.requests: list[httpx.Request] = []
        self.data: object = {
            "hitCount": 1,
            "request": {"queryString": f"DOI:{EUROPEPMC_DOI}"},
            "resultList": {"result": [{
                "id": "23903748", "source": "MED", "doi": EUROPEPMC_DOI,
                "title": "Source-only title MUST NOT leak via field projection",
            }]},
        }

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        assert request.method == "GET"
        assert request.url.path == "/europepmc/webservices/rest/search"
        assert dict(request.url.params) == {
            "query": f"DOI:{EUROPEPMC_DOI}", "format": "json", "pageSize": "1",
        }
        return httpx.Response(200, json=self.data, headers={
            "content-type": "application/json",
        })


def _router(*, client: httpx.AsyncClient | None = None, role: str = "reader") -> SchemaRouter:
    return SchemaRouter(
        http_client=client,
        network_policy=NetworkPolicy.trusted_internal(),
        policy=ExecutionPolicy(allow_unclassified_remote=True),
        authorization_policy=AuthorizationPolicy(default_effect="deny", rules=(
            AuthorizationRule(effect="allow", operation="europepmc.search_doi",
                              roles_any=(role,)),
        )),
    )


def test_curated_europepmc_declares_source_nested_array_and_required_host_inputs() -> None:
    profile = built_in_provider_profile_registry().get("europepmc")
    assert profile.methods[0].url == "https://www.ebi.ac.uk/europepmc/webservices/rest"
    assert profile.methods[0].tool is not None
    endpoint = profile.methods[0].tool.endpoint("search_doi")
    assert endpoint.method == "GET" and endpoint.path == "/search"
    assert endpoint.read_only and not endpoint.destructive
    assert {p.name: p.location for p in endpoint.parameters} == {
        "query": "query", "format": "query", "pageSize": "query",
    }
    assert endpoint.input_schema["required"] == ["query", "format", "pageSize"]
    fields = {field.name: field for field in endpoint.output_fields}
    assert fields["hitCount"].json_schema == {"type": "integer"}
    assert fields["resultList.result.*.doi"].path == [
        "resultList", "result", "*", "doi",
    ]
    assert not fields["resultList.result.*.doi"].identifier
    assert fields["resultList.result.*.id"].json_schema == {"type": "string"}


@pytest.mark.parametrize("suffix", [
    "*", "record?", "(OR)", "[1 TO 9]", 'x"OR"y', "x\\y",
])
def test_unquoted_europepmc_query_operators_rejected_before_http(suffix: str) -> None:
    with pytest.raises(SchemaSourceError, match="DOI"):
        validate_host_europepmc_query(f"DOI:10.1234/{suffix}")


@pytest.mark.asyncio
async def test_pinned_europepmc_registers_native_tool_and_projects_real_nested_fields() -> None:
    fake = FakeEuropePMC()
    probe = inspect_europepmc_paper_source()
    assert probe.base_url == "https://www.ebi.ac.uk/europepmc/webservices/rest"
    assert set(probe.available_fields) == {
        "hitCount", "resultList.result.*.doi", "resultList.result.*.id",
    }
    assert not fake.requests
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        router = _router(client=client)
        approved = register_reviewed_europepmc_paper_source(
            router, expected_source_fingerprint=probe.source_fingerprint,
            expected_base_url=probe.base_url,
            license="source-license-unverified-research-only", reviewed_by="host",
        )
        endpoint = approved.endpoint("search_doi")
        assert {f.semantic_id for f in endpoint.output_fields if f.semantic_id} == {
            "paper.search_hit_count", "paper.doi", "paper.europepmc_record_id",
        }
        results = await router.execute(ExecutionPlan(
            query="host reviewed DOI", registry_version=router.registry.version,
            calls=[ToolCall(
                tool=approved.key, endpoint="search_doi",
                arguments={"query": f"DOI:{EUROPEPMC_DOI}", "format": "json",
                           "pageSize": 1},
                fields=["hitCount", "resultList.result.*.doi",
                        "resultList.result.*.id"],
                schema_fingerprint=endpoint.fingerprint,
                tool_fingerprint=approved.fingerprint,
            )],
        ), config={"principal": PrincipalContext(
            subject="host", roles=("reader",),
        ).model_dump()})
    assert results[0].data == {
        "hitCount": 1,
        "resultList": {"result": [{"doi": EUROPEPMC_DOI, "id": "23903748"}]},
    }
    assert len(fake.requests) == 1


@pytest.mark.asyncio
async def test_original_p2_a5_requires_host_doi_and_ignores_forged_agent_arguments() -> None:
    fake = FakeEuropePMC()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        probe = await probe_europepmc_paper_a5()
        result = await run_europepmc_paper_a5(
            expected_source_fingerprint=probe.source_fingerprint,
            host_doi=EUROPEPMC_DOI, http_client=client,
            network_policy=NetworkPolicy.trusted_internal(),
        )
    assert result.doi == EUROPEPMC_DOI
    assert result.record_id == "23903748"
    assert result.hit_count == 1
    assert result.route_id == "europepmc.search_doi"
    assert result.host_bound_tool_calls == 1 and not result.independent_e2
    assert len(fake.requests) == 1
    assert "agent-forged" not in str(fake.requests[0].url)


@pytest.mark.asyncio
async def test_stale_or_changed_source_refuses_publish_with_no_network() -> None:
    fake = FakeEuropePMC()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        router = _router(client=client)
        probe = inspect_europepmc_paper_source()
        for kwargs in (
            {"expected_source_fingerprint": "0" * 64, "expected_base_url": probe.base_url},
            {"expected_source_fingerprint": probe.source_fingerprint,
             "expected_base_url": "https://attacker.invalid"},
        ):
            with pytest.raises(SchemaSourceError):
                register_reviewed_europepmc_paper_source(
                    router, **kwargs,
                    license="source-license-unverified-research-only",
                    reviewed_by="host",
                )
        assert router.registry.keys() == ()
        assert not fake.requests


@pytest.mark.asyncio
@pytest.mark.parametrize("data", [
    None,
    {"hitCount": 0, "resultList": {"result": []}},
    {"hitCount": 1, "resultList": {"result": []}},
    {"hitCount": 1, "resultList": {"result": [{"id": "x", "doi": "10.1234/other"}]}},
    {"hitCount": 1, "resultList": {"result": [{"doi": EUROPEPMC_DOI}]}},
    {"hitCount": 1, "resultList": {"result": [{"id": 4, "doi": EUROPEPMC_DOI}]}},
    {"hitCount": 1, "resultList": {"result": [None]}},
    {"hitCount": 1, "resultList": {"result": [{"id": "", "doi": EUROPEPMC_DOI}]}},
    {"hitCount": 1, "resultList": {"result": [{"id": "a\x00b", "doi": EUROPEPMC_DOI}]}},
    {"hitCount": 1, "resultList": {"result": [{"id": "a" * 161, "doi": EUROPEPMC_DOI}]}},
    {"hitCount": "1", "resultList": {"result": [{"id": "x", "doi": EUROPEPMC_DOI}]}},
    {"hitCount": 1, "resultList": {"result": "not-an-array"}},
    {"hitCount": True, "resultList": {"result": [{"id": "x", "doi": EUROPEPMC_DOI}]}},
    {"hitCount": 1, "resultList": {"result": [{"id": "x", "doi": EUROPEPMC_DOI + " "}]}},
    {"hitCount": 1, "resultList": {"result": [{"id": "x", "doi": EUROPEPMC_DOI}] * 2}},
])
async def test_missing_or_wrong_source_identity_never_yields_paper_receipt(data: object) -> None:
    fake = FakeEuropePMC()
    fake.data = deepcopy(data)
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        with pytest.raises(NonRetryableInvocationError):
            await run_europepmc_paper_a5(
                expected_source_fingerprint=(await probe_europepmc_paper_a5()).source_fingerprint,
                host_doi=EUROPEPMC_DOI, http_client=client,
                network_policy=NetworkPolicy.trusted_internal(),
            )
    assert len(fake.requests) == 1


@pytest.mark.asyncio
async def test_reported_upstream_hit_count_is_not_falsely_a_verified_match_count() -> None:
    fake = FakeEuropePMC()
    assert isinstance(fake.data, dict)
    fake.data["hitCount"] = 17
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        result = await run_europepmc_paper_a5(
            expected_source_fingerprint=(await probe_europepmc_paper_a5()).source_fingerprint,
            host_doi=EUROPEPMC_DOI, http_client=client,
            network_policy=NetworkPolicy.trusted_internal(),
        )
    assert result.hit_count == 17
    assert result.record_id == "23903748"
    assert len(fake.requests) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("host_doi", [
    "https://private.invalid/a", "10.١٢٣٤/unicode", "10.1234/bad\x00control",
    "10.1234/space query", "10.1234/" + "a" * 600,
    "10.1234/*", "10.1234/record?", "10.1234/(OR)", "10.1234/[1 TO 9]",
])
async def test_invalid_host_doi_rejected_before_network(host_doi: str) -> None:
    fake = FakeEuropePMC()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        with pytest.raises(SchemaSourceError, match="DOI"):
            await run_europepmc_paper_a5(
                expected_source_fingerprint=(await probe_europepmc_paper_a5()).source_fingerprint,
                host_doi=host_doi, http_client=client,
            )
    assert not fake.requests


@pytest.mark.asyncio
@pytest.mark.parametrize("arguments", [
    {"query": f"DOI:{EUROPEPMC_DOI}", "format": "xml", "pageSize": 1},
    {"query": f"DOI:{EUROPEPMC_DOI}", "format": "json", "pageSize": 2},
    {"query": EUROPEPMC_DOI, "format": "json", "pageSize": 1},
    {"query": f"DOI:{EUROPEPMC_DOI}", "format": "json", "pageSize": True},
])
async def test_direct_native_invocation_rejects_unreviewed_query_envelope(
    arguments: dict[str, object],
) -> None:
    fake = FakeEuropePMC()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        router = _router(client=client)
        probe = inspect_europepmc_paper_source()
        tool = register_reviewed_europepmc_paper_source(
            router, expected_source_fingerprint=probe.source_fingerprint,
            expected_base_url=probe.base_url,
            license="source-license-unverified-research-only", reviewed_by="host",
        )
        call = ToolCall(
            tool=tool.key, endpoint="search_doi", arguments=arguments,
            fields=["hitCount"],
            schema_fingerprint=tool.endpoint("search_doi").fingerprint,
            tool_fingerprint=tool.fingerprint,
        )
        with pytest.raises((
            NonRetryableInvocationError, SchemaSourceError, SchemaValidationError,
        )):
            await router.execute(ExecutionPlan(
                query="unapproved EPMC query", registry_version=router.registry.version,
                calls=[call],
            ), config={"principal": PRINCIPAL.model_dump()})
    assert not fake.requests


PRINCIPAL = PrincipalContext(subject="approved-reader", roles=("reader",))


@pytest.mark.asyncio
async def test_unapproved_principal_fails_before_any_provider_request() -> None:
    fake = FakeEuropePMC()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        router = _router(client=client)
        probe = inspect_europepmc_paper_source()
        tool = register_reviewed_europepmc_paper_source(
            router, expected_source_fingerprint=probe.source_fingerprint,
            expected_base_url=probe.base_url,
            license="source-license-unverified-research-only", reviewed_by="host",
        )
        with pytest.raises(PolicyViolationError):
            await router.execute(ExecutionPlan(
                query="unauthorized", registry_version=router.registry.version,
                calls=[ToolCall(
                    tool=tool.key, endpoint="search_doi",
                    arguments={"query": f"DOI:{EUROPEPMC_DOI}",
                               "format": "json", "pageSize": 1},
                    fields=["hitCount"],
                    schema_fingerprint=tool.endpoint("search_doi").fingerprint,
                    tool_fingerprint=tool.fingerprint,
                )],
            ), config={"principal": PrincipalContext(
                subject="unauthorized", roles=("guest",),
            ).model_dump()})
    assert not fake.requests


def test_modified_source_contract_never_attestable_even_with_new_matching_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = europepmc_registration._curated_source

    def changed_source():
        tool, base = original()
        endpoint = tool.endpoint("search_doi")
        endpoint.output_fields[1].path = ["invented", "doi"]
        return tool, base

    monkeypatch.setattr(europepmc_registration, "_curated_source", changed_source)
    changed = inspect_europepmc_paper_source()
    router = _router()
    with pytest.raises(SchemaSourceError, match="typed contract"):
        register_reviewed_europepmc_paper_source(
            router, expected_source_fingerprint=changed.source_fingerprint,
            expected_base_url=changed.base_url,
            license="source-license-unverified-research-only", reviewed_by="host",
        )
    assert router.registry.keys() == ()

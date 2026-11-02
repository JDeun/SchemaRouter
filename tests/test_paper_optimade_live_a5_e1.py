"""Source-discovered OPTIMADE → reviewed bound invoker → real A5 E1 wire."""

from __future__ import annotations

import json
from urllib.parse import unquote

import httpx
import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    ExecutionPolicy,
    SchemaRouter,
    register_reviewed_optimade_paper_source,
)
from schemarouter.errors import (
    NonRetryableInvocationError,
    SchemaSourceError,
    SchemaValidationError,
)
from schemarouter.network_policy import NetworkPolicy, NetworkPolicyError
from scripts.research_paper_optimade_live_e1 import (
    COD_OPTIMADE_URL,
    COD_VERSIONED_URL,
    probe_cod_optimade_paper_a5,
    run_cod_optimade_paper_a5,
)


def _info(url: str) -> dict:
    return {"data": {"type": "info", "id": "/", "attributes": {
        "api_version": "1.3.0",
        "available_api_versions": [{"url": url, "version": "1.3.0"}],
        "formats": ["json"],
        "entry_types_by_format": {"json": ["structures"]},
        "available_endpoints": ["structures", "info"], "is_index": False,
    }}}


def _structure_info(*, with_formula: bool = True,
                    invalid_formula_type: bool = False) -> dict:
    fields = {"nelements": {"type": "integer"}, "elements": {
        "type": "list", "items": {"type": "string"},
    }}
    if with_formula:
        fields["chemical_formula_descriptive"] = {
            "type": ["string", "null"] if not invalid_formula_type
            else ["string", "integer", "null"],
            "x-optimade-type": "string",
        }
    return {"data": {"type": "info", "id": "structures", "description": "structures",
                     "properties": fields,
                     "output_fields_by_format": {"json": list(fields)}}}


class FakeCOD:
    def __init__(self, *, with_formula: bool = True,
                 get_id: str = "1000059", get_formula: str | None = "O2Si",
                 invalid_formula_type: bool = False) -> None:
        self.with_formula = with_formula
        self.get_id = get_id
        self.get_formula = get_formula
        self.invalid_formula_type = invalid_formula_type
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.method != "GET":
            raise AssertionError("unsafe verb")
        if request.url.path == "/cod/optimade/v1/info":
            payload = _info(COD_VERSIONED_URL)
        elif request.url.path == "/cod/optimade/v1/info/structures":
            payload = _structure_info(with_formula=self.with_formula,
                                      invalid_formula_type=self.invalid_formula_type)
        elif request.url.path == "/cod/optimade/v1/structures":
            assert request.url.params["page_limit"] == "1"
            assert "elements HAS ALL" in request.url.params["filter"]
            payload = {"data": [{"type": "structures", "id": "1000059", "attributes": {
                "chemical_formula_descriptive": "O2Si", "nelements": 2,
                "elements": ["Si", "O"],
            }}]}
        elif request.url.path.startswith("/cod/optimade/v1/structures/"):
            assert unquote(request.url.path.rpartition("/")[2]) == "1000059"
            payload = {"data": {"type": "structures", "id": self.get_id,
                                "attributes": {"chemical_formula_descriptive":
                                               self.get_formula}}}
        else:
            raise AssertionError(f"unexpected OPTIMADE URL: {request.url}")
        return httpx.Response(200, content=json.dumps(payload),
                              headers={"content-type": "application/vnd.api+json"})


def _router() -> SchemaRouter:
    return SchemaRouter(
        policy=ExecutionPolicy(allow_unclassified_remote=True),
        authorization_policy=AuthorizationPolicy(default_effect="deny", rules=(
            AuthorizationRule(effect="allow", operation="cod_a5.get_structures",
                              roles_any=("reader",)),
            AuthorizationRule(effect="allow", operation="cod_a5.search_structures",
                              roles_any=("reader",)),
        )),
    )


@pytest.mark.asyncio
async def test_live_source_probe_registration_and_a5_get_use_same_native_binding():
    fake = FakeCOD()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        probe = await probe_cod_optimade_paper_a5(
            http_client=client, network_policy=NetworkPolicy.trusted_internal(),
        )
        assert probe.versioned_base_url == COD_VERSIONED_URL
        assert "chemical_formula_descriptive" in probe.available_fields
        assert probe.source_fingerprint
        assert [str(x.url) for x in fake.requests] == [
            f"{COD_VERSIONED_URL}/info", f"{COD_VERSIONED_URL}/info/structures",
        ]
        fake.requests.clear()
        outcome = await run_cod_optimade_paper_a5(
            expected_source_fingerprint=probe.source_fingerprint,
            http_client=client, network_policy=NetworkPolicy.trusted_internal(),
        )
        assert outcome.source_id == "1000059"
        assert outcome.formula == "O2Si"
        assert outcome.route_id == "cod_a5.get_structures"
        assert outcome.host_bound_tool_calls == 1
        assert outcome.independent_e2 is False
        assert [x.url.path for x in fake.requests] == [
            "/cod/optimade/v1/info", "/cod/optimade/v1/info/structures",
            "/cod/optimade/v1/structures", "/cod/optimade/v1/structures/1000059",
        ]
        assert fake.requests[-1].url.params["response_fields"] == "chemical_formula_descriptive"


@pytest.mark.asyncio
async def test_registration_requires_pinned_fingerprint_and_never_publishes_stale_source():
    fake = FakeCOD()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        router = _router()
        with pytest.raises(SchemaSourceError, match="fingerprint"):
            await register_reviewed_optimade_paper_source(
                router, url=COD_OPTIMADE_URL, name="cod_a5",
                expected_fingerprint="stale-host-reviewed-digest",
                expected_versioned_base_url=COD_VERSIONED_URL,
                license="source-license-unverified-research-only",
                field_semantic_ids={"chemical_formula_descriptive": "materials.formula"},
                identifier_semantic_id="materials.entry_id", http_client=client,
                network_policy=NetworkPolicy.trusted_internal(),
            )
        assert router.registry.keys() == ()
        assert len(fake.requests) == 2  # only discovery, no data reads


@pytest.mark.asyncio
async def test_live_a5_rejects_changed_schema_before_any_task_network_request():
    fake = FakeCOD(with_formula=False)
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        with pytest.raises(SchemaSourceError, match="fingerprint|unknown field"):
            await run_cod_optimade_paper_a5(
                expected_source_fingerprint="a-known-different-fingerprint",
                http_client=client, network_policy=NetworkPolicy.trusted_internal(),
            )
        assert all(not x.url.path.startswith("/cod/optimade/v1/structures")
                   for x in fake.requests)


@pytest.mark.asyncio
async def test_live_a5_rejects_provider_identity_swap_even_after_valid_search():
    fake = FakeCOD(get_id="different")
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        probe = await probe_cod_optimade_paper_a5(
            http_client=client, network_policy=NetworkPolicy.trusted_internal(),
        )
        with pytest.raises(NonRetryableInvocationError, match="identity"):
            await run_cod_optimade_paper_a5(
                expected_source_fingerprint=probe.source_fingerprint,
                http_client=client, network_policy=NetworkPolicy.trusted_internal(),
            )


@pytest.mark.asyncio
@pytest.mark.parametrize("get_formula", ["C6H6", None])
async def test_live_a5_rejects_changed_or_null_formula_after_host_source_search(get_formula):
    fake = FakeCOD(get_formula=get_formula)
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        probe = await probe_cod_optimade_paper_a5(
            http_client=client, network_policy=NetworkPolicy.trusted_internal(),
        )
        with pytest.raises((SchemaSourceError, SchemaValidationError),
                           match="formula|field|chemical_formula"):
            await run_cod_optimade_paper_a5(
                expected_source_fingerprint=probe.source_fingerprint,
                http_client=client, network_policy=NetworkPolicy.trusted_internal(),
            )


@pytest.mark.asyncio
async def test_nullable_refinement_rejects_unrelated_source_schema_types():
    fake = FakeCOD(invalid_formula_type=True)
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        probe = await probe_cod_optimade_paper_a5(
            http_client=client, network_policy=NetworkPolicy.trusted_internal(),
        )
        with pytest.raises(SchemaSourceError, match="nullable|string|refinement"):
            await run_cod_optimade_paper_a5(
                expected_source_fingerprint=probe.source_fingerprint,
                http_client=client, network_policy=NetworkPolicy.trusted_internal(),
            )


@pytest.mark.asyncio
async def test_pinned_source_url_cannot_be_changed_after_host_review():
    fake = FakeCOD()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        probe = await probe_cod_optimade_paper_a5(
            http_client=client, network_policy=NetworkPolicy.trusted_internal(),
        )
        router = _router()
        fake.requests.clear()
        with pytest.raises(SchemaSourceError, match="fingerprint or identity"):
            await register_reviewed_optimade_paper_source(
                router, url=COD_OPTIMADE_URL, name="cod_a5",
                expected_fingerprint=probe.source_fingerprint,
                expected_versioned_base_url="https://another.example/v1",
                license="source-license-unverified-research-only",
                field_semantic_ids={"chemical_formula_descriptive": "materials.formula"},
                identifier_semantic_id="materials.entry_id", http_client=client,
                network_policy=NetworkPolicy.trusted_internal(),
            )
        assert router.registry.keys() == ()
        assert len(fake.requests) == 2


@pytest.mark.asyncio
async def test_default_registration_network_policy_rejects_internal_destination():
    fake = FakeCOD()
    async with httpx.AsyncClient(transport=httpx.MockTransport(fake)) as client:
        with pytest.raises(NetworkPolicyError):
            await register_reviewed_optimade_paper_source(
                _router(), url="https://127.0.0.1/optimade", name="cod_a5",
                expected_fingerprint="host-pinned-snapshot",
                expected_versioned_base_url="https://127.0.0.1/optimade/v1",
                license="source-license-unverified-research-only",
                field_semantic_ids={"chemical_formula_descriptive": "materials.formula"},
                identifier_semantic_id="materials.entry_id", http_client=client,
            )
        assert fake.requests == []

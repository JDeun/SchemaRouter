"""#1560: host-reviewed OPTIMADE ID, source-unit, and canonical-unit contracts."""
from __future__ import annotations

import httpx
import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    ExecutionPlan,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    NativeSchemaGraphIndex,
    PrincipalContext,
    SchemaRouter,
    ToolCall,
    UnitNormalizationSpec,
    compile_paper_typed_tool_plan,
)
from schemarouter.adapters import OPTIMADERemoteInvoker
from schemarouter.adapters.optimade import _tool_from_discovery, review_optimade_paper_tool
from schemarouter.errors import NonRetryableInvocationError, SchemaSourceError
from schemarouter.native_graph_index import NativeSchemaPostingIndex

BASE_URL = "https://materials.example/v1"
LICENSE = "owner-reviewed-materials-db"
ACTOR = PrincipalContext(subject="approved-materials-analyst", roles=("reader",))
ALIASES = ("materials band gap", "재료 밴드갭", "材料バンドギャップ")
ROOT = "materials.get_structures"
NORMALIZATION = UnitNormalizationSpec(
    dimension="energy", canonical_unit="J", scale=1.602176634e-19,
)


def _source_tool():
    return _tool_from_discovery(
        name="materials", namespace=None, versioned_base_url=BASE_URL,
        base_info={"api_version": "1.3.0"},
        entries={
            "structures": {
                "properties": {"_lab_band_gap": {
                    "type": "number", "x-optimade-unit": "eV",
                }},
                "output_fields_by_format": {"json": ["_lab_band_gap"]},
            },
            "references": {
                "properties": {"title": {"type": "string"}},
                "output_fields_by_format": {"json": ["title"]},
            },
        },
        skipped=[],
    )


def _review(tool=None, **overrides):
    source = tool or _source_tool()
    args = {
        "expected_fingerprint": source.fingerprint,
        "expected_versioned_base_url": BASE_URL,
        "entry_type": "structures", "license": LICENSE,
        "field_semantic_ids": {"_lab_band_gap": "materials.band_gap"},
        "reviewed_unit_normalizations": {"_lab_band_gap": NORMALIZATION},
        "expected_source_units": {"_lab_band_gap": "eV"},
        "identifier_semantic_id": "materials.entry_id",
    }
    args.update(overrides)
    return review_optimade_paper_tool(source, **args)


def _catalog():
    return NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="materials.band_gap", aliases=ALIASES,
        required_fields=(CapabilityFieldContract(
            semantic_id="materials.band_gap", json_schema={"type": "number"},
            unit="J", dimension="energy",
        ),),
        source_type="optimade", license=LICENSE,
    ),))


def _router(tool, invoker):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(effect="allow", operation=ROOT, roles_any=("reader",)),),
    ))
    router.add_bound_tool(tool, invoker)
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
        approved_host_roots=frozenset({ROOT}),
    )
    return router, index


def test_get_single_entry_has_closed_required_id_input():
    endpoint = _source_tool().endpoint("get_structures")
    assert [(p.name, p.required, p.location) for p in endpoint.parameters] == [
        ("id", True, "path"),
    ]
    assert endpoint.input_schema == {
        "type": "object",
        "properties": {"id": {"type": "string", "minLength": 1}},
        "required": ["id"], "additionalProperties": False,
    }


def test_host_review_pins_original_source_and_units_without_mutation():
    source = _source_tool()
    fingerprint = source.fingerprint
    reviewed = _review(source)
    assert source.fingerprint == fingerprint and source.license is None
    assert source.endpoint("get_structures").parameters[0].semantic_id is None
    assert reviewed.fingerprint != fingerprint and reviewed.license == LICENSE
    assert {e.name for e in reviewed.endpoints} == {"search_structures", "get_structures"}
    assert reviewed.metadata["paper_optimade_review"]["source_tool_fingerprint"] == fingerprint
    get = reviewed.endpoint("get_structures")
    assert get.parameters[0].semantic_id == "materials.entry_id"
    assert get.input_schema["additionalProperties"] is False
    field = next(f for f in get.output_fields if f.name == "_lab_band_gap")
    assert (field.semantic_id, field.unit, field.unit_normalization.canonical_unit) == (
        "materials.band_gap", "eV", "J",
    )
    assert field.json_schema == {"type": "number"}


def test_review_cannot_be_repeated_to_erase_original_attestation():
    reviewed = _review()
    with pytest.raises(SchemaSourceError, match="already reviewed"):
        _review(reviewed)


def test_review_rejects_identifier_semantic_aliasing_a_physical_quantity():
    with pytest.raises(SchemaSourceError, match="identifier semantic"):
        _review(identifier_semantic_id="materials.band_gap")


def test_review_rejects_mismatched_source_unit_and_untrusted_unit_annotation():
    with pytest.raises(SchemaSourceError, match="source unit"):
        _review(expected_source_units={"_lab_band_gap": "meV"})
    source = _source_tool()
    for endpoint in source.endpoints:
        for field in endpoint.output_fields:
            if field.name == "_lab_band_gap":
                field.json_schema["x-optimade-unit"] = "meV"
    with pytest.raises(SchemaSourceError, match="source unit annotation"):
        _review(source)


@pytest.mark.parametrize(
    ("response_id", "response_type"),
    [("other-record", "structures"), ("db/42", "references"), (None, "structures")],
)
@pytest.mark.asyncio
async def test_get_refuses_source_record_identity_swap(response_id, response_type):
    reviewed = _review()
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        return httpx.Response(200, json={"data": {
            "id": response_id, "type": response_type,
            "attributes": {"_lab_band_gap": 2.0},
        }})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OPTIMADERemoteInvoker(reviewed, BASE_URL, http_client=client)
        call = ToolCall(
            tool="materials", endpoint="get_structures",
            arguments={"id": "db/42"}, fields=["_lab_band_gap"],
        )
        with pytest.raises(NonRetryableInvocationError, match="identity"):
            await invoker.invoke_call(call)
    assert len(seen) == 1


@pytest.mark.asyncio
async def test_original_paper_plan_binds_exact_host_id_and_preserves_source_and_canonical_units():
    seen_urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, json={"data": {
            "id": "db/42", "type": "structures",
            "attributes": {"_lab_band_gap": 2.0},
        }})

    reviewed = _review()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OPTIMADERemoteInvoker(reviewed, BASE_URL, http_client=client)
        router, index = _router(reviewed, invoker)
        catalog = _catalog()
        deferred = compile_paper_typed_tool_plan(
            router, ALIASES[0], principal=ACTOR, catalog=catalog, index=index,
        )
        assert deferred.status == "requires_arguments"
        assert len(deferred.calls) == 1
        assert deferred.calls[0].call.missing_required_arguments == ["id"]
        assert deferred.calls[0].call.arguments == {} and seen_urls == []
        plan = compile_paper_typed_tool_plan(
            router, ALIASES[1], principal=ACTOR, catalog=catalog, index=index,
            host_source_arguments={ROOT: {"id": "db/42"}},
        )
        assert plan.status == "ready" and plan.executable_authority is False
        assert plan.calls[0].route_id == ROOT
        assert plan.calls[0].call.fields == ["_lab_band_gap"]
        assert plan.calls[0].call.arguments == {"id": "db/42"}
        field = plan.calls[0].fields_meta[0]
        assert (field.semantic_id, field.source_unit, field.unit) == (
            "materials.band_gap", "eV", "J",
        )
        assert seen_urls == []


@pytest.mark.asyncio
async def test_standard_executor_applies_only_the_host_reviewed_unit_conversion():
    seen_urls = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen_urls.append(str(request.url))
        return httpx.Response(200, json={"data": {
            "id": "db/42", "type": "structures",
            "attributes": {"_lab_band_gap": 2.0},
        }})

    reviewed = _review()
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        invoker = OPTIMADERemoteInvoker(reviewed, BASE_URL, http_client=client)
        router, index = _router(reviewed, invoker)
        plan = compile_paper_typed_tool_plan(
            router, ALIASES[0], principal=ACTOR, catalog=_catalog(), index=index,
            host_source_arguments={ROOT: {"id": "db/42"}},
        )
        results = await router.execute(
            ExecutionPlan(
                query="host approved source projection",
                registry_version=router.registry.version,
                calls=[plan.calls[0].call],
            ),
            config={"principal": ACTOR.model_dump()},
        )
    assert len(seen_urls) == 1
    assert results[0].data["_lab_band_gap"] == pytest.approx(3.204353268e-19)
    contract = results[0].field_contracts["_lab_band_gap"]
    assert (contract.source_unit, contract.unit, contract.dimension) == ("eV", "J", "energy")


def test_unreviewed_provider_unit_is_not_a_semantic_hit():
    source = _source_tool()
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(effect="allow", operation=ROOT, roles_any=("reader",)),),
    ))
    router.add_tool(source)
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    plan = compile_paper_typed_tool_plan(
        router, ALIASES[0], principal=ACTOR, catalog=_catalog(), index=index,
    )
    assert plan.status == "no_proven_hit" and plan.calls == ()

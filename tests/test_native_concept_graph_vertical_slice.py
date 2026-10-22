"""End-to-end authorized concept -> complete native routes (no execution)."""

from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.concept_graph_retrieval import retrieve_authorized_concept_graph
from schemarouter.errors import PolicyViolationError
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex

ACTOR = PrincipalContext(subject="analyst", roles=("reader",))
VIEWER = PrincipalContext(subject="viewer", roles=("viewer",))


def _catalog(*, two_fields: bool = False) -> NativeConceptCatalog:
    fields = (
        CapabilityFieldContract(semantic_id="crm.status", json_schema={"type": "string"}),
    )
    if two_fields:
        fields += (
            CapabilityFieldContract(semantic_id="crm.priority", json_schema={"type": "string"}),
        )
    return NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="case_status", aliases=("case status", "문의 상태", "問い合わせ状態"),
        required_fields=fields, source_type="crm", license="owner-reviewed",
    ),))


def _policy(*, hidden: bool = False) -> AuthorizationPolicy:
    return AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(effect="allow", operation="*.*", roles_any=("reader", "viewer")),),
        data_rules=(DataScopeRule(
            operation="complete.read", roles_any=("viewer",), hidden_fields=("priority",),
        ),) if hidden else (),
    )


def _index(router: SchemaRouter) -> NativeSchemaGraphIndex:
    return NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))


def _direct_router() -> SchemaRouter:
    router = SchemaRouter(authorization_policy=_policy(hidden=True))
    for name, fields in (
        ("status_only", ("status",)),
        ("priority_only", ("priority",)),
        ("complete", ("status", "priority")),
    ):
        router.add_tool(ToolSpec(
            name=name, source_type="crm", license="owner-reviewed",
            endpoints=[EndpointSpec(name="read", read_only=True, output_fields=[
                FieldSpec(name=field, semantic_id=f"crm.{field}", json_schema={"type": "string"})
                for field in fields
            ])],
        ))
    return router


def _joined_router(*, incomplete: bool = False, extra_consumers: int = 0) -> SchemaRouter:
    router = SchemaRouter(authorization_policy=_policy())
    producer_fields = (("contact_id", "crm.contact_id"), ("region_id", "crm.region_id"))
    if incomplete:
        producer_fields = producer_fields[:1]
    router.add_tool(ToolSpec(
        name="contacts", source_type="crm", license="owner-reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            output_fields=[FieldSpec(name=name, semantic_id=semantic, identifier=True,
                                     json_schema={"type": "string"})
                           for name, semantic in producer_fields],
            output_schema={"type": "object", "properties": {
                name: {"type": "string"} for name, _ in producer_fields
            }, "required": [name for name, _ in producer_fields]},
        )],
    ))
    for index in range(extra_consumers + 1):
        name = "cases" if index == 0 else f"cases_{index}"
        params = ("contact_id", "region_id")
        router.add_tool(ToolSpec(
            name=name, source_type="crm", license="owner-reviewed",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                parameters=[ParameterSpec(name=p, semantic_id=f"crm.{p}", required=True,
                                          json_schema={"type": "string"}) for p in params],
                input_schema={"type": "object", "properties": {
                    p: {"type": "string"} for p in params
                }, "required": list(params)},
                output_fields=[FieldSpec(name="status", semantic_id="crm.status",
                                         json_schema={"type": "string"})],
            )],
        ))
    return router


def _select(router: SchemaRouter, *, catalog: NativeConceptCatalog | None = None,
            principal: PrincipalContext = ACTOR, query: str = "case status"):
    return retrieve_authorized_concept_graph(
        router, query, catalog=catalog or _catalog(), principal=principal, index=_index(router),
    )


def test_direct_complete_fieldgroup_precedes_partial_siblings() -> None:
    router = _direct_router()
    result = _select(router, catalog=_catalog(two_fields=True))
    assert result.status == "complete"
    assert result.route_ids == ("complete.read",)
    assert result.route_sets[0].required_semantic_ids == ("crm.priority", "crm.status")
    assert len(result.route_sets[0].route_fingerprints) == 1
    assert not result.executable_authority


def test_authorized_one_hop_preserves_route_ids_and_join_bindings() -> None:
    router = _joined_router()
    result = _select(router)
    assert result.status == "complete"
    assert result.route_ids == ("contacts.read", "cases.read")
    assert result.route_sets[0].parameter_bindings == (
        ("contact_id", "contact_id"), ("region_id", "region_id"),
    )
    assert len(result.route_sets[0].route_fingerprints) == 2
    assert not result.independent_quality_evidence
    assert not result.calibrated_no_fit
    assert not result.executable_authority


def test_reject_partial_native_join() -> None:
    assert _select(_joined_router(incomplete=True)).status == "no_proven_hit"
    assert _select(_joined_router(incomplete=True)).route_ids == ()


def test_graph_over_k_shared_root_is_not_arbitrary_top5() -> None:
    result = _select(_joined_router(extra_consumers=5))
    assert result.status == "over_k_unranked"
    assert result.route_ids == ()
    assert result.route_sets == ()


def test_input_required_consumers_cannot_hide_valid_direct_before_k() -> None:
    """Pre-K direct completeness includes the absence of unbound inputs."""
    router = _joined_router(extra_consumers=7)
    router.add_tool(ToolSpec(
        name="direct_status", source_type="crm", license="owner-reviewed",
        endpoints=[EndpointSpec(name="read", read_only=True,
                                output_fields=[FieldSpec(
                                    name="status", semantic_id="crm.status",
                                    json_schema={"type": "string"},
                                )])],
    ))
    result = _select(router)
    assert result.status == "complete"
    assert result.route_ids == ("direct_status.read",)


def test_graph_denied_and_hidden_routes_leave_no_public_metadata() -> None:
    result = _select(_direct_router(), catalog=_catalog(two_fields=True), principal=VIEWER)
    assert result.status == "no_proven_hit"
    assert result.route_ids == ()
    assert result.route_sets == ()


def test_graph_changed_registry_or_policy_fails_closed() -> None:
    router = _joined_router()
    index = _index(router)
    router.add_tool(ToolSpec(name="new", endpoints=[EndpointSpec(name="read", read_only=True)]))
    with pytest.raises(PolicyViolationError):
        retrieve_authorized_concept_graph(
            router, "case status", catalog=_catalog(), principal=ACTOR, index=index,
        )


def test_direct_candidate_revoked_by_live_availability_during_graph_lookup(
    monkeypatch,
) -> None:
    router = _direct_router()
    index = _index(router)
    available = {"complete.read": True}

    def eligible(tool, endpoint):
        return available.get(f"{tool.key}.{endpoint.name}", True)

    router.planner.availability_predicate = eligible
    original = NativeSchemaGraphIndex.lookup

    def revoke(*args, **kwargs):
        result = original(*args, **kwargs)
        available["complete.read"] = False
        return result

    monkeypatch.setattr(NativeSchemaGraphIndex, "lookup", revoke)
    with pytest.raises(PolicyViolationError):
        retrieve_authorized_concept_graph(
            router, "case status", principal=ACTOR,
            catalog=_catalog(two_fields=True), index=index,
        )


def test_graph_owner_catalog_mutation_refused() -> None:
    catalog = _catalog()
    catalog.concepts[0].required_fields[0].json_schema["type"] = "object"
    with pytest.raises(ValueError):
        _select(_joined_router(), catalog=catalog)


@pytest.mark.parametrize("query", ("case status", "문의 상태", "問い合わせ状態"))
def test_graph_ko_ja_en_aliases_produce_same_typed_paths(query: str) -> None:
    result = _select(_joined_router(), query=query)
    assert result.route_ids == ("contacts.read", "cases.read")


@pytest.mark.parametrize("k", (0, 4, 6, True, 5.0))
def test_graph_k_must_equal_five(k: object) -> None:
    router = _joined_router()
    with pytest.raises(ValueError):
        retrieve_authorized_concept_graph(
            router, "case status", catalog=_catalog(), principal=ACTOR,
            index=_index(router), k=k,
        )

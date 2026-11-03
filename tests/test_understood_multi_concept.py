"""One fixed ontology across independent/missing concept queries; no model or tool calls."""
from __future__ import annotations

from dataclasses import asdict

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
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperUnderstanding,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.paper_understood_direct_plan import compile_paper_understood_direct_plan

ACTOR = PrincipalContext(subject="reader", roles=("reader",))
# Explicit local fixture authorities, not claims about external provider licences.
SOURCES = {
    "material": ("materials-fixture", "materials-fixture-license"),
    "literature": ("literature-fixture", "literature-fixture-license"),
    "crm": ("crm-fixture", "crm-fixture-license"),
    "inventory": ("inventory-fixture", "inventory-fixture-license"),
    "weather": ("weather-fixture", "weather-fixture-license"),
    "finance": ("finance-fixture", "finance-fixture-license"),
}


def _concept(concept_id, semantic, kind, aliases, *, unit=None):
    source, license_id = SOURCES[concept_id.split(".")[0]]
    return NativeDeclaredConcept(
        concept_id=concept_id, aliases=aliases, source_type=source, license=license_id,
        required_fields=(CapabilityFieldContract(
            semantic_id=semantic, json_schema={"type": kind}, unit=unit,
        ),),
    )


CATALOG = NativeConceptCatalog(concepts=(
    _concept("material.band_gap", "band_gap", "number", ("band gap", "밴드갭"), unit="eV"),
    _concept("material.density", "density", "number", ("material density", "재료 밀도")),
    _concept("literature.abstract", "document_abstract", "string", ("paper abstract", "논문 초록")),
    _concept("crm.status", "crm.status", "string", ("case status", "문의 상태")),
    _concept("crm.priority", "crm.priority", "string", ("case priority", "문의 우선순위")),
    _concept("inventory.stock", "stock", "integer", ("stock count", "재고 수량")),
    _concept("weather.temperature", "temperature", "number", ("air temperature", "기온")),
    _concept("finance.price", "price", "number", ("stock price", "주가")),
    NativeDeclaredConcept(
        concept_id="crm.overview", aliases=("complete case overview", "문의 전체 요약"),
        source_type=SOURCES["crm"][0], license=SOURCES["crm"][1],
        required_fields=(
            CapabilityFieldContract(semantic_id="crm.status", json_schema={"type": "string"}),
            CapabilityFieldContract(semantic_id="crm.priority", json_schema={"type": "string"}),
        ),
    ),
))
INTENTS = PaperIntentRegistry(intents=(
    PaperIntentDeclaration(intent_id="material.lookup",
                           required_concept_ids=("material.band_gap",)),
    PaperIntentDeclaration(intent_id="research.summary", required_concept_ids=(
        "material.band_gap", "literature.abstract",
    )),
    PaperIntentDeclaration(intent_id="material.properties", required_concept_ids=(
        "material.band_gap", "material.density",
    )),
    PaperIntentDeclaration(intent_id="case.overview", required_concept_ids=(
        "crm.status", "crm.priority",
    )),
    PaperIntentDeclaration(intent_id="case.review", required_concept_ids=(
        "crm.overview", "literature.abstract",
    )),
    PaperIntentDeclaration(intent_id="all.metrics", required_concept_ids=(
        "material.band_gap", "literature.abstract", "crm.status", "inventory.stock",
        "weather.temperature", "finance.price",
    )),
))


def _tool(name, family, fields, *, parameters=()):
    source, license_id = SOURCES[family]
    return ToolSpec(
        name=name, source_type=source, license=license_id,
        endpoints=[EndpointSpec(
            name="read", read_only=True, parameters=list(parameters),
            input_schema={
                "type": "object", "properties": {p.name: p.json_schema for p in parameters},
                "required": [p.name for p in parameters if p.required],
            } if parameters else {},
            output_fields=[FieldSpec(name=f"{name}_id", semantic_id=f"{family}.{name}.id",
                                     identifier=True,
                                     json_schema={"type": "string"}), *fields],
        )],
    )


def _field(name, semantic, kind="string", **kwargs):
    return FieldSpec(name=name, semantic_id=semantic, json_schema={"type": kind}, **kwargs)


def _router():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),),
    ))
    router.add_tool(_tool("materials", "material", [
        _field("gap", "band_gap", "number", unit="eV"),
    ]))
    router.add_tool(_tool("papers", "literature", [_field("abstract", "document_abstract")]))
    return router


def _compile(router, understanding, *, session=None, inputs=None):
    session = session or router.prepare_field_routing(catalog=CATALOG)
    return session.compile_understood(
        understanding, principal=ACTOR, intent_registry=INTENTS,
        host_source_arguments=inputs,
    )


@pytest.mark.parametrize("understanding", [
    PaperUnderstanding(intent_id="research.summary"),
    PaperUnderstanding(intent_id="material.lookup", concept_ids=("literature.abstract",)),
    PaperUnderstanding(intent_id="research.summary", named_tools=("materials", "papers"),
                       parameter_hints={"material_id": "UNTRUSTED"}),
])
def test_independent_mixed_source_concepts_compile_complete_groups(understanding):
    router = _router()
    plan = _compile(router, understanding)
    assert plan.status == "ready" and not plan.executable_authority
    assert plan.coverage.complete and plan.coverage.uncovered == []
    assert {r.semantic_id for r in plan.coverage.covered} == {"band_gap", "document_abstract"}
    by_route = {call.route_id: call for call in plan.calls}
    assert by_route["materials.read"].call.fields == ["materials_id", "gap"]
    assert by_route["papers.read"].call.fields == ["papers_id", "abstract"]
    assert by_route["materials.read"].source_type != by_route["papers.read"].source_type
    assert by_route["materials.read"].license != by_route["papers.read"].license
    assert all(call.call.arguments == {} for call in plan.calls)
    assert next(m for m in by_route["materials.read"].fields_meta if m.name == "gap").unit == "eV"


def test_missing_density_is_uncovered_without_discarding_proved_band_gap():
    plan = _compile(_router(), PaperUnderstanding(intent_id="material.properties"))
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert [c.route_id for c in plan.calls] == ["materials.read"]
    assert [r.semantic_id for r in plan.coverage.covered] == ["band_gap"]
    assert [r.semantic_id for r in plan.coverage.uncovered] == ["density"]


def test_repeated_source_route_unions_fields_and_identifiers_once():
    router = _router()
    tool = router.registry.get("materials")
    tool.endpoints[0].output_fields.append(_field("density", "density", "number"))
    router.add_tool(tool, replace=True)
    plan = _compile(router, PaperUnderstanding(intent_id="material.properties"))
    assert plan.status == "ready" and plan.coverage.complete
    assert len(plan.calls) == 1
    assert plan.calls[0].call.fields == ["materials_id", "gap", "density"]


def test_six_independently_proved_routes_exceed_global_k5_budget():
    router = _router()
    for name, family, semantic, kind in (
        ("cases", "crm", "crm.status", "string"),
        ("inventory", "inventory", "stock", "integer"),
        ("weather", "weather", "temperature", "number"),
        ("finance", "finance", "price", "number"),
    ):
        router.add_tool(_tool(name, family, [_field("value", semantic, kind)]))
    plan = _compile(router, PaperUnderstanding(intent_id="all.metrics"))
    assert plan.status == "budget_unsatisfied" and plan.calls == ()
    assert not plan.coverage.complete and plan.coverage.covered == []
    assert len(plan.coverage.uncovered) == 6


def test_hidden_field_and_hidden_decoy_count_do_not_change_partial_public_receipt():
    router = _router()
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("reader",),
        ),), data_rules=(DataScopeRule(
            operation="papers.read", roles_any=("reader",), hidden_fields=("abstract",),
        ), DataScopeRule(operation="private_*.read", roles_any=("reader",),
                         hidden_fields=("abstract",))),
    )
    hints = PaperUnderstanding(intent_id="research.summary")
    first = _compile(router, hints)
    for index in range(33):
        router.add_tool(_tool(f"private_{index}", "literature", [
            _field("abstract", "document_abstract"),
        ]))
    second = _compile(router, hints)
    assert first.status == second.status == "no_proven_hit"
    assert first.calls == second.calls
    assert first.coverage == second.coverage and not second.coverage.complete
    assert "private_" not in repr(second)


def test_current_fingerprint_change_invalidates_prepared_multi_concept_proof():
    router = _router()
    session = router.prepare_field_routing(catalog=CATALOG)
    tool = router.registry.get("papers")
    tool.endpoints[0].output_fields[1].description = "changed source contract"
    router.add_tool(tool, replace=True)
    with pytest.raises(PolicyViolationError, match="source|eligibility|stale"):
        _compile(router, PaperUnderstanding(intent_id="research.summary"), session=session)


def test_explicit_host_root_values_bind_but_model_hints_do_not():
    router = _router()
    tool = _tool("materials", "material", [_field("gap", "band_gap", "number", unit="eV")],
                 parameters=(ParameterSpec(name="material_id", required=True,
                                           json_schema={"type": "string"}),))
    router.add_tool(tool, replace=True)
    session = router.prepare_field_routing(
        catalog=CATALOG, approved_host_roots=frozenset({"materials.read"}),
    )
    hints = PaperUnderstanding(intent_id="research.summary",
                               parameter_hints={"material_id": "MODEL_VALUE"})
    missing = _compile(router, hints, session=session)
    assert missing.status == "requires_arguments" and missing.coverage.complete
    assert next(c for c in missing.calls if c.route_id == "materials.read").call.arguments == {}
    ready = _compile(router, hints, session=session,
                     inputs={"materials.read": {"material_id": "HOST_VALUE"}})
    assert ready.status == "ready"
    assert next(c for c in ready.calls if c.route_id == "materials.read").call.arguments == {
        "material_id": "HOST_VALUE",
    }


def test_direct_public_compiler_uses_the_same_multi_concept_proof():
    router = _router()
    session = router.prepare_field_routing(catalog=CATALOG)
    hints = PaperUnderstanding(intent_id="research.summary")
    direct = compile_paper_understood_direct_plan(
        router, hints, principal=ACTOR, catalog=CATALOG, intent_registry=INTENTS,
        index=session._index,
    )
    assert asdict(direct) == asdict(_compile(router, hints, session=session))


@pytest.mark.parametrize("intent", ["material.lookup", "research.summary"])
def test_unresolved_model_proposals_remain_uncovered_without_source_inference(intent):
    plan = _compile(_router(), PaperUnderstanding(
        intent_id=intent, unresolved_concepts=("unregistered thermal lifetime",),
    ))
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert plan.calls and all(call.call.arguments == {} for call in plan.calls)
    assert [item.model_dump() for item in plan.coverage.uncovered] == [{
        "semantic_id": "unresolved",
        "qualifiers": ["query_concept=unregistered thermal lifetime"],
    }]


def test_wrong_unit_cannot_be_combined_into_a_complete_concept_plan():
    router = _router()
    tool = router.registry.get("materials")
    tool.endpoints[0].output_fields[1].unit = "J"
    router.add_tool(tool, replace=True)
    plan = _compile(router, PaperUnderstanding(intent_id="research.summary"))
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert [call.route_id for call in plan.calls] == ["papers.read"]
    assert [item.semantic_id for item in plan.coverage.uncovered] == ["band_gap"]


def test_same_callable_health_revocation_rejects_earlier_group_proof():
    router = _router()
    observed = 0

    def available(tool, endpoint):
        nonlocal observed
        if tool.name == "materials":
            observed += 1
        return tool.name != "papers" or observed == 0

    router.planner.availability_predicate = available
    with pytest.raises(PolicyViolationError, match="source eligibility changed"):
        _compile(router, PaperUnderstanding(intent_id="research.summary"))


def test_each_concept_remains_an_atomic_complete_group_at_one_endpoint():
    router = _router()
    router.add_tool(_tool("status_only", "crm", [_field("status", "crm.status")]))
    router.add_tool(_tool("priority_only", "crm", [_field("priority", "crm.priority")]))
    plan = _compile(router, PaperUnderstanding(intent_id="case.review"))
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert [call.route_id for call in plan.calls] == ["papers.read"]
    assert {item.semantic_id for item in plan.coverage.uncovered} == {
        "crm.status", "crm.priority",
    }


def test_concepts_sharing_a_typed_graph_target_merge_the_original_binding_once():
    router = _router()
    router.add_tool(_tool("case_keys", "crm", [
        _field("case_id", "crm.case_id", identifier=True),
    ]))
    router.add_tool(_tool("cases", "crm", [
        _field("status", "crm.status"), _field("priority", "crm.priority"),
    ], parameters=(ParameterSpec(name="case_id", semantic_id="crm.case_id", required=True,
                                 json_schema={"type": "string"}),)))
    plan = _compile(router, PaperUnderstanding(intent_id="case.overview", named_tools=("cases",)))
    assert plan.status == "requires_observation" and plan.coverage.complete
    assert [call.route_id for call in plan.calls] == ["case_keys.read", "cases.read"]
    assert [call.call.fields for call in plan.calls] == [
        ["case_id"], ["status", "priority"],
    ]
    assert [(edge.consumer_call_index, edge.parameter,
             edge.producer_call_index, edge.producer_field) for edge in plan.bindings] == [
        (1, "case_id", 0, "case_id"),
    ]
    assert all(not call.call.arguments for call in plan.calls)


def test_mixed_source_proof_does_not_accept_wrong_local_licence():
    router = _router()
    tool = router.registry.get("papers")
    tool.license = SOURCES["material"][1]
    router.add_tool(tool, replace=True)
    plan = _compile(router, PaperUnderstanding(intent_id="research.summary"))
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert [call.route_id for call in plan.calls] == ["materials.read"]
    assert [item.semantic_id for item in plan.coverage.uncovered] == ["document_abstract"]


def test_foreign_host_input_route_is_not_silently_discarded():
    with pytest.raises(ValueError, match="unproved source route"):
        _compile(_router(), PaperUnderstanding(intent_id="research.summary"),
                 inputs={"private.read": {"secret": "NOT_BOUND"}})


@pytest.mark.parametrize("unresolved", ((), ("unregistered thermal lifetime",)))
def test_complete_homogeneous_rank_precedes_independent_concept_menus(unresolved):
    from test_paper_native_rank import (
        ANALYST,
        _paper_catalog,
        _paper_intents,
        _paper_router,
        _paper_understanding,
    )

    from schemarouter import PaperNativeRankPolicy

    router = _paper_router()
    catalog, intents = _paper_catalog(), _paper_intents()
    session = router.prepare_field_routing(catalog=catalog)
    policy = PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id, route_priorities={"full_5.read": 10},
    )
    hints = _paper_understanding().model_copy(update={"unresolved_concepts": unresolved})
    plan = compile_paper_understood_direct_plan(
        router, hints, principal=ANALYST, catalog=catalog, intent_registry=intents,
        index=session._index, rank_policy=policy,
    )
    assert plan.status == ("no_proven_hit" if unresolved else "ready")
    assert len(plan.calls) == 5 and plan.calls[0].route_id == "full_5.read"
    assert all({"status", "priority"} <= set(item.call.fields) for item in plan.calls)
    assert plan.ranked_unverified is True
    assert plan.coverage.complete is (not unresolved)
    assert len(plan.coverage.uncovered) == len(unresolved)


def test_disjoint_same_source_fields_still_split_after_complete_group_no_hit():
    router = _router()
    router.add_tool(_tool("density", "material", [_field("density", "density", "number")]))
    plan = _compile(router, PaperUnderstanding(intent_id="material.properties"))
    assert plan.status == "ready" and plan.coverage.complete
    assert {item.route_id for item in plan.calls} == {"materials.read", "density.read"}

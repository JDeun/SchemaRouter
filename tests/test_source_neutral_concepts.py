"""Optional concept constraints never replace current original-source proof."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

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
    PaperNativeRankPolicy,
    PaperUnderstanding,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.concept_retrieval import _merged_concept_constraints, resolve_native_concepts
from schemarouter.errors import PolicyViolationError

ACTOR = PrincipalContext(subject="neutral-test", roles=("reader",))


def _concept(name, *, source=None, license=None, aliases=None):
    return NativeDeclaredConcept(
        concept_id=f"case.{name}", aliases=aliases or (f"case {name}",),
        required_fields=(CapabilityFieldContract(
            semantic_id=f"case.{name}", json_schema={"type": "string"},
        ),), source_type=source, license=license,
    )


def test_neutral_concept_does_not_fabricate_source_or_license_constraints():
    concept = _concept("status")
    assert concept.source_type is None and concept.license is None
    assert _merged_concept_constraints((concept,)) == (None, None)
    result = resolve_native_concepts(
        "case status", catalog=NativeConceptCatalog(concepts=(concept,)),
    )
    assert result.field_group.source_type is None and result.field_group.license is None


def test_compatible_neutral_and_explicit_constraints_intersect_independently():
    concepts = (_concept("status"), _concept("priority", source="crm"),
                _concept("owner", license="reviewed"))
    assert _merged_concept_constraints(concepts) == ("crm", "reviewed")
    resolved = resolve_native_concepts(
        "case status case priority case owner", catalog=NativeConceptCatalog(concepts=concepts),
    )
    assert (resolved.field_group.source_type, resolved.field_group.license) == ("crm", "reviewed")


@pytest.mark.parametrize("constraints", (
    ({"source": "first"}, {"source": "second"}),
    ({"license": "first"}, {"license": "second"}),
))
def test_conflicting_nonnull_constraints_do_not_merge(constraints):
    concepts = tuple(_concept(name, **values) for name, values in zip(
        ("status", "priority"), constraints, strict=True,
    ))
    assert _merged_concept_constraints(concepts) is None
    with pytest.raises(ValueError, match="incompatible source policy"):
        resolve_native_concepts("case status case priority", catalog=NativeConceptCatalog(
            concepts=concepts,
        ))


def test_unspecified_and_explicit_source_are_not_disjoint_alias_authority():
    with pytest.raises(ValidationError, match="ambiguous owner-declared"):
        NativeConceptCatalog(concepts=(
            _concept("status", aliases=("shared name",)),
            _concept("priority", source="crm", aliases=("shared name",)),
        ))


def _providers(*, count=3, host=False):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(default_effect="deny", rules=(
        AuthorizationRule(effect="allow", operation="*.read", roles_any=("reader",)),
    )))
    health = {chr(97 + i): True for i in range(count)}
    router.planner.availability_predicate = lambda tool, _endpoint: health[tool.key]
    for name in health:
        parameters = [ParameterSpec(name="key", required=True, json_schema={"type": "string"})]
        router.add_tool(ToolSpec(name=name, source_type=f"provider-{name}",
            license=f"license-{name}", endpoints=[EndpointSpec(
                name="read", read_only=True, output_fields=[FieldSpec(
                    name=field, semantic_id=f"case.{field}", json_schema={"type": "string"},
                ) for field in ("status", "priority")],
                parameters=parameters if host else [],
                input_schema={"type": "object", "properties": {"key": {"type": "string"}},
                              "required": ["key"]} if host else {},
            )]))
    return router, health


def _compile(router, concepts, *, source=None, rank=None):
    catalog = NativeConceptCatalog(concepts=tuple(concepts))
    session = router.prepare_field_routing(catalog=catalog)
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="case.lookup", required_concept_ids=tuple(c.concept_id for c in concepts),
    ),))
    return session.compile_understood(
        PaperUnderstanding(intent_id="case.lookup", source_type=source),
        principal=ACTOR, intent_registry=intents,
        rank_policy=rank(session) if rank else None,
    )


def test_neutral_meaning_retains_other_original_providers_after_a_becomes_unavailable():
    router, health = _providers()
    health["a"] = False
    plan = _compile(router, (_concept("status"),))
    assert plan.status == "ready"
    assert {call.route_id for call in plan.calls} == {"b.read", "c.read"}
    assert {call.source_type for call in plan.calls} == {"provider-b", "provider-c"}
    assert {call.license for call in plan.calls} == {"license-b", "license-c"}
    narrowed = _compile(router, (_concept("status"),), source="provider-b")
    assert narrowed.status == "ready" and [c.route_id for c in narrowed.calls] == ["b.read"]


def test_compatible_neutral_and_explicit_groups_use_one_complete_original_endpoint():
    router, _ = _providers()
    plan = _compile(router, (_concept("status"),
                             _concept("priority", source="provider-b", license="license-b")))
    assert plan.status == "ready" and plan.coverage.complete
    assert [c.route_id for c in plan.calls] == ["b.read"]
    assert plan.calls[0].call.fields == ["status", "priority"]
    assert all("None" not in qualifier for requirement in plan.coverage.required
               for qualifier in requirement.qualifiers)


def test_conflicting_explicit_groups_keep_independent_original_source_proofs():
    router, _ = _providers()
    plan = _compile(router, (_concept("status", source="provider-a"),
                             _concept("priority", source="provider-b")))
    assert plan.status == "ready" and plan.coverage.complete
    assert {c.route_id for c in plan.calls} == {"a.read", "b.read"}


def test_neutral_group_coverage_omits_unspecified_source_qualifiers():
    router, _ = _providers(count=1)
    plan = _compile(router, (_concept("status"), _concept("priority")))
    assert plan.status == "ready" and plan.coverage.complete
    assert all(not qualifier.startswith(("source_type=", "license="))
               for item in plan.coverage.required for qualifier in item.qualifiers)


def test_neutral_host_approved_root_still_requires_original_inputs_and_metadata():
    router, _ = _providers(count=1, host=True)
    session = router.prepare_field_routing(catalog=NativeConceptCatalog(concepts=(
        _concept("status"),
    )), approved_host_roots=frozenset({"a.read"}))
    plan = session.compile("case status", principal=ACTOR,
                           host_source_arguments={"a.read": {"key": "host"}})
    assert plan.status == "ready" and plan.calls[0].call.arguments == {"key": "host"}


@pytest.mark.parametrize("hops", (1, 2))
def test_neutral_graph_keeps_typed_original_identifier_producers(hops):
    from test_paper_understood_graph_plan import CATALOG, INTENTS
    from test_paper_understood_observed_graph_a9_e0 import _fixture

    router, _, _ = _fixture(hops=hops)
    neutral = NativeConceptCatalog(concepts=tuple(c.model_copy(update={
        "source_type": None, "license": None,
    }) for c in CATALOG.concepts))
    session = router.prepare_field_routing(catalog=neutral)
    plan = session.compile_understood(PaperUnderstanding(
        intent_id="case.lookup", named_tools=("target_0",),
    ), principal=ACTOR, intent_registry=INTENTS)
    assert plan.status == "requires_observation" and len(plan.bindings) == hops
    assert all(c.call.tool_fingerprint and c.call.schema_fingerprint for c in plan.calls)


def test_neutral_discovery_keeps_k5_rank_and_live_scope_boundaries():
    router, _ = _providers(count=6)
    plan = _compile(router, (_concept("status"),))
    assert plan.status == "over_k_unranked" and plan.calls == ()
    ranked = _compile(router, (_concept("status"),), rank=lambda session: PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id, route_priorities={"f.read": 100},
    ))
    assert len(ranked.calls) == 5 and ranked.calls[0].route_id == "f.read"
    router.authorization_policy = AuthorizationPolicy(default_effect="allow", data_rules=(
        DataScopeRule(operation="a.read", roles_any=("reader",), hidden_fields=("status",)),
    ))
    scoped = _compile(router, (_concept("status"),))
    assert scoped.status == "ready" and "a.read" not in {c.route_id for c in scoped.calls}


def test_neutral_plan_rejects_original_metadata_mutation():
    router, _ = _providers(count=1)
    session = router.prepare_field_routing(catalog=NativeConceptCatalog(concepts=(
        _concept("status"),
    )))
    changed = router.registry.get("a")
    changed.license = "replaced"
    router.add_tool(changed, replace=True)
    with pytest.raises(PolicyViolationError):
        session.compile("case status", principal=ACTOR)


def test_neutral_plan_rejects_inplace_policy_mutation_during_source_health_check():
    router, _ = _providers(count=1)

    def mutate(_tool, _endpoint):
        router.authorization_policy.rules[0].roles_any = ("different",)
        return True

    router.planner.availability_predicate = mutate
    with pytest.raises(PolicyViolationError):
        _compile(router, (_concept("status"),))


def test_neutral_owner_does_not_invent_missing_original_source_metadata():
    router, health = _providers(count=1)
    health["missing"] = True
    router.add_tool(ToolSpec(name="missing", endpoints=[EndpointSpec(
        name="read", read_only=True, output_fields=[FieldSpec(
            name="status", semantic_id="case.status", json_schema={"type": "string"},
        )],
    )]))
    plan = _compile(router, (_concept("status"),))
    assert [c.route_id for c in plan.calls] == ["a.read"]

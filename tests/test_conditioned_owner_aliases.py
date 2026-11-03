"""Only explicit owner conditions distinguish whole, shared concept aliases."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperUnderstanding,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.concept_retrieval import resolve_native_concepts
from schemarouter.paper_query_needs import PaperQueryNeed, _resolve_query_need


def _field(*, unit=None, **qualifiers):
    return CapabilityFieldContract(
        semantic_id="account.login", json_schema={"type": "string"},
        unit=unit, qualifiers=qualifiers,
    )


def _concept(cid, *fields, source="crm"):
    return NativeDeclaredConcept(
        concept_id=cid, aliases=(cid.replace(".", " "), "login"),
        source_type=source, license="reviewed", required_fields=fields or (_field(),),
    )


def _roles():
    return NativeConceptCatalog(concepts=(
        _concept("account.author", _field(role="author")),
        _concept("account.reviewer", _field(role="reviewer")),
    ))


def test_owner_roles_resolve_only_with_an_explicit_qualifier():
    catalog = _roles()
    for role in ("author", "reviewer"):
        assert _resolve_query_need(PaperQueryNeed(
            concept="LOGIN", qualifiers={"role": role},
        ), catalog) == (f"account.{role}", False)
    assert _resolve_query_need(PaperQueryNeed(concept="login"), catalog) == (None, True)
    assert _resolve_query_need(PaperQueryNeed(
        concept="login", qualifiers={"role": "moderator"},
    ), catalog) == (None, False)
    assert _resolve_query_need(PaperQueryNeed(
        concept="login and email", qualifiers={"role": "author"},
    ), catalog) == (None, False)
    with pytest.raises(ValueError, match="ambiguous overlapping"):
        resolve_native_concepts("login", catalog=catalog)


@pytest.mark.parametrize("conditions,global_source,expected", (
    ({"source_type": "primary"}, None, "account.first"),
    ({}, "secondary", "account.second"),
    ({"source_type": "secondary"}, "primary", None),
    ({"source_type": "Primary"}, None, None),
))
def test_only_explicit_exact_source_constraints_narrow_candidates(
    conditions, global_source, expected,
):
    catalog = NativeConceptCatalog(concepts=(
        _concept("account.first", source="primary"),
        _concept("account.second", source="secondary"),
    ))
    assert _resolve_query_need(PaperQueryNeed(concept="login", **conditions), catalog,
                               global_source_type=global_source) == (expected, False)
    assert _resolve_query_need(PaperQueryNeed(concept="login"), catalog) == (None, True)


def test_declared_units_distinguish_candidates_without_inferred_conversion():
    catalog = NativeConceptCatalog(concepts=(
        _concept("account.first", _field(unit="K")),
        _concept("account.second", _field(unit="Cel")),
    ))
    assert _resolve_query_need(PaperQueryNeed(concept="login", unit="K"), catalog) == (
        "account.first", False,
    )
    assert _resolve_query_need(PaperQueryNeed(concept="login", unit="Celsius"), catalog) == (
        None, False,
    )
    assert _resolve_query_need(PaperQueryNeed(concept="login"), catalog) == (None, True)


def test_multiple_candidates_satisfying_the_supplied_condition_remain_ambiguous():
    catalog = NativeConceptCatalog(concepts=(
        _concept("account.first", _field(unit="K", role="author")),
        _concept("account.second", _field(unit="Cel", role="author")),
    ))
    assert _resolve_query_need(PaperQueryNeed(
        concept="login", qualifiers={"role": "author"},
    ), catalog) == (None, True)


def test_unit_and_qualifiers_cannot_be_joined_across_different_owner_fields():
    split = _concept("account.split", _field(unit="K", role="current"),
                     CapabilityFieldContract(
                         semantic_id="account.other", json_schema={"type": "string"},
                         unit="Cel", qualifiers={"role": "forecast"},
                     ), source="primary")
    catalog = NativeConceptCatalog(concepts=(split, _concept(
        "account.together", _field(unit="K", role="forecast"), source="secondary",
    )))
    need = PaperQueryNeed(concept="login", unit="K", qualifiers={"role": "forecast"})
    assert _resolve_query_need(need, catalog) == ("account.together", False)
    assert _resolve_query_need(need, catalog, global_source_type="primary") == (None, False)


@pytest.mark.parametrize("first,second", (
    (_field(), _field()),
    (_field(role="author"), _field()),
    (_field(role="author"), _field(role="author")),
))
def test_shared_alias_without_explicit_owner_distinction_is_still_invalid(first, second):
    with pytest.raises(ValidationError, match="ambiguous owner-declared concept alias"):
        NativeConceptCatalog(concepts=(
            _concept("account.first", first), _concept("account.second", second),
        ))


def test_every_owner_field_pair_needs_a_declared_distinction():
    with pytest.raises(ValidationError, match="ambiguous owner-declared concept alias"):
        NativeConceptCatalog(concepts=(
            _concept("account.first", _field(role="author"), CapabilityFieldContract(
                semantic_id="account.other", json_schema={"type": "string"},
            )),
            _concept("account.second", _field(role="reviewer")),
        ))


def test_reused_aliases_still_count_toward_the_original_total_budget():
    with pytest.raises(ValidationError, match="too many declared concept aliases"):
        NativeConceptCatalog(concepts=tuple(
            _concept(f"account.c{i}", source=f"source{i}").model_copy(update={
                "aliases": tuple(f"shared{number}" for number in range(16)),
            }) for i in range(9)
        ))


def test_resolved_owner_role_reuses_public_field_proof_and_live_acl():
    catalog = _roles()
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="author.read", roles_any=("reader",),
        ),),
    ))
    for role in ("author", "reviewer"):
        router.add_tool(ToolSpec(name=role, source_type="crm", license="reviewed", endpoints=[
            EndpointSpec(name="read", read_only=True, output_fields=[FieldSpec(
                name="login", semantic_id="account.login", qualifiers={"role": role},
                json_schema={"type": "string"}, path=[role, "login"],
            )]),
        ]))
    session = router.prepare_field_routing(catalog=catalog)
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="lookup", required_concept_ids=(),
    ),))
    principal = PrincipalContext(subject="alias-test", roles=("reader",))
    assert _resolve_query_need(PaperQueryNeed(concept="login"), catalog) == (None, True)
    for role in ("author", "reviewer"):
        cid, ambiguous = _resolve_query_need(PaperQueryNeed(
            concept="login", qualifiers={"role": role},
        ), catalog)
        assert cid is not None and not ambiguous
        plan = session.compile_understood(
            PaperUnderstanding(intent_id="lookup", concept_ids=(cid,)),
            principal=principal, intent_registry=intents,
        )
        assert plan.status == ("ready" if role == "author" else "no_proven_hit")
        assert [call.route_id for call in plan.calls] == (
            ["author.read"] if role == "author" else []
        )
        if plan.calls:
            assert plan.calls[0].fields_meta[0].source_path == ("author", "login")

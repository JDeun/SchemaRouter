"""Synthetic E1: complete required field group before strict K5; no agent."""
from __future__ import annotations

import json

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.capability_contracts import CapabilityFieldContract
from scripts.research_required_field_group_e1 import (
    DeclaredFieldGroupAnalyzer,
    DeclaredRequiredFieldGroup,
    retrieve_required_field_group_e1,
)

ANALYST = PrincipalContext(subject="synthetic-analyst", roles=("analyst",))
VIEWER = PrincipalContext(subject="synthetic-viewer", roles=("viewer",))
GROUP = DeclaredRequiredFieldGroup(
    aliases=("탄성계수와 인장강도", "ヤング率と引張強さ", "Young modulus tensile strength"),
    required_fields=(
        CapabilityFieldContract(
            semantic_id="mechanics.elastic_modulus",
            json_schema={"type": "number"}, unit="GPa",
            qualifiers={"temperature": "room"},
        ),
        CapabilityFieldContract(
            semantic_id="mechanics.tensile_strength",
            json_schema={"type": "number"}, unit="MPa",
            qualifiers={"temperature": "room"},
        ),
    ),
    source_type="materials_data",
    license="CC-BY-4.0",
)


def _field(name: str, semantic: str, unit: str) -> FieldSpec:
    return FieldSpec(
        name=name, semantic_id=semantic, unit=unit,
        qualifiers={"temperature": "room"},
        json_schema={"type": "number"},
    )


A = _field("elastic_measurement", "mechanics.elastic_modulus", "GPa")
B = _field("tensile_measurement", "mechanics.tensile_strength", "MPa")


def _router() -> SchemaRouter:
    policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(
            AuthorizationRule(
                effect="deny", operation="private.read", roles_any=("analyst", "viewer"),
            ),
            AuthorizationRule(
                effect="allow", operation="*.read", roles_any=("analyst", "viewer"),
            ),
        ),
        data_rules=(
            DataScopeRule(
                operation="complete.read", roles_any=("viewer",),
                hidden_fields=("tensile_measurement",),
            ),
        ),
    )
    router = SchemaRouter(
        analyzer=DeclaredFieldGroupAnalyzer(GROUP),
        authorization_policy=policy,
    )
    tools = (
        ("partial_a", [A], "materials_data", "CC-BY-4.0"),
        ("partial_b", [B], "materials_data", "CC-BY-4.0"),
        ("complete", [A, B], "materials_data", "CC-BY-4.0"),
        ("wrong_unit", [A, _field("bad_b", "mechanics.tensile_strength", "GPa")],
         "materials_data", "CC-BY-4.0"),
        ("wrong_type", [A, B.model_copy(update={
            "name": "wrong_type_value", "json_schema": {"type": "string"},
            "unit": None,
        })], "materials_data", "CC-BY-4.0"),
        ("wrong_qualifier", [A, B.model_copy(update={
            "name": "wrong_qualifier_value", "qualifiers": {"temperature": "cold"},
        })], "materials_data", "CC-BY-4.0"),
        ("missing_unit", [A, B.model_copy(update={
            "name": "missing_unit_value", "unit": None,
        })], "materials_data", "CC-BY-4.0"),
        ("wrong_source", [A, B], "incompatible_data", "CC-BY-4.0"),
        ("wrong_license", [A, B], "materials_data", "proprietary"),
        ("private", [A, B], "materials_data", "CC-BY-4.0"),
    )
    for name, fields, source, license_id in tools:
        router.add_tool(ToolSpec(
            name=name, description="Scientific registered property source",
            source_type=source, license=license_id,
            endpoints=[EndpointSpec(
                name="read", read_only=True, description="Read measured values",
                output_fields=fields,
            )],
        ))
    return router


@pytest.mark.parametrize("query", GROUP.aliases)
def test_group_pre_k_only_exposes_complete_compatible_authorized_tool(query: str) -> None:
    router = _router()
    original = router.retrieve_authorized(query, principal=ANALYST, k=5)
    # The baseline can rank field-incomplete contracts whose names/IDs
    # match even though type, unit or evidence requirements are wrong.
    assert any(
        c.route_id in {
            "wrong_unit.read", "wrong_type.read",
            "wrong_qualifier.read", "missing_unit.read",
        }
        for c in original.candidates
    )
    assert all(c.route_id != "private.read" for c in original.candidates)

    result = retrieve_required_field_group_e1(
        router, query, principal=ANALYST, group=GROUP,
    )
    assert result.requested_k == 5
    assert result.total_ranked == 1
    assert [c.route_id for c in result.candidates] == ["complete.read"]
    assert {f.semantic_id for f in result.candidates[0].output_fields} == {
        field.semantic_id for field in GROUP.required_fields
    }
    assert result.candidates[0].source_type == "materials_data"
    assert result.candidates[0].license == "CC-BY-4.0"
    assert result.candidates[0].tool_fingerprint
    assert result.candidates[0].endpoint_fingerprint


def test_two_partial_sources_do_not_form_a_proven_full_endpoint() -> None:
    """An arbitrary union of A-only and B-only tool contracts is not a join."""
    router = SchemaRouter(
        analyzer=DeclaredFieldGroupAnalyzer(GROUP),
        authorization_policy=AuthorizationPolicy(default_effect="allow"),
    )
    for name, item in (("partial_a", A), ("partial_b", B)):
        router.add_tool(ToolSpec(
            name=name, source_type="materials_data", license="CC-BY-4.0",
            endpoints=[EndpointSpec(
                name="read", read_only=True, output_fields=[item],
            )],
        ))
    baseline = router.retrieve_authorized(
        GROUP.aliases[0], principal=ANALYST, k=5,
    )
    assert {c.route_id for c in baseline.candidates} == {
        "partial_a.read", "partial_b.read",
    }
    gated = retrieve_required_field_group_e1(
        router, GROUP.aliases[0], principal=ANALYST, group=GROUP,
    )
    assert gated.candidates == []
    assert gated.total_ranked == 0


def test_hidden_member_of_required_group_is_not_satisfied_by_public_alias() -> None:
    router = _router()
    result = retrieve_required_field_group_e1(
        router, GROUP.aliases[0], principal=VIEWER, group=GROUP,
    )
    assert result.candidates == []
    assert result.total_ranked == 0
    assert result.requested_k == 5
    encoded = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    assert "private.read" not in encoded
    assert "tensile_measurement" not in encoded


def test_group_rejection_never_fills_k_with_partial_or_wrong_contract() -> None:
    result = retrieve_required_field_group_e1(
        _router(), GROUP.aliases[1], principal=ANALYST, group=GROUP,
    )
    routes = {c.route_id for c in result.candidates}
    assert not routes.intersection({
        "partial_a.read", "partial_b.read", "wrong_unit.read",
        "wrong_type.read", "wrong_qualifier.read", "missing_unit.read",
        "wrong_source.read", "wrong_license.read", "private.read",
    })


def test_group_query_must_be_declared_exactly_and_k_remain_five() -> None:
    router = _router()
    for query in ("탄성계수", "elastic and tensile unknown extra"):
        with pytest.raises(ValueError, match="no declared FieldGroup"):
            retrieve_required_field_group_e1(
                router, query, principal=ANALYST, group=GROUP,
            )
    for k in (1, 6, True, 5.0):
        with pytest.raises(ValueError, match="exactly fixed K5"):
            retrieve_required_field_group_e1(
                router, GROUP.aliases[0], principal=ANALYST, group=GROUP, k=k,
            )


def test_group_never_plans_or_executes(monkeypatch: pytest.MonkeyPatch) -> None:
    router = _router()

    def forbidden(*_args, **_kwargs):
        raise AssertionError("graph candidate retrieval is not agent execution")

    monkeypatch.setattr(router, "plan", forbidden)
    monkeypatch.setattr(router, "execute", forbidden)
    assert retrieve_required_field_group_e1(
        router, GROUP.aliases[2], principal=ANALYST, group=GROUP,
    ).candidates


def test_group_source_identity_changes_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    router = _router()
    original = router._project_retrieval_data_scope

    def drift(result, principal):
        response = original(result, principal)
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return response

    monkeypatch.setattr(router, "_project_retrieval_data_scope", drift)
    from schemarouter.errors import PolicyViolationError
    with pytest.raises(PolicyViolationError, match="retrieval authority changed"):
        retrieve_required_field_group_e1(
            router, GROUP.aliases[0], principal=ANALYST, group=GROUP,
        )


def test_invalid_groups_are_not_silent_partial_requirements() -> None:
    with pytest.raises(ValueError, match="invalid bounded declared FieldGroup"):
        DeclaredRequiredFieldGroup(aliases=("same", "same"), required_fields=GROUP.required_fields)
    with pytest.raises(ValueError, match="invalid bounded declared FieldGroup"):
        DeclaredRequiredFieldGroup(aliases=("a",), required_fields=(GROUP.required_fields[0],) * 2)
    with pytest.raises(ValueError, match="invalid bounded declared FieldGroup"):
        DeclaredRequiredFieldGroup(aliases=(), required_fields=GROUP.required_fields)

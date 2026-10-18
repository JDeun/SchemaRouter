"""Declared concept composition into the existing authorized pre-K field search."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.concept_retrieval import (
    NativeConceptCatalog,
    NativeDeclaredConcept,
    resolve_native_concepts,
    retrieve_authorized_concepts,
)

ANALYST = PrincipalContext(subject="analyst", roles=("analyst",))
VIEWER = PrincipalContext(subject="viewer", roles=("viewer",))


def _contract(sid: str, *, kind: str = "string", unit: str | None = None):
    return CapabilityFieldContract(
        semantic_id=sid, json_schema={"type": kind}, unit=unit,
    )


STATUS = NativeDeclaredConcept(
    concept_id="support.status",
    aliases=("case status", "status", "문의 상태", "問い合わせ状態"),
    required_fields=(_contract("support.status"),),
    source_type="support", license="reviewed",
)
PRIORITY = NativeDeclaredConcept(
    concept_id="support.priority",
    aliases=("priority", "우선순위", "優先度"),
    required_fields=(_contract("support.priority"),),
    source_type="support", license="reviewed",
)
CATALOG = NativeConceptCatalog(concepts=(STATUS, PRIORITY))
QUERIES = (
    "Please check case status and priority",
    "문의 상태와 우선순위를 조회",
    "問い合わせ状態と優先度を教えて",
)


def _field(sid: str, name: str | None = None, *, kind: str = "string") -> FieldSpec:
    return FieldSpec(
        name=name or sid.split(".")[-1], semantic_id=sid,
        json_schema={"type": kind},
    )


def _router(*, extra_noise: int = 0) -> SchemaRouter:
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.read", roles_any=("analyst", "viewer"),
        ),),
        data_rules=(DataScopeRule(
            operation="complete.read", roles_any=("viewer",),
            hidden_fields=("priority",),
        ),),
    ))
    for name, output in (
        ("complete", [_field("support.status"), _field("support.priority")]),
        ("status_only", [_field("support.status")]),
        ("priority_only", [_field("support.priority")]),
        ("wrong_type", [_field("support.status"),
                        _field("support.priority", kind="integer")]),
    ):
        router.add_tool(ToolSpec(
            name=name, source_type="support", license="reviewed",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                description="case status priority", output_fields=output,
            )],
        ))
    for idx in range(extra_noise):
        router.add_tool(ToolSpec(
            name=f"partial_{idx}", source_type="support", license="reviewed",
            endpoints=[EndpointSpec(
                name="read", read_only=True, description="case status priority",
                output_fields=[_field("support.status")],
            )],
        ))
    return router


@pytest.mark.parametrize("query", QUERIES)
def test_declared_mentions_combine_into_complete_authorized_topk(query):
    router = _router()
    original = router.retrieve_authorized(query, principal=ANALYST, k=5)
    resolved = resolve_native_concepts(query, catalog=CATALOG)
    assert resolved.concept_ids == ("support.priority", "support.status")
    assert {f.semantic_id for f in resolved.field_group.required_fields} == {
        "support.priority", "support.status",
    }
    result = retrieve_authorized_concepts(
        router, query, principal=ANALYST, catalog=CATALOG,
    )
    assert result.requested_k == 5
    assert result.total_ranked == 1
    assert [c.route_id for c in result.candidates] == ["complete.read"]
    assert all(c.tool_fingerprint and c.endpoint_fingerprint
               for c in result.candidates)
    # No shadow ranker, no default opt-in, no semantic router permission grant.
    assert router.retrieve_authorized(query, principal=ANALYST, k=5) == original


def test_existing_pre_k_gate_survives_many_lexically_matching_partial_routes():
    router = _router(extra_noise=120)
    result = retrieve_authorized_concepts(
        router, QUERIES[0], principal=ANALYST, catalog=CATALOG,
    )
    assert [c.route_id for c in result.candidates] == ["complete.read"]
    assert result.total_ranked == 1


def test_data_scope_does_not_reconstruct_a_hidden_required_field():
    result = retrieve_authorized_concepts(
        _router(), QUERIES[1], principal=VIEWER, catalog=CATALOG,
    )
    assert result.candidates == []
    assert result.total_ranked == 0


def test_ascii_word_boundaries_and_unknown_queries_reject():
    for query in ("metastatus", "prepriority", "weather forecast"):
        with pytest.raises(ValueError, match="no declared concept"):
            resolve_native_concepts(query, catalog=CATALOG)
    # Scope or negation is NOT understood. Exact lexeme matches are not
    # evidence of the user's positive intent; this E1 is not a classifier.


def test_same_concept_overlapping_aliases_are_not_double_counted():
    result = resolve_native_concepts("case status", catalog=CATALOG)
    assert result.concept_ids == ("support.status",)
    assert len(result.field_group.required_fields) == 1


def test_different_concepts_with_overlapping_spans_abstain():
    bad = NativeConceptCatalog(concepts=(
        STATUS,
        NativeDeclaredConcept(
            concept_id="another.state",
            aliases=("case status report",),
            required_fields=(_contract("another.state"),),
            source_type="support", license="reviewed",
        ),
    ))
    with pytest.raises(ValueError, match="ambiguous overlapping"):
        resolve_native_concepts("case status report", catalog=bad)


def test_canonical_alias_collision_is_rejected_before_runtime():
    with pytest.raises(ValueError, match="ambiguous owner-declared"):
        NativeConceptCatalog(concepts=(
            STATUS,
            NativeDeclaredConcept(
                concept_id="other", aliases=("STATUS",),
                required_fields=(_contract("other"),),
            ),
        ))


def test_conflicting_type_or_source_rules_never_become_a_union():
    conflict = NativeConceptCatalog(concepts=(
        STATUS,
        NativeDeclaredConcept(
            concept_id="other.type", aliases=("conflicting type",),
            required_fields=(_contract("support.status", kind="integer"),),
            source_type="support", license="reviewed",
        ),
    ))
    with pytest.raises(ValueError, match="conflicting typed requirements"):
        resolve_native_concepts("status and conflicting type", catalog=conflict)

    bad_source = NativeConceptCatalog(concepts=(
        STATUS,
        NativeDeclaredConcept(
            concept_id="other.source", aliases=("different source",),
            required_fields=(_contract("other.source"),),
            source_type="elsewhere", license="reviewed",
        ),
    ))
    with pytest.raises(ValueError, match="incompatible source policy"):
        resolve_native_concepts("status different source", catalog=bad_source)


def test_source_schema_mismatch_and_extra_required_units_cannot_grant_a_result():
    support = NativeConceptCatalog(concepts=(
        NativeDeclaredConcept(
            concept_id="science.pressure",
            aliases=("vapor pressure",),
            required_fields=(_contract("science.pressure", kind="number", unit="kPa"),),
            source_type="science", license="reviewed",
        ),
    ))
    router = _router()
    assert retrieve_authorized_concepts(
        router, "show vapor pressure", principal=ANALYST, catalog=support,
    ).candidates == []


def test_modified_approved_declaration_is_revalidated_before_lookup():
    catalog = CATALOG.model_copy(deep=True)
    # Simulate a corrupted/mutable document bypassing Pydantic assignment.
    object.__setattr__(catalog.concepts[0], "aliases", ("",))
    with pytest.raises(ValueError, match="trusted concept catalog has changed"):
        resolve_native_concepts(QUERIES[0], catalog=catalog)


def test_deny_invalid_k_and_no_agent_execution(monkeypatch):
    router = _router()
    monkeypatch.setattr(
        router, "plan", lambda *_a, **_kw: pytest.fail("no planning"),
    )
    monkeypatch.setattr(
        router, "execute", lambda *_a, **_kw: pytest.fail("no execution"),
    )
    assert retrieve_authorized_concepts(
        router, QUERIES[0], principal=ANALYST, catalog=CATALOG,
    ).candidates
    with pytest.raises(ValueError, match="exactly K5"):
        retrieve_authorized_concepts(
            router, QUERIES[0], principal=ANALYST, catalog=CATALOG, k=6,
        )


def test_determinism_across_catalog_order_and_unicode():
    other = NativeConceptCatalog(concepts=(PRIORITY, STATUS))
    assert resolve_native_concepts(QUERIES[0], catalog=CATALOG) == (
        resolve_native_concepts(QUERIES[0], catalog=other)
    )
    assert resolve_native_concepts(
        "문의 상태와 우선순위를 조회", catalog=CATALOG,
    ).concept_ids == ("support.priority", "support.status")

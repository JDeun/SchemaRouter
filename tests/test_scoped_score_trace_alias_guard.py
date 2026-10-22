"""#1532: scoped score traces must not replay source aliases (scripted E0)."""
from __future__ import annotations

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
from schemarouter.models import ParameterSpec, ScoreComponent

SECRET_ALIAS = "unreviewed_private_field_name_p614"
VIEWER = PrincipalContext(subject="viewer", roles=("viewer",))


def _router() -> SchemaRouter:
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="records.read", roles_any=("viewer",),
        ),),
        data_rules=(DataScopeRule(
            operation="records.read", roles_any=("viewer",),
            visible_fields=("public_value",),
        ),),
    ))
    router.add_tool(ToolSpec(
        name="records",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            parameters=[
                ParameterSpec(
                    name="public_query", required=False,
                    json_schema={"type": "string"},
                ),
            ],
            output_fields=[
                FieldSpec(
                    name="public_value", semantic_id="public.value",
                    aliases=[SECRET_ALIAS], json_schema={"type": "string"},
                ),
                FieldSpec(name="private_value", json_schema={"type": "string"}),
            ],
        )],
    ))
    return router


def _injected_components() -> list[ScoreComponent]:
    return [
        ScoreComponent(kind="field_lexical", value=3.0, matched=SECRET_ALIAS),
        ScoreComponent(
            kind="field_qualifier", value=4.0,
            matched=f"public_value:{SECRET_ALIAS}",
        ),
        ScoreComponent(kind="tool_token", value=1.5, matched=SECRET_ALIAS),
        ScoreComponent(
            kind="tool_token", value=1.5,
            matched="source_description_secret_not_declared_in_aliases",
        ),
        ScoreComponent(
            kind="argument_match", value=2.0,
            matched="not_a_public_parameter_name",
        ),
        ScoreComponent(
            kind="argument_alias_match", value=2.0,
            matched=f"{SECRET_ALIAS}->public_query",
        ),
        # Stale structural explanations and arbitrary future kinds must fail closed.
        ScoreComponent(kind="experimental_debug_secret", value=9.0,
                       matched="unreviewed_kind_secret"),
        ScoreComponent(kind="preferred_tool", value=100.0,
                       matched="not_a_public_tool"),
        ScoreComponent(kind="preferred_endpoint", value=250.0,
                       matched="not_a_public_endpoint"),
        ScoreComponent(kind="tool_identifier", value=12.0,
                       matched="not_a_public_tool_identifier"),
        ScoreComponent(kind="endpoint_identifier", value=12.0,
                       matched="not_a_public_endpoint_identifier"),
        ScoreComponent(kind="operation_family", value=8.0,
                       matched="not_a_public_operation"),
        ScoreComponent(kind="field_exact", value=6.0, matched="public_value"),
        ScoreComponent(kind="tool_token", value=1.5, matched="records"),
        ScoreComponent(kind="tool_token", value=1.5, matched="read"),
        ScoreComponent(kind="argument_match", value=2.0, matched="public_query"),
        ScoreComponent(kind="preferred_tool", value=100.0, matched="records"),
        ScoreComponent(kind="preferred_endpoint", value=250.0,
                       matched="records.read"),
        ScoreComponent(kind="tool_identifier", value=12.0, matched="records"),
        ScoreComponent(kind="operation_family", value=8.0, matched="read"),
    ]


def _assert_safe(candidate) -> None:
    assert candidate.matched_fields == ["public_value"]
    assert [
        (item.kind, item.matched) for item in candidate.score_components
    ] == [
        ("field_exact", "public_value"),
        ("tool_token", "records"),
        ("tool_token", "read"),
        ("argument_match", "public_query"),
        ("preferred_tool", "records"),
        ("preferred_endpoint", "records.read"),
        ("tool_identifier", "records"),
        ("operation_family", "read"),
    ]
    assert SECRET_ALIAS not in candidate.model_dump_json()
    assert "source_description_secret_not_declared_in_aliases" not in (
        candidate.model_dump_json()
    )
    assert "not_a_public_parameter_name" not in candidate.model_dump_json()
    for canary in (
        "unreviewed_kind_secret",
        "not_a_public_tool",
        "not_a_public_endpoint",
        "not_a_public_tool_identifier",
        "not_a_public_endpoint_identifier",
        "not_a_public_operation",
        "experimental_debug_secret",
    ):
        assert canary not in candidate.model_dump_json()


def test_full_candidate_scope_removes_source_alias_match_traces():
    router = _router()
    ranked = router.retrieve_authorized("public_value", principal=VIEWER, k=5)
    assert len(ranked.candidates) == 1
    injected = ranked.candidates[0].model_copy(deep=True, update={
        "matched_fields": [SECRET_ALIAS, "public_value"],
        "score_components": _injected_components(),
    })
    decorated = ranked.model_copy(deep=True, update={"candidates": [injected]})
    sanitized = router._project_retrieval_data_scope(decorated, VIEWER)
    _assert_safe(sanitized.candidates[0])
    assert sanitized.total_ranked == ranked.total_ranked
    assert sanitized.candidates[0].route_id == ranked.candidates[0].route_id


def test_route_only_candidate_scope_has_identical_alias_guard():
    router = _router()
    ranked = router.retrieve_routes_authorized(
        "public_value", principal=VIEWER, k=5,
    )
    assert len(ranked.candidates) == 1
    injected = ranked.candidates[0].model_copy(deep=True, update={
        "matched_fields": [SECRET_ALIAS, "public_value"],
        "score_components": _injected_components(),
    })
    decorated = ranked.model_copy(deep=True, update={"candidates": [injected]})
    sanitized = router._project_route_retrieval_data_scope(decorated, VIEWER)
    _assert_safe(sanitized.candidates[0])
    assert sanitized.total_ranked == ranked.total_ranked
    assert sanitized.candidates[0].route_id == ranked.candidates[0].route_id


def test_original_authority_and_normal_ranking_preserve_canonical_identity():
    router = _router()
    tool = router.registry.get("records")
    source = tool.endpoint("read")
    assert source.output_fields[0].aliases == [SECRET_ALIAS]
    for retrieval in (
        router.retrieve_authorized("public_value", principal=VIEWER),
        router.retrieve_routes_authorized("public_value", principal=VIEWER),
    ):
        assert len(retrieval.candidates) == 1
        candidate = retrieval.candidates[0]
        assert candidate.route_id == "records.read"
        assert candidate.score > 0
        assert SECRET_ALIAS not in retrieval.model_dump_json()
        assert candidate.tool_fingerprint == tool.fingerprint
        assert candidate.endpoint_fingerprint == source.fingerprint


def test_authorized_score_trace_includes_only_public_native_endpoint_name():
    router = _router()
    retrieval = router.retrieve_authorized("read", principal=VIEWER, k=1)
    assert len(retrieval.candidates) == 1
    assert ("endpoint_identifier", "read") in [
        (component.kind, component.matched)
        for component in retrieval.candidates[0].score_components
    ]
    assert SECRET_ALIAS not in retrieval.model_dump_json()

"""#1532 E0: restricted tool descriptions must not affect candidate score.

Local paired source variation only; not a semantic model or external E2 test.
"""
from __future__ import annotations

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    PlanRequest,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.models import QueryIntent

CANARY = "private_score_canary_t3397"
VIEWER = PrincipalContext(subject="viewer", roles=("viewer",))


def _router(*, description: str, scoped: bool) -> SchemaRouter:
    policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="records.read", roles_any=("viewer",),
        ),),
        data_rules=(DataScopeRule(
            operation="records.read", roles_any=("viewer",),
            visible_fields=("public_value",),
        ),) if scoped else (),
    )
    router = SchemaRouter(authorization_policy=policy)
    router.add_tool(ToolSpec(
        name="records",
        description=description,
        endpoints=[EndpointSpec(
            name="read",
            description="Read public data",
            read_only=True,
            output_fields=[
                FieldSpec(name="public_value", json_schema={"type": "string"}),
                FieldSpec(name="private_value", json_schema={"type": "string"}),
            ],
        )],
    ))
    return router


def test_scoped_ranking_never_changes_with_source_private_tool_description():
    base = _router(description="", scoped=True)
    tainted = _router(description=f"secret description {CANARY}", scoped=True)
    for query in (CANARY, "public_value"):
        original = base.retrieve_authorized(query, principal=VIEWER, k=5)
        altered = tainted.retrieve_authorized(query, principal=VIEWER, k=5)
        assert len(original.candidates) == len(altered.candidates) == 1
        left, right = original.candidates[0], altered.candidates[0]
        assert left.rank == right.rank == 1
        assert left.route_id == right.route_id == "records.read"
        assert left.score == right.score
        assert left.score_components == right.score_components
        assert left.matched_fields == right.matched_fields
        assert left.tool_description == right.tool_description == ""
        # Source fingerprint changes when the SOURCE description changes,
        # and must continue to attest each distinct original contract.
        assert left.tool_fingerprint != right.tool_fingerprint
        assert tainted.registry.get("records").description.endswith(CANARY)


def test_original_unscoped_keyword_ranking_remains_source_sensitive():
    baseline = _router(description="", scoped=False)
    tainted = _router(description=CANARY, scoped=False)
    a = baseline.retrieve_authorized(CANARY, principal=VIEWER)
    b = tainted.retrieve_authorized(CANARY, principal=VIEWER)
    assert len(a.candidates) == len(b.candidates) == 1
    assert b.candidates[0].score > a.candidates[0].score
    assert b.candidates[0].tool_description == CANARY


def test_optional_recall_decision_request_uses_scoped_not_raw_description():
    router = _router(description=CANARY, scoped=True)
    request = PlanRequest(query=CANARY)
    catalog = router.planner._semantic_recall_catalog(
        request,
        QueryIntent(),
        scoring_endpoint_transform=(
            lambda tool, endpoint: router._data_scope_endpoint_view(
                VIEWER, tool, endpoint,
            )
        ),
    )
    assert len(catalog) == 1
    decision = router.planner._semantic_recall_request(request, catalog)
    assert len(decision.options) == 1
    assert CANARY not in decision.options[0].description
    assert catalog[0].tool.fingerprint == router.registry.get("records").fingerprint
    assert catalog[0].tool.description == CANARY


def test_scoped_canonical_tool_identifier_still_matches_spaced_query():
    """Do not break real plan+retry authority by losing safe tool-name tokens."""
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="retry_records.read",
            roles_any=("viewer",),
        ),),
        data_rules=(DataScopeRule(
            operation="retry_records.read", roles_any=("viewer",),
            visible_fields=("value",),
        ),),
    ))
    router.add_tool(ToolSpec(
        name="retry_records",
        description=f"untrusted note {CANARY}",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            output_fields=[FieldSpec(name="value", json_schema={"type": "string"})],
        )],
    ))
    result = router.retrieve_authorized(
        "retry records", principal=VIEWER, k=5,
    )
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.route_id == "retry_records.read"
    assert candidate.score > 0
    assert candidate.tool_description == ""
    assert CANARY not in str(candidate.score_components)
    plan = router.plan_authorized("retry records", principal=VIEWER)
    assert plan.calls
    assert plan.calls[0].tool == "retry_records"

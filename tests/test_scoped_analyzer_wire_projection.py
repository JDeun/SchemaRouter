"""#1532 E0: no provider wire selectors in principal-scoped analyzer schemas.

Raw source paths are trusted execution metadata, not public field contracts.
"""
from __future__ import annotations

import json

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    PrincipalContext,
    SchemaRouter,
    ServerProjectionSpec,
    ToolSpec,
)
from schemarouter.models import AuthRequirementSet, AuthSchemeRequirement
from schemarouter.planner import KeywordAnalyzer

CANARY = "wire_private_source_xyz_2749"
AUTH_CANARY = "auth_hidden_scope_xyz_8163"
VIEWER = PrincipalContext(subject="viewer", roles=("viewer",))


def _router(*, auth_canary: bool = False):
    analyzer_tools: list[dict] = []

    class AuditingAnalyzer:
        def analyze(self, request, registry):
            analyzer_tools.extend(
                tool.model_dump(mode="json")
                for tool in registry.tools()
            )
            return KeywordAnalyzer().analyze(request, registry)

    router = SchemaRouter(
        analyzer=AuditingAnalyzer(),
        authorization_policy=AuthorizationPolicy(
            default_effect="deny",
            rules=(
                AuthorizationRule(
                    effect="allow", operation="records.read",
                    roles_any=("viewer",),
                ),
            ),
            data_rules=(
                DataScopeRule(
                    operation="records.read",
                    roles_any=("viewer",),
                    visible_fields=("public_value",),
                ),
            ),
        ),
    )
    router.add_tool(ToolSpec(
        name="records",
        endpoints=[EndpointSpec(
            name="read",
            read_only=True,
            auth_requirements=(
                [AuthRequirementSet(schemes=[AuthSchemeRequirement(
                    name=f"source_{AUTH_CANARY}",
                    kind="api_key",
                    location="header",
                    parameter_name=f"X-{AUTH_CANARY}",
                    scopes=[AUTH_CANARY],
                )])]
                if auth_canary else []
            ),
            output_fields=[
                FieldSpec(
                    name="public_value",
                    path=[CANARY],
                    result_path=["public_value"],
                    json_schema={"type": "string"},
                ),
                FieldSpec(name="private_value"),
            ],
            output_schema={
                "type": "object",
                "properties": {
                    CANARY: {"type": "string"},
                    "private_value": {"type": "string"},
                },
            },
            server_projection=ServerProjectionSpec(
                parameter="response_fields",
                field_map={"public_value": CANARY},
            ),
        )],
    ))
    return router, analyzer_tools


def test_analyzer_does_not_receive_original_wire_selector_or_hidden_name():
    router, analyzer_tools = _router()
    retrieval = router.retrieve_authorized(
        "public_value", principal=VIEWER, k=5,
    )
    assert len(retrieval.candidates) == 1
    assert [f.name for f in retrieval.candidates[0].output_fields] == [
        "public_value",
    ]
    assert analyzer_tools
    public = json.dumps(analyzer_tools, sort_keys=True)
    candidate = retrieval.model_dump_json()
    for forbidden in (CANARY, "private_value"):
        assert forbidden not in public
        assert forbidden not in candidate
    visible = analyzer_tools[0]["endpoints"][0]
    assert visible["server_projection"] is None
    assert visible["output_fields"][0]["path"] == []


def test_original_provider_wire_projection_and_authority_remain_intact():
    router, _ = _router()
    tool = router.registry.get("records")
    original = tool.endpoint("read")
    fingerprint = original.fingerprint
    assert original.server_projection is not None
    assert original.server_projection.field_map == {"public_value": CANARY}
    scoped = router._data_scope_endpoint_view(VIEWER, tool, original)
    assert scoped is not None
    assert scoped.server_projection is not None
    assert scoped.server_projection.field_map == {"public_value": CANARY}
    assert original.fingerprint == fingerprint
    assert original.output_fields[0].path == [CANARY]
    assert router.plan_authorized("public_value", principal=VIEWER).calls


def test_scoped_analyzer_drops_unreviewed_source_auth_requirement_labels():
    # Source security requirements are a trusted execution/auth contract, not
    # safe public metadata on a principal-visible, output-restricted route.
    router, analyzer_tools = _router(auth_canary=True)
    original = router.registry.get("records").endpoint("read")
    fingerprint = original.fingerprint
    assert AUTH_CANARY in original.model_dump_json()

    result = router.retrieve_authorized("public_value", principal=VIEWER, k=5)
    assert len(result.candidates) == 1
    assert analyzer_tools
    exposed = json.dumps(analyzer_tools, sort_keys=True)
    assert AUTH_CANARY not in exposed
    assert AUTH_CANARY not in result.model_dump_json()
    assert analyzer_tools[0]["endpoints"][0]["auth_requirements"] == []

    # The raw source is still available to trusted host checks and its
    # original schema fingerprint cannot be rewritten by display projection.
    assert original.fingerprint == fingerprint
    assert AUTH_CANARY in original.model_dump_json()

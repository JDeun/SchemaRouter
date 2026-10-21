"""#1532: lightweight route retrieval must honor principal data-scope E0."""
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
from schemarouter.planner import KeywordAnalyzer

CANARY = "denied_route_sidecar_27391"
VIEWER = PrincipalContext(subject="viewer", roles=("viewer",))


def _router(*, tainted: bool = True, scoped: bool = True):
    inspected: list[dict] = []

    class Analyzer:
        def analyze(self, request, registry):
            inspected.extend(tool.model_dump(mode="json") for tool in registry.tools())
            return KeywordAnalyzer().analyze(request, registry)

    raw = f"hidden_{CANARY}" if tainted else ""
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
    router = SchemaRouter(authorization_policy=policy, analyzer=Analyzer())
    router.add_tool(ToolSpec(
        name="records", description=raw,
        provider=raw or "public_provider",
        access_mode=raw or "public_access",
        source_type=raw or "public_source",
        license=raw or "public_license",
        endpoints=[EndpointSpec(
            name="read", read_only=True, description=raw,
            operation_aliases=[raw] if raw else [],
            output_fields=[
                FieldSpec(
                    name="public_value", semantic_id="public.value",
                    aliases=[raw] if raw else [],
                    json_schema={"type": "string"},
                ),
                FieldSpec(
                    name="private_value", description=raw,
                    json_schema={"type": "string"},
                ),
            ],
        )],
    ))
    return router, inspected


def test_route_only_scoped_source_labels_are_hidden():
    router, inspected = _router()
    result = router.retrieve_routes_authorized(
        "public_value", principal=VIEWER, k=5,
    )
    assert len(result.candidates) == 1
    route = result.candidates[0]
    assert route.route_id == "records.read"
    assert route.score > 0
    assert route.provider is None
    assert route.access_mode is None
    assert inspected
    assert CANARY not in json.dumps(inspected, sort_keys=True)
    assert "private_value" not in json.dumps(inspected, sort_keys=True)
    assert CANARY not in result.model_dump_json()
    original = router.registry.get("records")
    assert original.provider == f"hidden_{CANARY}"
    assert route.tool_fingerprint == original.fingerprint
    assert route.endpoint_fingerprint == original.endpoint("read").fingerprint


def test_route_only_ranking_invariant_under_hidden_source_change():
    clean, _ = _router(tainted=False)
    tainted, _ = _router()
    for query in ("public_value", CANARY):
        left = clean.retrieve_routes_authorized(
            query, principal=VIEWER, k=5,
        )
        right = tainted.retrieve_routes_authorized(
            query, principal=VIEWER, k=5,
        )
        assert left.total_ranked == right.total_ranked == 1
        for attr in ("route_id", "score", "score_components", "matched_fields"):
            assert [getattr(c, attr) for c in left.candidates] == [
                getattr(c, attr) for c in right.candidates
            ]


def test_unscoped_authorized_route_still_exposes_original_metadata():
    router, _ = _router(scoped=False)
    result = router.retrieve_routes_authorized(
        "public_value", principal=VIEWER,
    )
    assert len(result.candidates) == 1
    assert result.candidates[0].provider == f"hidden_{CANARY}"
    assert result.candidates[0].access_mode == f"hidden_{CANARY}"


@pytest.mark.asyncio
async def test_async_scoped_route_same_as_sync():
    router, _ = _router()
    before = router.retrieve_routes_authorized(
        "public_value", principal=VIEWER,
    )
    after = await router.aretrieve_routes_authorized(
        "public_value", principal=VIEWER,
    )
    assert before == after

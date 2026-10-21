"""#1532 E0: restricted endpoint descriptors must not expose raw metadata.

Tests address direct public/analyzer schema disclosure; rank/score information
side channels and independent semantic retrieval quality are not claimed.
"""
from __future__ import annotations

import json

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    HostFieldContract,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
    select_authorized_field_contract,
)
from schemarouter.evidence import available_evidence
from schemarouter.planner import KeywordAnalyzer

CANARY = "private_route_canary_q9421"
VIEWER = PrincipalContext(subject="scoped-viewer", roles=("viewer",))


def _router():
    analyzer_views: list[dict] = []

    class InspectingAnalyzer:
        def analyze(self, request, registry):
            analyzer_views.extend(
                tool.model_dump(mode="json")
                for tool in registry.tools()
            )
            return KeywordAnalyzer().analyze(request, registry)

    policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="records.read", roles_any=("viewer",),
        ),),
        data_rules=(DataScopeRule(
            operation="records.read", roles_any=("viewer",),
            visible_fields=("public_value",),
        ),),
    )
    router = SchemaRouter(
        authorization_policy=policy,
        analyzer=InspectingAnalyzer(),
    )
    router.add_tool(ToolSpec(
        name="records",
        description=f"Source text mentions {CANARY}",
        source_type=f"source references {CANARY}",
        license=f"license references {CANARY}",
        provider=f"provider references {CANARY}",
        access_mode=f"access-mode references {CANARY}",
        metadata={"private": CANARY},
        endpoints=[EndpointSpec(
            name="read",
            description=f"Read {CANARY}",
            operation_aliases=[CANARY],
            path=f"/{CANARY}",
            read_only=True,
            metadata={"private": CANARY},
            output_fields=[
                FieldSpec(name="public_value", json_schema={"type": "string"}),
                FieldSpec(name="private_value", json_schema={"type": "string"}),
            ],
        )],
    ))
    return router, analyzer_views


def test_scoped_analyzer_and_public_candidate_strip_untrusted_descriptions():
    router, analyzer_views = _router()
    result = router.retrieve_authorized(
        "public_value", principal=VIEWER, k=5,
    )
    assert len(result.candidates) == 1
    assert analyzer_views
    candidate = result.candidates[0]
    assert candidate.tool_description == ""
    assert candidate.endpoint_description == ""
    assert candidate.source_type is None
    assert candidate.license is None
    assert candidate.provider is None
    assert candidate.access_mode is None
    assert [field.name for field in candidate.output_fields] == ["public_value"]

    serialized_analyzer = json.dumps(analyzer_views, sort_keys=True)
    serialized_candidate = json.dumps(
        candidate.model_dump(mode="json"), sort_keys=True,
    )
    assert CANARY not in serialized_analyzer
    assert CANARY not in serialized_candidate
    assert "private_value" not in serialized_analyzer
    assert "private_value" not in serialized_candidate

    tool = analyzer_views[0]
    assert tool["description"] == ""
    assert tool["source_type"] is None
    assert tool["license"] is None
    assert tool["provider"] is None
    assert tool["access_mode"] is None
    assert tool["metadata"] == {}
    endpoint = tool["endpoints"][0]
    assert endpoint["description"] == ""
    assert endpoint["operation_aliases"] == []
    assert endpoint["path"] is None
    assert endpoint["metadata"] == {}
    assert endpoint["execution_metadata"] == {}


def test_original_source_and_exact_host_contract_remain_valid():
    router, _ = _router()
    tool = router.registry.get("records")
    original = tool.endpoint("read")
    original_tool_fp = tool.fingerprint
    original_endpoint_fp = original.fingerprint
    assert CANARY in json.dumps(tool.model_dump(mode="json"))
    assert original.operation_aliases == [CANARY]
    assert tool.source_type == f"source references {CANARY}"
    assert tool.license == f"license references {CANARY}"
    assert tool.provider == f"provider references {CANARY}"
    assert tool.access_mode == f"access-mode references {CANARY}"
    assert original.path == f"/{CANARY}"
    assert original.metadata == {"private": CANARY}

    decision = select_authorized_field_contract(
        router, "public_value", principal=VIEWER,
        contract=HostFieldContract(
            operation="read", required_output_fields=["public_value"],
        ),
    )
    assert decision.disposition == "selected"
    assert decision.selected_route_id == "records.read"
    assert decision.selected_tool_fingerprint == original_tool_fp
    assert decision.selected_endpoint_fingerprint == original_endpoint_fp

    denied = select_authorized_field_contract(
        router, "public_value", principal=VIEWER,
        contract=HostFieldContract(
            operation="read", required_output_fields=["private_value"],
        ),
    )
    assert denied.disposition == "abstained"
    assert denied.reason == "no_contract_match"


def test_unscoped_original_descriptor_is_not_globally_redacted():
    router, _ = _router()
    tool = router.registry.get("records")
    endpoint = tool.endpoint("read")
    assert router.authorization_policy is not None
    # No matching scope rule: unchanged original local source contract.
    other = PrincipalContext(subject="admin", roles=("admin",))
    assert router._data_scope_endpoint_view(other, tool, endpoint) is endpoint
    assert tool.description.endswith(CANARY)
    assert tool.provider == f"provider references {CANARY}"
    assert tool.access_mode == f"access-mode references {CANARY}"


def test_scoped_tool_provenance_does_not_claim_unreviewed_evidence():
    router, _ = _router()
    original_tool = router.registry.get("records")
    original_endpoint = original_tool.endpoint("read")
    original = available_evidence(
        original_tool, original_endpoint, ["public_value"],
    )
    assert original.provenance is True
    assert original.license is True

    # An analyzer's public restricted registry cannot treat unchecked
    # source-owned labels as provenance/license grants.
    restricted_registry = router._scoped_analysis_registry(
        VIEWER, lambda tool, endpoint: True,
    )
    restricted_tool = restricted_registry.get("records")
    restricted_endpoint = restricted_tool.endpoint("read")
    scoped = available_evidence(
        restricted_tool, restricted_endpoint, ["public_value"],
    )
    assert scoped.provenance is False
    assert scoped.license is False
    assert original_tool.source_type == f"source references {CANARY}"
    assert original_tool.license == f"license references {CANARY}"

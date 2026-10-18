"""Native opt-in FieldGroup Top-K tests: actual planner, no agent execution."""
from __future__ import annotations

import json

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    NativeDeclaredFieldGroup,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
    retrieve_authorized_field_group,
)
from schemarouter.adapters import tool_from_mcp, tool_from_openapi
from schemarouter.errors import PolicyViolationError

ANALYST = PrincipalContext(subject="analyst", roles=("analyst",))
VIEWER = PrincipalContext(subject="viewer", roles=("viewer",))
GROUP = NativeDeclaredFieldGroup(
    aliases=("support status and priority", "고객 문의 상태와 우선순위", "顧客問合せ状態と優先度"),
    required_fields=(
        CapabilityFieldContract(
            semantic_id="support.status", json_schema={"type": "string"},
        ),
        CapabilityFieldContract(
            semantic_id="support.priority", json_schema={"type": "string"},
        ),
    ),
    source_type="support_records", license="locally-reviewed",
)


def _field(name: str, semantic: str, *, kind: str = "string") -> FieldSpec:
    return FieldSpec(name=name, semantic_id=semantic, json_schema={"type": kind})


def _router() -> SchemaRouter:
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(
            AuthorizationRule(effect="deny", operation="private.read",
                              roles_any=("analyst", "viewer")),
            AuthorizationRule(effect="allow", operation="*.read",
                              roles_any=("analyst", "viewer")),
        ),
        data_rules=(DataScopeRule(
            operation="complete.read", roles_any=("viewer",),
            hidden_fields=("priority",),
        ),),
    ))
    for name, fields, source, license_id, read_only in (
        ("partial_status", [_field("status", "support.status")],
         "support_records", "locally-reviewed", True),
        ("partial_priority", [_field("priority", "support.priority")],
         "support_records", "locally-reviewed", True),
        ("wrong_type", [_field("status", "support.status"),
                        _field("priority", "support.priority", kind="integer")],
         "support_records", "locally-reviewed", True),
        ("wrong_source", [_field("status", "support.status"),
                          _field("priority", "support.priority")],
         "unreviewed", "locally-reviewed", True),
        ("wrong_license", [_field("status", "support.status"),
                           _field("priority", "support.priority")],
         "support_records", "unreviewed", True),
        ("mutating", [_field("status", "support.status"),
                      _field("priority", "support.priority")],
         "support_records", "locally-reviewed", False),
        ("private", [_field("status", "support.status"),
                     _field("priority", "support.priority")],
         "support_records", "locally-reviewed", True),
        ("complete", [_field("status", "support.status"),
                      _field("priority", "support.priority")],
         "support_records", "locally-reviewed", True),
    ):
        router.add_tool(ToolSpec(
            name=name, source_type=source, license=license_id,
            endpoints=[EndpointSpec(
                name="read", description="Read support status and priority",
                read_only=read_only, destructive=not read_only,
                output_fields=fields,
            )],
        ))
    return router


@pytest.mark.parametrize("query", GROUP.aliases)
def test_native_topk_requires_complete_authorized_fieldgroup_before_k(query):
    router = _router()
    baseline = router.retrieve_authorized(query, principal=ANALYST, k=5)
    assert any(c.route_id != "complete.read" for c in baseline.candidates)
    result = retrieve_authorized_field_group(
        router, query, principal=ANALYST, group=GROUP,
    )
    assert result.requested_k == 5
    assert result.total_ranked == 1
    assert [candidate.route_id for candidate in result.candidates] == [
        "complete.read",
    ]
    assert {f.semantic_id for f in result.candidates[0].output_fields} == {
        "support.status", "support.priority",
    }
    assert result.candidates[0].tool_fingerprint
    assert result.candidates[0].endpoint_fingerprint
    # Opt-in diagnostic must not silently replace the baseline router.
    assert router.retrieve_authorized(query, principal=ANALYST, k=5) == baseline


def test_principal_field_scope_prevents_a_partial_public_schema():
    router = _router()
    result = retrieve_authorized_field_group(
        router, GROUP.aliases[0], principal=VIEWER, group=GROUP,
    )
    assert result.candidates == []
    assert result.total_ranked == 0
    raw = json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
    assert "private.read" not in raw
    assert "priority" not in raw


def test_unknown_json_schema_and_unit_mismatch_do_not_prove_fieldgroup():
    group = GROUP.model_copy(deep=True)
    group.required_fields[0].json_schema = {"type": "string", "pattern": "^X$"}
    with pytest.raises(ValueError, match="invalid bounded"):
        retrieve_authorized_field_group(
            _router(), GROUP.aliases[0], principal=ANALYST, group=group,
        )

    different_unit = NativeDeclaredFieldGroup(
        aliases=GROUP.aliases,
        required_fields=(
            CapabilityFieldContract(
                semantic_id="support.status", json_schema={"type": "string"},
                unit="kPa",
            ),
            GROUP.required_fields[1],
        ),
        source_type=GROUP.source_type, license=GROUP.license,
    )
    assert retrieve_authorized_field_group(
        _router(), GROUP.aliases[0], principal=ANALYST, group=different_unit,
    ).candidates == []


def test_rejected_query_or_k_does_not_fallback_to_default_retrieval():
    router = _router()
    with pytest.raises(ValueError, match="host-declared"):
        retrieve_authorized_field_group(
            router, "any support records", principal=ANALYST, group=GROUP,
        )
    for k in (1, 4, 6, True, 5.0):
        with pytest.raises(ValueError, match="exactly K5"):
            retrieve_authorized_field_group(
                router, GROUP.aliases[0], principal=ANALYST, group=GROUP, k=k,
            )
    with pytest.raises(ValueError, match="invalid bounded"):
        NativeDeclaredFieldGroup(
            aliases=("x",), required_fields=(
                CapabilityFieldContract(
                    semantic_id="support.status", json_schema={"type": "string", "enum": ["A"]},
                ),
            ),
        )


def test_drift_and_execution_never_become_a_fieldgroup_selection(monkeypatch):
    router = _router()
    def forbidden(*_args, **_kwargs):
        raise AssertionError("FieldGroup lookup cannot plan/execute")
    monkeypatch.setattr(router, "plan", forbidden)
    monkeypatch.setattr(router, "execute", forbidden)
    assert retrieve_authorized_field_group(
        router, GROUP.aliases[0], principal=ANALYST, group=GROUP,
    ).candidates

    original = router._project_retrieval_data_scope
    def drift(*args, **kwargs):
        result = original(*args, **kwargs)
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return result
    monkeypatch.setattr(router, "_project_retrieval_data_scope", drift)
    with pytest.raises(PolicyViolationError, match="retrieval authority changed"):
        retrieve_authorized_field_group(
            router, GROUP.aliases[0], principal=ANALYST, group=GROUP,
        )


def test_actual_mcp_and_openapi_converters_share_native_fieldgroup_boundary():
    openapi = tool_from_openapi("api", {
        "openapi": "3.1.0", "info": {"title": "Support", "version": "1"},
        "paths": {"/status": {"get": {
            "operationId": "read_status",
            "responses": {"200": {"description": "OK", "content": {
                "application/json": {"schema": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "priority": {"type": "string"},
                    },
                }},
            }}},
        }}},
    })
    mcp = tool_from_mcp("mcp", {"tools": [{
        "name": "read_status",
        "annotations": {"readOnlyHint": True},
        "inputSchema": {"type": "object", "properties": {}},
        "outputSchema": {"type": "object", "properties": {
            "status": {"type": "string"}, "priority": {"type": "string"},
        }},
    }]})
    # Remote annotations do not grant read-only authority or semantic IDs.
    assert mcp.endpoint("read_status").read_only is None
    for tool in (openapi, mcp):
        tool.source_type = "support_records"
        tool.license = "locally-reviewed"
        ep = tool.endpoint("read_status")
        for field in ep.output_fields:
            if field.name in {"status", "priority"}:
                field.semantic_id = "support." + field.name
    # An explicit locally reviewed read-only amendment is mandatory for MCP.
    mcp.endpoint("read_status").read_only = True
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(
            AuthorizationRule(effect="allow", operation="*.read_status",
                              roles_any=("analyst",)),
        ),
    ))
    router.add_tool(openapi)
    router.add_tool(mcp)
    result = retrieve_authorized_field_group(
        router, GROUP.aliases[0], principal=ANALYST, group=GROUP,
    )
    assert {c.route_id for c in result.candidates} == {
        "api.read_status", "mcp.read_status",
    }
    assert result.total_ranked == 2

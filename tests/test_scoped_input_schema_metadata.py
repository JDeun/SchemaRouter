"""Regression for #1532: nested INPUT metadata must not cross data scope.

Original provider schema is deliberately retained in trusted registry.
This is only a public/analyzer scoped-descriptor noninterference check.
"""
from __future__ import annotations

import json

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    HostFieldContract,
    ParameterSpec,
    PrincipalContext,
    RequiredEnumValue,
    SchemaRouter,
    ToolSpec,
    select_authorized_field_contract,
)
from schemarouter.planner import KeywordAnalyzer

HIDDEN = "private_value"
VIEWER = PrincipalContext(subject="viewer", roles=("viewer",))
RAW_PARAM_SCHEMA = {
    "type": "string",
    "description": "unreviewed reference to private_value",
    "$defs": {
        "private_value": {
            "type": "object",
            "properties": {"private_value": {"type": "string"}},
        },
    },
    "examples": ["private_value"],
}
RAW_INPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "query": RAW_PARAM_SCHEMA,
        "filter__private_value": {"type": "string"},
    },
    "required": ["query"],
    "$defs": {"private_value": {"type": "string"}},
    "allOf": [{"$ref": "#/$defs/private_value"}],
}


def _router(*, declared_hidden: bool = True):
    inspected: list[dict] = []

    class InspectingAnalyzer:
        def analyze(self, request, registry):
            inspected.extend(
                endpoint.model_dump(mode="json")
                for tool in registry.tools()
                for endpoint in tool.endpoints
            )
            return KeywordAnalyzer().analyze(request, registry)

    policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="records.read", roles_any=("viewer",),
        ),),
        data_rules=(DataScopeRule(
            operation="records.read", roles_any=("viewer",),
            **(
                {"hidden_fields": (HIDDEN,)}
                if declared_hidden
                else {"visible_fields": ("public_value",)}
            ),
        ),),
    )
    fields = [FieldSpec(name="public_value", json_schema={"type": "string"})]
    if declared_hidden:
        fields.append(FieldSpec(name=HIDDEN, json_schema={"type": "string"}))
    router = SchemaRouter(authorization_policy=policy, analyzer=InspectingAnalyzer())
    router.add_tool(ToolSpec(
        name="records",
        endpoints=[EndpointSpec(
            name="read", description="Read public_value records", read_only=True,
            parameters=[
                ParameterSpec(
                    name="query", description="private_value in producer docs",
                    aliases=["private_value"],
                    required=True, location="query", json_schema=RAW_PARAM_SCHEMA,
                ),
                ParameterSpec(
                    name="filter__private_value", location="query",
                    json_schema={"type": "string"},
                ),
            ],
            input_schema=RAW_INPUT_SCHEMA,
            output_fields=fields,
            output_schema={
                "type": "object",
                "properties": {
                    f.name: {"type": "string"} for f in fields
                },
            },
        )],
    ))
    return router, inspected


@pytest.mark.parametrize("declared_hidden", [True, False])
def test_no_nested_input_refs_or_annotations_reach_scoped_catalog_or_candidate(
    declared_hidden: bool,
):
    router, inspected = _router(declared_hidden=declared_hidden)
    result = router.retrieve_authorized("public_value", principal=VIEWER, k=5)
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert [p.name for p in candidate.parameters] == ["query"]
    assert candidate.parameters[0].json_schema == {"type": "string"}
    assert candidate.parameters[0].description == ""
    assert candidate.parameters[0].aliases == []
    assert candidate.input_schema == {
        "type": "object",
        "properties": {"query": {"type": "string"}},
        "required": ["query"],
    }
    for surfaced in [inspected, result.model_dump(mode="json")]:
        serialized = json.dumps(surfaced, ensure_ascii=False)
        assert HIDDEN not in serialized
        assert "$defs" not in serialized
        assert "$ref" not in serialized
        assert "examples" not in serialized

    original = router.registry.get("records").endpoint("read")
    assert original.input_schema == RAW_INPUT_SCHEMA
    assert original.parameters[0].json_schema == RAW_PARAM_SCHEMA
    assert HIDDEN in json.dumps(original.model_dump(mode="json"))
    assert "filter__private_value" in original.input_schema["properties"]


def test_public_descriptor_cannot_be_confused_with_raw_validation_contract():
    router, _ = _router()
    original = router.registry.get("records").endpoint("read")
    public = router._data_scope_endpoint_view(
        VIEWER, router.registry.get("records"), original,
    )
    assert public is not None
    assert original.fingerprint != public.fingerprint
    assert original.parameters[0].json_schema is not public.parameters[0].json_schema
    assert original.input_schema is not public.input_schema


def test_host_owned_enum_fit_remains_private_but_original_proof_selects():
    """Raw provider enum is read internally after scope and receipt checks."""
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
    router = SchemaRouter(authorization_policy=policy)
    router.add_tool(ToolSpec(
        name="records",
        endpoints=[EndpointSpec(
            name="read",
            read_only=True,
            parameters=[ParameterSpec(
                name="category", location="query", required=True,
                json_schema={
                    "type": "string", "enum": ["marine"],
                    "description": "private_value",
                },
            )],
            input_schema={
                "type": "object",
                "properties": {"category": {
                    "type": "string", "enum": ["marine"],
                }},
                "required": ["category"],
            },
            output_fields=[FieldSpec(
                name="public_value", json_schema={"type": "string"},
            )],
        )],
    ))
    result = router.retrieve_authorized(
        "public_value", principal=VIEWER, k=5,
    )
    assert len(result.candidates) == 1
    raw = router.registry.get("records").endpoint("read")
    assert raw.parameters[0].json_schema["enum"] == ["marine"]
    visible = result.candidates[0].parameters[0]
    assert visible.json_schema == {"type": "string"}
    assert "private_value" not in json.dumps(result.model_dump(mode="json"))

    receipt = select_authorized_field_contract(
        router, "public_value", principal=VIEWER,
        contract=HostFieldContract(
            operation="read",
            required_enums=[RequiredEnumValue(
                parameter="category", value="marine",
            )],
            required_output_fields=["public_value"],
        ),
    )
    assert receipt.disposition == "selected"
    assert receipt.selected_route_id == "records.read"
    assert "marine" not in json.dumps(receipt.model_dump(mode="json"))

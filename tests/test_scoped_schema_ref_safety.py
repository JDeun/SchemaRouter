"""Prevent recursive/ref JSON Schema names from crossing a data-scope boundary."""

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


@pytest.mark.parametrize("with_named_hidden_field", [True, False])
def test_data_scoped_output_never_exposes_nested_hidden_schema_metadata(
    with_named_hidden_field: bool,
) -> None:
    hidden = "private_value"
    nested = {
        "type": "number",
        "$defs": {
            "private_value": {
                "type": "object",
                "properties": {hidden: {"type": "string"}},
            },
        },
        "allOf": [{"$ref": "#/$defs/private_value"}],
        "description": "secret schema private_value",
    }
    raw_schema = {
        "type": "object",
        "properties": {
            "public_value": {"$ref": "#/$defs/visible"},
            hidden: {"type": "string"},
        },
        "$defs": {
            "visible": nested,
            "private_value": {"type": "string"},
        },
    }
    fields = [FieldSpec(name="public_value", json_schema=nested)]
    if with_named_hidden_field:
        fields.append(FieldSpec(name=hidden, json_schema={"type": "string"}))
    policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="materials.read", roles_any=("viewer",),
        ),),
        data_rules=(DataScopeRule(
            operation="materials.read", roles_any=("viewer",),
            **(
                {"hidden_fields": (hidden,)}
                if with_named_hidden_field
                else {"visible_fields": ("public_value",)}
            ),
        ),),
    )
    inspected: list[dict] = []

    class InspectingAnalyzer:
        def analyze(self, request, registry):
            inspected.extend(
                endpoint.model_dump(mode="json")
                for tool in registry.tools()
                for endpoint in tool.endpoints
            )
            return KeywordAnalyzer().analyze(request, registry)

    router = SchemaRouter(
        authorization_policy=policy,
        analyzer=InspectingAnalyzer(),
    )
    router.add_tool(ToolSpec(
        name="materials",
        endpoints=[EndpointSpec(
            name="read", description="Read public sample", read_only=True,
            output_fields=fields,
            output_schema=raw_schema,
        )],
    ))
    viewer = PrincipalContext(subject="viewer", roles=("viewer",))
    received = router.retrieve_authorized(
        "public_value", principal=viewer, k=5,
    )
    assert len(received.candidates) == 1
    candidate = received.candidates[0]
    assert candidate.output_schema == {
        "type": "object",
        "properties": {"public_value": {"type": "number"}},
    }
    assert candidate.output_fields[0].json_schema == {"type": "number"}
    assert hidden not in json.dumps(received.model_dump(mode="json"))
    assert inspected
    assert hidden not in json.dumps(inspected)

    original = router.registry.get("materials").endpoint("read")
    assert original.output_schema == raw_schema
    assert original.output_fields[0].json_schema == nested
    # Trusted raw provider validation remains on the unmodified source schema.
    assert hidden in json.dumps(original.model_dump(mode="json"))


def test_masked_scope_with_all_visible_declarations_still_strips_unknown_refs() -> None:
    policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="materials.read", roles_any=("viewer",),
        ),),
        data_rules=(DataScopeRule(
            operation="materials.read", roles_any=("viewer",),
            visible_fields=("public_value",),
        ),),
    )
    router = SchemaRouter(authorization_policy=policy)
    router.add_tool(ToolSpec(
        name="materials",
        endpoints=[EndpointSpec(
            name="read", description="Public metric", read_only=True,
            output_fields=[FieldSpec(name="public_value", json_schema={
                "$ref": "#/$defs/secret",
            })],
            output_schema={
                "type": "object",
                "properties": {"public_value": {"type": "number"}},
                "$defs": {"secret": {"private_value": {"type": "string"}}},
            },
        )],
    ))
    viewer = PrincipalContext(subject="viewer", roles=("viewer",))
    result = router.retrieve_authorized("public_value", principal=viewer, k=5)
    assert len(result.candidates) == 1
    assert result.candidates[0].output_schema == {
        "type": "object", "properties": {"public_value": {}},
    }
    assert "private_value" not in json.dumps(result.model_dump(mode="json"))

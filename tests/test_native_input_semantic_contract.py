"""Native input ontology is source metadata, not a model guess or authority."""
from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)


def _tool(*, semantic_id: str | None) -> ToolSpec:
    return ToolSpec(
        name="materials",
        provider="synthetic",
        source_type="materials_data",
        license="CC-BY-4.0",
        endpoints=[EndpointSpec(
            name="read",
            read_only=True,
            parameters=[ParameterSpec(
                name="material_id", required=True,
                json_schema={"type": "string"},
                semantic_id=semantic_id,
            )],
            output_fields=[FieldSpec(
                name="result",
                semantic_id="mechanics.elastic_modulus",
                json_schema={"type": "number"},
            )],
        )],
    )


def test_unannotated_parameter_has_byte_identical_legacy_json_shape():
    p = ParameterSpec(
        name="material_id", required=True,
        json_schema={"type": "string"},
    )
    assert "semantic_id" not in p.model_dump()
    assert "semantic_id" not in p.model_dump(mode="json")
    assert "semantic_id" not in json.loads(p.model_dump_json())

    base = _tool(semantic_id=None)
    body = base.model_dump(mode="json")
    assert "semantic_id" not in body["endpoints"][0]["parameters"][0]
    assert "semantic_id" not in base.endpoint("read").model_dump(
        mode="json"
    )["parameters"][0]
    assert json.loads(base.model_dump_json()) == body

    # Legacy reloading has identical wire data and schema revision receipts.
    reloaded = ToolSpec.model_validate(body)
    assert reloaded == base
    assert reloaded.fingerprint == base.fingerprint
    assert reloaded.endpoint("read").fingerprint == base.endpoint("read").fingerprint


def test_explicit_semantic_id_round_trip_and_versioned_fingerprint_change():
    legacy = _tool(semantic_id=None)
    declared = _tool(semantic_id="resource.material_id")
    assert legacy.endpoint("read").parameters[0].semantic_id is None
    assert declared.endpoint("read").parameters[0].semantic_id == (
        "resource.material_id"
    )
    assert declared.model_dump(mode="json")["endpoints"][0]["parameters"][0][
        "semantic_id"
    ] == "resource.material_id"
    assert ToolSpec.model_validate(declared.model_dump(mode="json")) == declared
    assert declared.fingerprint != legacy.fingerprint
    assert declared.endpoint("read").fingerprint != legacy.endpoint("read").fingerprint
    assert declared.endpoint("read").parameters[0].json_schema == (
        legacy.endpoint("read").parameters[0].json_schema
    )


@pytest.mark.parametrize("bad", (
    "", " ", " resource.material_id", "resource.material_id ",
    "resource material.id", "resource\nmaterial.id", "resource\tmaterial.id",
    "X" * 161, "material.\x00id",
))
def test_declaration_rejects_ambiguous_or_unsafe_semantic_ids(bad):
    with pytest.raises(ValidationError, match="declared input semantic_id"):
        ParameterSpec(
            name="material_id",
            json_schema={"type": "string"},
            semantic_id=bad,
        )


def test_absent_semantic_id_does_not_change_native_route_retrieval():
    principal = PrincipalContext(subject="research", roles=("viewer",))
    base = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="materials.read", roles_any=("viewer",),
        ),),
    ))
    annotated = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="materials.read", roles_any=("viewer",),
        ),),
    ))
    base.add_tool(_tool(semantic_id=None))
    annotated.add_tool(_tool(semantic_id="resource.material_id"))
    ordinary = base.retrieve_authorized("elastic modulus", principal=principal, k=5)
    extended = annotated.retrieve_authorized(
        "elastic modulus", principal=principal, k=5,
    )
    assert [c.route_id for c in ordinary.candidates] == [
        c.route_id for c in extended.candidates
    ]
    assert [c.score for c in ordinary.candidates] == [
        c.score for c in extended.candidates
    ]
    assert [c.matched_fields for c in ordinary.candidates] == [
        c.matched_fields for c in extended.candidates
    ]
    assert extended.candidates[0].tool_fingerprint != (
        ordinary.candidates[0].tool_fingerprint
    )


def test_a_semantic_annotation_is_not_an_execution_authority(monkeypatch):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
    ))
    router.add_tool(_tool(semantic_id="resource.material_id"))
    principal = PrincipalContext(subject="denied", roles=("viewer",))

    def forbidden(*_args, **_kwargs):
        raise AssertionError("semantic metadata must not execute anything")

    monkeypatch.setattr(router, "execute", forbidden)
    result = router.retrieve_authorized(
        "resource.material_id", principal=principal, k=5,
    )
    assert result.candidates == []


def test_no_synthetic_semantic_id_is_inferred_from_parameter_name():
    param = ParameterSpec(
        name="material_id",
        aliases=["material_identifier", "mp-id"],
        json_schema={"type": "string"},
    )
    assert param.semantic_id is None
    assert "semantic_id" not in param.model_dump(mode="json")

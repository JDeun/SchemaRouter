"""Real-adapter/native schema semantic attestation: source pin, no invention."""
from __future__ import annotations

from copy import deepcopy

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    NativeDeclaredFieldGroup,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
    retrieve_authorized_field_group,
)
from schemarouter.adapters import tool_from_mcp, tool_from_openapi
from schemarouter.adapters.optimade import _tool_from_discovery
from schemarouter.semantic_attestations import (
    HostSemanticAttestation,
    HostSemanticMapping,
    apply_host_semantic_attestation,
)

ANALYST = PrincipalContext(subject="host-analyst", roles=("analyst",))


def _native_openapi():
    tool = tool_from_openapi("contacts", {
        "openapi": "3.1.0", "info": {"title": "Contacts", "version": "1"},
        "paths": {"/contacts": {"get": {
            "operationId": "lookup",
            "responses": {"200": {"description": "OK", "content": {
                "application/json": {"schema": {
                    "type": "object", "properties": {
                        "contact_id": {"type": "string"},
                        "status": {"type": "string"},
                    },
                }},
            }}},
        }}},
    })
    tool.source_type = "crm"
    tool.license = "host-approved-terms"
    return tool


def _native_mcp():
    tool = tool_from_mcp("cases", {"tools": [{
        "name": "read_case", "annotations": {"readOnlyHint": True},
        "inputSchema": {"type": "object", "properties": {
            "contact_id": {"type": "string"},
        }, "required": ["contact_id"]},
        "outputSchema": {"type": "object", "properties": {
            "status": {"type": "string"},
        }},
    }]})
    tool.source_type = "crm"
    tool.license = "host-approved-terms"
    return tool


def _attest(tool: ToolSpec, endpoint: str, *mappings):
    ep = tool.endpoint(endpoint)
    return HostSemanticAttestation(
        expected_tool_key=tool.key,
        expected_tool_fingerprint=tool.fingerprint,
        source_type=tool.source_type, license=tool.license,
        reviewed_by="local-host-ontology-owner",
        mappings=tuple(
            HostSemanticMapping(
                endpoint_name=endpoint,
                expected_endpoint_fingerprint=ep.fingerprint,
                member_kind=kind,
                member_name=name,
                semantic_id=semantic,
            )
            for kind, name, semantic in mappings
        ),
    )


def test_openapi_existing_field_is_annotated_without_source_mutation_or_permissions():
    tool = _native_openapi()
    fp = tool.fingerprint
    old_ep = tool.endpoint("lookup")
    amended = apply_host_semantic_attestation(
        tool, attestation=_attest(
            tool, "lookup",
            ("output_field", "contact_id", "crm.contact_id"),
            ("output_field", "status", "crm.status"),
        ),
    )
    assert tool.fingerprint == fp
    assert amended.fingerprint != fp
    assert all(field.semantic_id is None for field in old_ep.output_fields)
    assert {field.name: field.semantic_id for field in amended.endpoint("lookup").output_fields} == {
        "contact_id": "crm.contact_id",
        "status": "crm.status",
    }
    assert amended.endpoint("lookup").read_only == old_ep.read_only
    assert amended.endpoint("lookup").destructive == old_ep.destructive
    assert amended.endpoint("lookup").input_schema == old_ep.input_schema
    assert amended.endpoint("lookup").output_schema == old_ep.output_schema
    assert amended.execution_metadata == tool.execution_metadata
    assert amended.metadata == tool.metadata


def test_mcp_untrusted_readonly_hint_is_never_promoted_into_authority():
    tool = _native_mcp()
    assert tool.endpoint("read_case").read_only is None
    enriched = apply_host_semantic_attestation(
        tool, attestation=_attest(
            tool, "read_case",
            ("input_parameter", "contact_id", "crm.contact_id"),
            ("output_field", "status", "crm.status"),
        ),
    )
    ep = enriched.endpoint("read_case")
    assert ep.read_only is None
    assert ep.parameters[0].semantic_id == "crm.contact_id"
    assert ep.output_fields[0].semantic_id == "crm.status"
    assert ep.metadata["annotations"]["readOnlyHint"] is True

    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="cases.read_case", roles_any=("analyst",),
        ),),
    ))
    router.add_tool(enriched)
    assert retrieve_authorized_field_group(
        router, "case status", principal=ANALYST,
        group=NativeDeclaredFieldGroup(
            aliases=("case status",),
            required_fields=(CapabilityFieldContract(
                semantic_id="crm.status", json_schema={"type": "string"},
            ),), source_type="crm", license="host-approved-terms",
        ),
    ).candidates == []


def test_real_optimade_discovery_scalar_metadata_can_be_reviewed_without_domain_bias():
    tool = _tool_from_discovery(
        name="materials", namespace=None,
        versioned_base_url="https://example.org/optimade/v1",
        base_info={"api_version": "1.2.0"},
        entries={"structures": {"properties": {
            "chemical_formula_reduced": {"type": "string"},
        }}}, skipped=[],
    )
    tool.source_type = "materials"
    tool.license = "host-reviewed-usage"
    scalar = [(ep, field) for ep in tool.endpoints for field in ep.output_fields
              if field.json_schema == {"type": "string"}]
    if scalar:
        endpoint, field = scalar[0]
        enriched = apply_host_semantic_attestation(
            tool, attestation=_attest(
                tool, endpoint.name,
                ("output_field", field.name, "materials.structure_label"),
            ),
        )
        assert enriched.endpoint(endpoint.name).output_fields[
            next(i for i, x in enumerate(endpoint.output_fields) if x.name == field.name)
        ].semantic_id == "materials.structure_label"
    else:
        # No adapter-inferred flat scalar field: an attestation must abstain.
        with pytest.raises(ValueError, match="cannot invent"):
            apply_host_semantic_attestation(
                tool, attestation=_attest(
                    tool, tool.endpoints[0].name,
                    ("output_field", "invented", "materials.structure_label"),
                ),
            )


@pytest.mark.parametrize("change,match", [
    ("tool_fp", "tool contract differs"),
    ("source", "tool contract differs"),
    ("license", "tool contract differs"),
    ("endpoint_fp", "endpoint changed"),
    ("missing_field", "cannot invent"),
    ("missing_endpoint", "nonexistent native endpoint"),
])
def test_source_revision_provenance_and_member_must_match_exactly(change, match):
    tool = _native_openapi()
    doc = _attest(tool, "lookup", ("output_field", "status", "crm.status"))
    bad = doc.model_copy(deep=True)
    if change == "tool_fp":
        bad.expected_tool_fingerprint = "a" * 64
    elif change == "source":
        bad.source_type = "wrong-source"
    elif change == "license":
        bad.license = "unreviewed-license"
    elif change == "endpoint_fp":
        bad.mappings[0].expected_endpoint_fingerprint = "a" * 64
    elif change == "missing_field":
        bad.mappings[0].member_name = "invented"
    else:
        bad.mappings[0].endpoint_name = "invented"
    with pytest.raises(ValueError, match=match):
        apply_host_semantic_attestation(tool, attestation=bad)
    assert tool.endpoint("lookup").output_fields[0].semantic_id is None


def test_duplicate_conflict_and_unsafe_semantic_id_fail_closed():
    tool = _native_openapi()
    atom = _attest(tool, "lookup", ("output_field", "status", "crm.status"))
    with pytest.raises(ValueError, match="invalid bounded"):
        HostSemanticAttestation(
            **{**atom.model_dump(),
               "mappings": [atom.mappings[0].model_dump()] * 2},
        )
    with pytest.raises(ValueError, match="invalid bounded"):
        HostSemanticMapping(
            endpoint_name="lookup", expected_endpoint_fingerprint=tool.endpoint("lookup").fingerprint,
            member_kind="output_field", member_name="status",
            semantic_id="invalid; injection",
        )
    occupied = deepcopy(tool)
    next(f for f in occupied.endpoint("lookup").output_fields
         if f.name == "status").semantic_id = "different.original"
    with pytest.raises(ValueError, match="semantic identity conflicts"):
        apply_host_semantic_attestation(
            occupied,
            attestation=_attest(
                occupied, "lookup", ("output_field", "status", "crm.status"),
            ),
        )


def test_complex_schema_and_fake_metadata_only_catalog_cannot_be_completed_from_gold():
    tool = _native_openapi()
    target = next(f for f in tool.endpoint("lookup").output_fields
                  if f.name == "status")
    target.json_schema = {"type": "string", "pattern": "^open$"}
    with pytest.raises(ValueError, match="unproved native member JSON Schema"):
        apply_host_semantic_attestation(
            tool, attestation=_attest(
                tool, "lookup", ("output_field", "status", "crm.status"),
            ),
        )

    # Mirrors existing Qwen3 metadata-only DEV source: only name+description
    # exist, NO field names, schemas or output observations are registered.
    from schemarouter import EndpointSpec
    metadata_only = ToolSpec(
        name="published_dev_tool", source_type="fixture",
        license="host-reviewed", endpoints=[EndpointSpec(
            name="search", description="Find records", read_only=True,
        )],
    )
    with pytest.raises(ValueError, match="cannot invent"):
        apply_host_semantic_attestation(
            metadata_only, attestation=_attest(
                metadata_only, "search",
                ("output_field", "expected_answer_from_gold", "truth.answer"),
            ),
        )


def test_valid_attestation_does_not_allow_declaring_new_readonly_or_updating_registry():
    tool = _native_mcp()
    fingerprint = tool.fingerprint
    _ = apply_host_semantic_attestation(
        tool, attestation=_attest(
            tool, "read_case", ("output_field", "status", "crm.status"),
        ),
    )
    assert tool.fingerprint == fingerprint
    assert tool.endpoint("read_case").read_only is None

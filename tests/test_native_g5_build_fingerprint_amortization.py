"""E0: G5 builds retain original full-native fingerprints, once per tool scan."""
from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    FieldSpec,
    NativeDeclaredFieldGroup,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.errors import PolicyViolationError
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex

QUERY = "case status"
PRINCIPAL = PrincipalContext(subject="reader", roles=("reader",))
GROUP = NativeDeclaredFieldGroup(
    aliases=(QUERY,),
    required_fields=(CapabilityFieldContract(
        semantic_id="crm.status", json_schema={"type": "string"},
    ),),
    source_type="crm", license="reviewed",
)


def _source() -> SchemaRouter:
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny", rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader",),
        ),),
    ))
    for name, endpoints in (
        ("contacts", [
            EndpointSpec(
                name="read", read_only=True,
                output_fields=[FieldSpec(
                    name="contact_id", semantic_id="crm.contact_id",
                    json_schema={"type": "string"}, identifier=True,
                )],
            ),
            *[
                EndpointSpec(
                    name=f"other_{n}", read_only=True,
                    output_fields=[FieldSpec(
                        name="name", semantic_id=f"noise_{n}.name",
                        json_schema={"type": "string"},
                    )],
                )
                for n in range(14)
            ],
        ]),
        ("cases", [
            EndpointSpec(
                name="read", read_only=True,
                parameters=[{
                    "name": "contact_id", "required": True, "location": "argument",
                    "semantic_id": "crm.contact_id",
                    "json_schema": {"type": "string"},
                }],
                input_schema={
                    "type": "object",
                    "properties": {"contact_id": {"type": "string"}},
                    "required": ["contact_id"],
                },
                output_fields=[FieldSpec(
                    name="status", semantic_id="crm.status",
                    json_schema={"type": "string"},
                )],
            ),
            *[
                EndpointSpec(name=f"extra_{n}", read_only=True)
                for n in range(12)
            ],
        ]),
    ):
        router.add_tool(ToolSpec(
            name=name, source_type="crm", license="reviewed",
            endpoints=endpoints,
        ))
    return router


def test_multientpoint_build_reuses_one_parent_hash_with_exact_original_identity(
    monkeypatch,
):
    router = _source()
    snapshots = router.registry.tools()
    reference: dict[str, tuple[str, str]] = {
        f"{tool.key}.{endpoint.name}": (tool.fingerprint, endpoint.fingerprint)
        for tool in snapshots for endpoint in tool.endpoints
    }
    assert len(reference) == 28
    getter = ToolSpec.fingerprint.fget
    assert getter is not None
    calls = 0

    def counted(tool):
        nonlocal calls
        calls += 1
        return getter(tool)

    with monkeypatch.context() as patched:
        patched.setattr(ToolSpec, "fingerprint", property(counted))
        field_index = NativeSchemaPostingIndex.build(router.registry)
        assert calls == len(snapshots)
        assert dict(field_index.route_fingerprints) == reference
        calls = 0
        graph = NativeSchemaGraphIndex.build(field_index)
        assert calls == len(snapshots)
        assert dict(graph.field_index.route_fingerprints) == reference

    outcome = graph.lookup(router, QUERY, principal=PRINCIPAL, group=GROUP)
    assert outcome.status == "complete"
    assert outcome.qualified_path_count == 1
    assert [(c.producer_route_id, c.consumer_route_id) for c in outcome.candidates] == [
        ("contacts.read", "cases.read"),
    ]


def test_mutated_native_source_refuses_stale_graph_even_after_hash_amortization():
    router = _source()
    field_index = NativeSchemaPostingIndex.build(router.registry)
    graph = NativeSchemaGraphIndex.build(field_index)
    tool = router.registry.get("contacts")
    tool.description = "source-owned changed schema"
    router.add_tool(tool, replace=True)
    with pytest.raises(PolicyViolationError, match="stale"):
        graph.lookup(router, QUERY, principal=PRINCIPAL, group=GROUP)
    with pytest.raises(PolicyViolationError, match="changed before graph build"):
        NativeSchemaGraphIndex.build(field_index)
    assert NativeSchemaPostingIndex.build(router.registry).snapshot_id != (
        field_index.snapshot_id
    )

"""G5 E0: full native multi-parameter binding from ONE typed, scoped root."""

from __future__ import annotations

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.capability_contracts import CapabilityFieldContract
from schemarouter.field_group_retrieval import NativeDeclaredFieldGroup
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex

ACTOR = PrincipalContext(subject="analyst", roles=("reader",))
MASKED = PrincipalContext(subject="viewer", roles=("viewer",))
GROUP = NativeDeclaredFieldGroup(
    aliases=("case status", "문의 상태", "問い合わせ状態"),
    required_fields=(
        CapabilityFieldContract(
            semantic_id="crm.status", json_schema={"type": "string"},
        ),
    ),
    source_type="crm",
    license="owner-reviewed",
)


def _router(
    *,
    producer_fields: tuple[tuple[str, str, str], ...] = (
        ("contact_id", "crm.contact_id", "string"),
        ("region_id", "crm.region_id", "string"),
    ),
    requirements: tuple[tuple[str, str, str, bool], ...] = (
        ("contact_id", "crm.contact_id", "string", True),
        ("region_id", "crm.region_id", "string", True),
    ),
    hidden: bool = False,
    schema_override: dict | None = None,
) -> SchemaRouter:
    parameters = [
        ParameterSpec(
            name=name, semantic_id=semantic, required=required,
            json_schema={"type": kind},
        )
        for name, semantic, kind, required in requirements
    ]
    declared = {
        "type": "object",
        "properties": {p.name: p.json_schema for p in parameters},
        "required": [p.name for p in parameters if p.required],
    }
    policy = AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader", "viewer"),
        ),),
        data_rules=(
            (DataScopeRule(
                operation="contacts.read", roles_any=("viewer",),
                hidden_fields=("region_id",),
            ),) if hidden else ()
        ),
    )
    router = SchemaRouter(authorization_policy=policy)
    router.add_tool(ToolSpec(
        name="contacts", source_type="crm", license="owner-reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            output_fields=[
                FieldSpec(
                    name=name, semantic_id=semantic, identifier=True,
                    json_schema={"type": kind},
                )
                for name, semantic, kind in producer_fields
            ],
        )],
    ))
    router.add_tool(ToolSpec(
        name="cases", source_type="crm", license="owner-reviewed",
        endpoints=[EndpointSpec(
            name="read", read_only=True,
            parameters=parameters,
            input_schema=schema_override if schema_override is not None else declared,
            output_fields=[FieldSpec(
                name="status", semantic_id="crm.status",
                json_schema={"type": "string"},
            )],
        )],
    ))
    return router


def _index(router: SchemaRouter) -> NativeSchemaGraphIndex:
    return NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )


@pytest.mark.parametrize("query", GROUP.aliases)
def test_two_input_complete_binding_original_owned_ids(query: str) -> None:
    router = _router()
    graph = _index(router)
    assert graph.graph.predecessors("cases.read") == ("contacts.read",)
    out = graph.lookup(router, query, principal=ACTOR, group=GROUP)
    assert out.status == "complete"
    assert out.qualified_path_count == 1
    assert len(out.candidates) == 1
    c = out.candidates[0]
    assert c.parameter_bindings == (
        ("contact_id", "contact_id"),
        ("region_id", "region_id"),
    )
    # A single-field legacy receipt MUST NOT masquerade as a complete
    # multi-parameter argument mapping.
    assert c.producer_identifier_field is None
    assert c.consumer_required_parameter is None
    assert c.consumer_output_fields == ("status",)
    assert out.executable_authority is False
    assert out.independent_quality_evidence is False
    assert out.calibrated_no_fit is False


@pytest.mark.parametrize(("change", "kwargs"), [
    ("missing producer field", {
        "producer_fields": (("contact_id", "crm.contact_id", "string"),),
    }),
    ("incompatible region type", {
        "producer_fields": (
            ("contact_id", "crm.contact_id", "string"),
            ("region_id", "crm.region_id", "integer"),
        ),
    }),
    ("one input optional", {
        "requirements": (
            ("contact_id", "crm.contact_id", "string", True),
            ("region_id", "crm.region_id", "string", False),
        ),
    }),
    ("extra undeclared consumer property", {
        "schema_override": {
            "type": "object",
            "properties": {
                "contact_id": {"type": "string"},
                "region_id": {"type": "string"},
                "private_shadow": {"type": "string"},
            },
            "required": ["contact_id", "region_id"],
        },
    }),
])
def test_multi_input_rejects_incomplete_or_unproven_contracts(
    change: str, kwargs: dict,
) -> None:
    router = _router(**kwargs)
    index = _index(router)
    assert index.graph.predecessors("cases.read") == (), change
    out = index.lookup(router, GROUP.aliases[0], group=GROUP, principal=ACTOR)
    assert out.status == "no_proven_hit"
    assert out.candidates == ()


def test_same_semantic_id_producer_ambiguous_binding_fails_closed() -> None:
    router = _router(producer_fields=(
        ("contact_id", "crm.contact_id", "string"),
        ("contact_alt", "crm.contact_id", "string"),
        ("region_id", "crm.region_id", "string"),
    ))
    idx = _index(router)
    # Canonical typed graph marks the contract jointly satisfiable, but the
    # native wire binder cannot choose arbitrarily between duplicate fields.
    assert idx.graph.predecessors("cases.read") == ("contacts.read",)
    result = idx.lookup(router, GROUP.aliases[0], group=GROUP, principal=ACTOR)
    assert result.status == "no_proven_hit"


def test_hidden_one_required_identifier_blocks_complete_multi_binding() -> None:
    router = _router(hidden=True)
    idx = _index(router)
    assert idx.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
    ).status == "complete"
    # Viewer may see contact_id, but a field-scope mask hides region_id.
    result = idx.lookup(router, GROUP.aliases[0], group=GROUP, principal=MASKED)
    assert result.status == "no_proven_hit"
    assert result.candidates == ()


def test_unavailable_producer_and_schema_version_change_fail_closed() -> None:
    router = _router()
    idx = _index(router)
    router.planner.availability_predicate = (
        lambda tool, endpoint: tool.key != "contacts"
    )
    assert idx.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
    ).status == "no_proven_hit"
    router.planner.availability_predicate = None
    router.add_tool(ToolSpec(
        name="unrelated", source_type="crm", license="owner-reviewed",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    ))
    with pytest.raises(Exception, match="stale|revision|changed"):
        idx.lookup(router, GROUP.aliases[0], group=GROUP, principal=ACTOR)


def test_more_than_four_required_inputs_are_conservatively_not_graphable() -> None:
    req = tuple(
        (f"key_{i}", f"crm.key_{i}", "string", True) for i in range(5)
    )
    root = tuple(
        (f"key_{i}", f"crm.key_{i}", "string") for i in range(5)
    )
    router = _router(producer_fields=root, requirements=req)
    idx = _index(router)
    assert idx.graph.predecessors("cases.read") == ()
    assert idx.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ACTOR,
    ).status == "no_proven_hit"

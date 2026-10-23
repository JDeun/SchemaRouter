"""#1711: nonexecuting paired full-schema/surgical G5 context controls."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    DataScopeRule,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.errors import PolicyViolationError
from schemarouter.native_graph_index import NativeSchemaGraphIndex
from schemarouter.native_semantic_index import NativeSchemaPostingIndex

READER = PrincipalContext(subject="reader-one", roles=("reader",))
VIEWER = PrincipalContext(subject="viewer-one", roles=("viewer",))
QUERY = "case status"


def _source(*, missing_input: bool = False, extra_consumers: int = 0):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(AuthorizationRule(
            effect="allow", operation="*.*", roles_any=("reader",),
        ),),
    ))
    producer = [("contact_id", "crm.contact_id"), ("region_id", "crm.region_id")]
    if missing_input:
        producer = producer[:1]
    router.add_tool(ToolSpec(
        name="contacts", description="case status root contact region lookup",
        source_type="crm", license="owner-reviewed",
        endpoints=[EndpointSpec(
            name="read", description="case status root identifier",
            read_only=True,
            output_fields=[FieldSpec(
                name=name, semantic_id=semantic, identifier=True,
                json_schema={"type": "string"},
            ) for name, semantic in producer],
            output_schema={
                "type": "object",
                "properties": {name: {"type": "string"} for name, _ in producer},
                "required": [name for name, _ in producer],
            },
        )],
    ))
    for i in range(extra_consumers + 1):
        name = "cases" if i == 0 else f"cases_{i}"
        names = ("contact_id", "region_id")
        router.add_tool(ToolSpec(
            name=name, description="case status CRM query",
            source_type="crm", license="owner-reviewed",
            endpoints=[EndpointSpec(
                name="read", description="case status from CRM account",
                read_only=True,
                parameters=[ParameterSpec(
                    name=param, semantic_id=f"crm.{param}", required=True,
                    json_schema={"type": "string"},
                ) for param in names],
                input_schema={
                    "type": "object",
                    "properties": {param: {"type": "string"} for param in names},
                    "required": list(names),
                },
                output_fields=[FieldSpec(
                    name="status", semantic_id="crm.status",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id="case_status", aliases=(QUERY, "문의 상태", "問い合わせ状態"),
        required_fields=(CapabilityFieldContract(
            semantic_id="crm.status", json_schema={"type": "string"},
        ),),
        source_type="crm", license="owner-reviewed",
    ),))
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    return router, catalog, index


def test_same_scoped_g5_path_and_complete_bindings_without_executable_grant():
    from scripts.research_codegraph_surgical_context_e0 import compare_contexts

    router, catalog, index = _source()
    result = compare_contexts(
        router, QUERY, principal=READER, catalog=catalog, index=index,
    )
    full, surgical = result["full_envelope"], result["surgical_envelope"]
    assert full["status"] == surgical["status"] == "complete"
    assert full["route_ids"] == surgical["route_ids"] == [
        "contacts.read", "cases.read",
    ]
    assert full["route_sets"] == surgical["route_sets"]
    assert full["route_sets"][0]["parameter_bindings"] == [
        ["contact_id", "contact_id"], ["region_id", "region_id"],
    ]
    assert full["route_sets"][0]["visible_output_fields"] == [
        {"route_id": "contacts.read", "fields": ["contact_id", "region_id"]},
        {"route_id": "cases.read", "fields": ["status"]},
    ]
    assert all(len(row) == 3 for row in full["route_sets"][0]["route_fingerprints"])
    assert not full["independent_quality_evidence"]
    assert not surgical["calibrated_no_fit"]
    assert not surgical["executable_authority"]
    assert surgical["tool_call_ready"] is False
    assert "tool_definitions" in full and "tool_definitions" not in surgical
    assert result["surgical_utf8_json_bytes"] < result["full_utf8_json_bytes"]
    assert 0 < result["surgical_to_full_ratio"] < 1


def test_repeat_same_principal_query_snapshot_is_byte_deterministic():
    from scripts.research_codegraph_surgical_context_e0 import compare_contexts

    router, catalog, index = _source()
    first = compare_contexts(router, QUERY, principal=READER, catalog=catalog, index=index)
    second = compare_contexts(router, QUERY, principal=READER, catalog=catalog, index=index)
    assert first == second
    for arm in ("full_envelope", "surgical_envelope"):
        assert len(json.dumps(
            first[arm], sort_keys=True, ensure_ascii=False,
            separators=(",", ":"), allow_nan=False,
        ).encode("utf-8")) == first[
            "full_utf8_json_bytes" if arm == "full_envelope"
            else "surgical_utf8_json_bytes"
        ]


@pytest.mark.parametrize("kind,principal,status", (
    ("missing", READER, "no_proven_hit"),
    ("denied", VIEWER, "no_proven_hit"),
    ("overflow", READER, "over_k_unranked"),
))
def test_no_fit_denied_and_over_k_do_not_leak_path(
    kind: str, principal: PrincipalContext, status: str,
):
    from scripts.research_codegraph_surgical_context_e0 import compare_contexts

    router, catalog, index = _source(
        missing_input=kind == "missing",
        extra_consumers=5 if kind == "overflow" else 0,
    )
    report = compare_contexts(
        router, QUERY, principal=principal, catalog=catalog, index=index,
    )
    for key in ("full_envelope", "surgical_envelope"):
        envelope = report[key]
        assert envelope["status"] == status
        assert envelope["route_ids"] == []
        assert envelope["route_sets"] == []
        assert envelope["executable_authority"] is False
        assert "contacts.read" not in json.dumps(envelope)
        assert "cases.read" not in json.dumps(envelope)
    assert report["selected_path_parity"] is True
    assert report["token_cost"] == report["task_success"] == "NOT_MEASURED"


def test_changed_native_source_fails_closed_then_new_snapshot_is_distinct():
    from scripts.research_codegraph_surgical_context_e0 import compare_contexts

    router, catalog, old_index = _source()
    old = compare_contexts(router, QUERY, principal=READER, catalog=catalog, index=old_index)
    router.add_tool(ToolSpec(
        name="unrelated", source_type="crm", license="owner-reviewed",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    ))
    with pytest.raises(PolicyViolationError):
        compare_contexts(router, QUERY, principal=READER, catalog=catalog, index=old_index)
    current = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    new = compare_contexts(router, QUERY, principal=READER, catalog=catalog, index=current)
    assert old["full_envelope"]["index_snapshot_id"] != new["full_envelope"][
        "index_snapshot_id"
    ]
    assert old["full_envelope"]["route_ids"] == new["full_envelope"]["route_ids"]


def test_false_authority_and_quality_flags_must_be_checked_not_rewritten(monkeypatch):
    import scripts.research_codegraph_surgical_context_e0 as study

    router, catalog, index = _source()
    original = study.retrieve_authorized_concept_graph

    def unsupported_grant(*args, **kwargs):
        return replace(original(*args, **kwargs), executable_authority=True)

    monkeypatch.setattr(study, "retrieve_authorized_concept_graph", unsupported_grant)
    with pytest.raises(PolicyViolationError, match="authority"):
        study.compare_contexts(
            router, QUERY, principal=READER, catalog=catalog, index=index,
        )


@pytest.mark.parametrize("mutation", ("replace", "in_place"))
def test_policy_scope_cannot_change_between_g5_path_and_source_view(
    monkeypatch, mutation: str,
):
    import scripts.research_codegraph_surgical_context_e0 as study

    router, catalog, index = _source()
    original = study.capture_authorized_agent_tool_surface

    def change_policy_before_source_capture(*args, **kwargs):
        restricted = (DataScopeRule(
            operation="contacts.read", hidden_fields=("region_id",),
        ),)
        if mutation == "replace":
            router.authorization_policy = replace(
                router.authorization_policy, data_rules=restricted,
            )
        else:
            object.__setattr__(router.authorization_policy, "data_rules", restricted)
        return original(*args, **kwargs)

    monkeypatch.setattr(
        study, "capture_authorized_agent_tool_surface",
        change_policy_before_source_capture,
    )
    with pytest.raises(PolicyViolationError):
        study.compare_contexts(
            router, QUERY, principal=READER, catalog=catalog, index=index,
        )


def test_principal_claims_cannot_change_between_selection_and_source_view(monkeypatch):
    import scripts.research_codegraph_surgical_context_e0 as study

    router, catalog, index = _source()
    principal = PrincipalContext(subject="mutable-reader", roles=("reader",))
    original = study.capture_authorized_agent_tool_surface

    def change_principal_before_source_capture(*args, **kwargs):
        object.__setattr__(principal, "roles", ("viewer",))
        return original(*args, **kwargs)

    monkeypatch.setattr(
        study, "capture_authorized_agent_tool_surface",
        change_principal_before_source_capture,
    )
    with pytest.raises(PolicyViolationError):
        study.compare_contexts(
            router, QUERY, principal=principal, catalog=catalog, index=index,
        )


def test_cli_control_covers_paired_arms_and_provenance_without_cost_claim():
    from scripts.research_codegraph_surgical_context_e0 import run_synthetic_controls

    result = run_synthetic_controls()
    assert result["evidence_tier"] == "E0_SYNTHETIC_NONEXECUTING"
    assert result["fixed_k"] == 5
    assert result["token_cost"] == result["task_success"] == "NOT_MEASURED"
    cases = {row["case_id"]: row for row in result["cases"]}
    assert set(cases) == {"joined_en", "joined_ko", "joined_ja", "no_fit", "denied", "over_k"}
    for name in ("joined_en", "joined_ko", "joined_ja"):
        assert cases[name]["status"] == "complete"
        assert cases[name]["selected_path_parity"] is True
        assert cases[name]["surgical_utf8_json_bytes"] < cases[name]["full_utf8_json_bytes"]
    assert cases["denied"]["status"] == cases["no_fit"]["status"] == "no_proven_hit"
    assert cases["over_k"]["status"] == "over_k_unranked"

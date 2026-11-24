"""Conditional historical Rank parity and scoped public-pipeline regressions.

The comparator cohort is fixed; archived selected tools and gold labels are not
inputs. The runtime must still qualify each route under its typed/ACL contract.
"""
from __future__ import annotations

import json
from pathlib import Path

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
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperNativeRankPolicy,
    PaperUnderstanding,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.native_semantic_index import IndexedNativeFieldCandidate
from schemarouter.paper_native_rank import rank_authorized_paper_direct

SNAPSHOT = "a" * 64
ACTOR = PrincipalContext(subject="original-rank-regression")
CONCEPT = "case.status"
INTENTS = PaperIntentRegistry(intents=(
    PaperIntentDeclaration(intent_id="case.lookup", required_concept_ids=(CONCEPT,)),
))
FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "original_paper_rank_replay.json").read_text(
        encoding="utf-8",
    )
)


def _candidate(route: str, required: str = "value") -> IndexedNativeFieldCandidate:
    return IndexedNativeFieldCandidate(
        route_id=route, tool_fingerprint="t", endpoint_fingerprint="e",
        required_output_fields=(required,),
    )


def _rank(names, raw, *, priorities=None, web=(), focus=True):
    candidates = tuple(_candidate(route, fields[0]) for route, fields in names.items())
    offsets = rank_authorized_paper_direct(
        candidates, concept_aliases=(),
        visible_field_count={route: len(fields) for route, fields in names.items()},
        visible_field_names=names, raw_concepts=raw,
        policy=PaperNativeRankPolicy(
            snapshot_id=SNAPSHOT, direct_score_mode="paper_v1", focus_direct=focus,
            route_priorities=priorities or {}, web_route_ids=web,
        ),
    )
    return tuple(candidates[offset].route_id for offset in offsets)


def test_original_score_two_partial_matches_tie_one_exact_then_use_priority():
    assert _rank({
        "exact.search": ("value", "alpha"),
        "partial.search": ("value", "alpha_value", "beta_value"),
    }, ("alpha", "beta"), priorities={"partial.search": 10}) == ("partial.search",)


def test_original_raw_names_are_not_underscore_normalized():
    assert _rank({
        "collapsed.search": ("value", "spacegroup"),
        "raw.search": ("value", "space_group_number"),
    }, ("SPACE_GROUP",), priorities={"collapsed.search": 100}) == ("raw.search",)


def test_original_tie_breaks_web_priority_default_one_width_and_name():
    names = {
        "a_web.search": ("value",),
        "b_zero.search": ("value",),
        "c_wide.search": ("value", "aux"),
        "z_tie.search": ("value",),
        "d_tie.search": ("value",),
    }
    assert _rank(
        names, ("value",), priorities={"a_web.search": 100, "b_zero.search": 0},
        web=("a_web.search",), focus=False,
    ) == ("d_tie.search", "z_tie.search", "c_wide.search", "b_zero.search", "a_web.search")


def test_original_rank_rejects_missing_raw_labels_or_visible_source_names():
    policy = PaperNativeRankPolicy(snapshot_id=SNAPSHOT, direct_score_mode="paper_v1")
    with pytest.raises(ValueError, match="raw concepts"):
        rank_authorized_paper_direct(
            (_candidate("a.search"),), concept_aliases=(),
            visible_field_count={"a.search": 1}, policy=policy,
        )


def test_historical_comparator_replay_covers_all_nontrivial_frozen_label_patterns():
    assert FIXTURE["original_query_count"] == 110
    assert len(FIXTURE["apis"]) == 19
    assert sum(len(case["query_ids"]) for case in FIXTURE["cases"]) == 91
    for case in FIXTURE["cases"]:
        apis = [FIXTURE["apis"][name] for name in case["eligible_tools"]]
        names = {f"{api['name']}.search": tuple(api["fields"]) for api in apis}
        actual = _rank(
            names, tuple(case["concepts"]),
            priorities={f"{api['name']}.search": api["priority"] for api in apis},
            web=tuple(f"{api['name']}.search" for api in apis if api["domain"] == "web"),
        )
        assert actual == (f"{case['reference_winner']}.search",), case["query_ids"]


def _session():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="allow",
        rules=(AuthorizationRule(effect="deny", operation="denied.search"),),
        data_rules=(DataScopeRule(operation="hidden.search", hidden_fields=("case_status",)),),
    ))
    for name, extra in (
        ("visible", "case_status_value"), ("hidden", "case_status"),
        ("denied", "case_status"), ("incomplete", "case_status"),
    ):
        fields = [] if name == "incomplete" else [
            FieldSpec(name="value", semantic_id=CONCEPT, json_schema={"type": "string"}),
        ]
        fields.append(FieldSpec(
            name=extra, semantic_id=f"{name}.extra", json_schema={"type": "string"},
        ))
        router.add_tool(ToolSpec(
            name=name, source_type="crm", license="reviewed",
            endpoints=[EndpointSpec(name="search", read_only=True, output_fields=fields)],
        ))
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id=CONCEPT, aliases=("case_status",),
        required_fields=(CapabilityFieldContract(
            semantic_id=CONCEPT, json_schema={"type": "string"},
        ),),
        source_type="crm", license="reviewed",
    ),))
    session = router.prepare_field_routing(catalog=catalog)
    policy = PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id, direct_score_mode="paper_v1", focus_direct=True,
        route_priorities={"hidden.search": 100, "denied.search": 100,
                          "incomplete.search": 100},
    )
    return session, policy


def test_original_rank_uses_visible_nonprojected_names_only_after_typed_and_acl_proof():
    session, policy = _session()
    understood = PaperUnderstanding(
        intent_id="case.lookup", concept_ids=(CONCEPT,), raw_rank_concepts=("case_status",),
    )
    plan = session.compile_understood(
        understood, principal=ACTOR, intent_registry=INTENTS, rank_policy=policy,
    )
    assert plan.status == "ready" and not plan.executable_authority
    assert [call.route_id for call in plan.calls] == ["visible.search"]
    # The raw hint can rank, but cannot add a field to the typed plan.
    assert plan.calls[0].call.fields == ["value"]
    typed = session.compile_understood(
        understood, principal=ACTOR, intent_registry=INTENTS,
        rank_policy=policy.model_copy(update={"direct_score_mode": "typed"}),
    )
    assert [call.route_id for call in typed.calls] == ["hidden.search"]


def test_original_rank_structured_hints_require_explicit_raw_labels():
    session, policy = _session()
    with pytest.raises(ValueError, match="raw concepts"):
        session.compile_understood(
            PaperUnderstanding(intent_id="case.lookup", concept_ids=(CONCEPT,)),
            principal=ACTOR, intent_registry=INTENTS, rank_policy=policy,
        )


@pytest.mark.asyncio
async def test_original_rank_schema_independent_query_carries_raw_labels_to_comparator():
    session, policy = _session()
    observed = []

    def model(payload):
        observed.append(payload)
        return {"intent_id": "case.lookup", "needs": [{"concept": "case_status"}]}

    plan = await session.acompile_query(
        "show case status", principal=ACTOR, intent_registry=INTENTS,
        model=model, model_visible_intent_ids=("case.lookup",), rank_policy=policy,
    )
    assert len(observed) == 1
    assert "offered_concepts" not in observed[0] and "schema_catalog" not in observed[0]
    assert plan.status == "ready" and not plan.executable_authority
    assert [call.route_id for call in plan.calls] == ["visible.search"]
    assert plan.calls[0].call.fields == ["value"]


@pytest.mark.asyncio
async def test_original_rank_refuses_legacy_offered_id_protocol_before_model_disclosure():
    session, policy = _session()
    with pytest.raises(ValueError, match="schema-independent"):
        await session.acompile_query(
            "show case status", principal=ACTOR, intent_registry=INTENTS,
            model=lambda _: pytest.fail("model invoked before Rank protocol preflight"),
            model_visible_intent_ids=("case.lookup",), model_visible_concept_ids=(CONCEPT,),
            rank_policy=policy,
        )

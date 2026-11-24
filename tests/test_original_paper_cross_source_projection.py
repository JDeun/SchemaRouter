"""Replay the original cross-source field-group projection, not model quality.

The query's understood concept and two named sources are fixed historical
inputs. The archived outputs are assertion-only, not a routing oracle.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemarouter import (
    AuthorizationPolicy,
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
from schemarouter.errors import PolicyViolationError

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "original_paper_cross_source_projection.json").read_text(
        encoding="utf-8",
    )
)
ACTOR = PrincipalContext(subject="historical-cross-source-replay")
TYPES = {"string": "string", "integer": "integer", "float": "number", "boolean": "boolean"}
MP = "materials_project.search"
OQMD = "oqmd.search"
TOOLS = ("materials_project", "oqmd")
CONCEPT = "material.band_gap"


def _build(*, hidden: tuple[str, ...] = ()):
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="allow",
        data_rules=(DataScopeRule(operation=MP, hidden_fields=hidden),) if hidden else (),
    ))
    groups = {}
    for api in FIXTURE["apis"]:
        fields = [FieldSpec(
            name=raw["name"],
            semantic_id=(CONCEPT if raw["name"] == "band_gap"
                         else f"{api['name']}.{raw['name']}"),
            json_schema={"type": TYPES[raw["type"]]},
            identifier=raw["is_identifier"], unit=raw["unit"],
        ) for raw in api["fields"]]
        router.add_tool(ToolSpec(
            name=api["name"], source_type=api["source_type"], license=api["license"],
            endpoints=[EndpointSpec(name="search", read_only=True, output_fields=fields)],
        ))
        groups[f"{api['name']}.search"] = {
            group["name"]: tuple(group["field_names"])
            for group in api["field_groups"]
        }

    # Shared concept only: the original inventory declares equivalent band_gap
    # fields with the same unit. Other fields remain source-local, not presumed
    # semantically interchangeable.
    catalog = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
        concept_id=CONCEPT, aliases=("band_gap", "band gap"),
        required_fields=(CapabilityFieldContract(
            semantic_id=CONCEPT, json_schema={"type": "number"}, unit="eV",
        ),), source_type="calculated",
    ),))
    session = router.prepare_field_routing(catalog=catalog)
    original_intent = FIXTURE["intent"]
    intent = PaperIntentDeclaration(
        intent_id=original_intent["name"], required_concept_ids=(CONCEPT,),
        recall_group_ids=tuple(original_intent["required_groups"]),
        domains=tuple(original_intent["applicable_domains"]),
    )
    intents = PaperIntentRegistry(
        intents=(intent,), projection_snapshot_id=session.snapshot_id,
        route_field_groups=groups,
    )
    return session, intents


def _rank_policy(session):
    # Domains are trusted source annotations, not model-generated metadata.
    return PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id,
        route_domains={
            f"{api['name']}.search": (api["domain"],) for api in FIXTURE["apis"]
        },
    )


def _compile(session, intents):
    return session.compile_understood(
        PaperUnderstanding(intent_id=FIXTURE["intent"]["name"],
                           concept_ids=(CONCEPT,), named_tools=TOOLS),
        principal=ACTOR, intent_registry=intents, rank_policy=_rank_policy(session),
    )


@pytest.fixture(scope="module")
def replay():
    return _build()


def test_original_cross_source_fixture_scope():
    assert FIXTURE["provenance"]["original_query_count"] == 110
    assert len(FIXTURE["cases"]) == 8
    assert {case["query_id"] for case in FIXTURE["cases"]} == {
        f"g{i:03d}" for i in range(69, 77)
    }


@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda case: case["query_id"])
def test_original_cross_source_projection(case, replay):
    session, intents = replay
    plan = _compile(session, intents)
    assert plan.status == "ready" and not plan.executable_authority
    assert len(plan.calls) == 2
    calls = {call.call.tool: call for call in plan.calls}
    assert set(calls) == set(TOOLS)
    for expected in case["expected"]:
        tool = expected["tool"]
        call = calls[tool]
        assert set(call.call.fields) == set(expected["fields"])
        assert len(call.call.fields) == len(set(call.call.fields))
        assert call.source_type == expected["evidence_requirements"]["source_type"]
        assert call.license == expected["evidence_requirements"]["license"]
        fields = {
            raw["name"]: raw for api in FIXTURE["apis"]
            if api["name"] == tool for raw in api["fields"]
        }
        assert {meta.name for meta in call.fields_meta} == set(expected["fields"])
        for meta in call.fields_meta:
            assert meta.unit == fields[meta.name]["unit"]
            assert meta.license == call.license


def test_recall_group_projection_does_not_change_mandatory_semantic_proof(replay):
    session, intents = replay
    original = intents.intents[0]
    bare = PaperIntentRegistry(intents=(original.model_copy(update={"recall_group_ids": ()}),))
    plan = _compile(session, bare)
    assert plan.status == "ready"
    assert {call.route_id: set(call.call.fields) for call in plan.calls} == {
        MP: {"material_id", "formula_pretty", "band_gap"},
        OQMD: {"entry_id", "name", "band_gap"},
    }


def test_matched_group_expands_without_recursively_expanding_adjuncts(replay):
    session, intents = replay
    groups = {route: dict(value) for route, value in intents.route_field_groups.items()}
    groups[MP]["overlap"] = ("is_gap_direct", "k_vrh")
    narrower = intents.model_copy(update={
        "intents": (intents.intents[0].model_copy(update={"recall_group_ids": ()}),),
        "route_field_groups": groups,
    })
    plan = _compile(session, narrower)
    assert plan.status == "ready"
    assert {call.route_id: set(call.call.fields) for call in plan.calls} == {
        MP: {"material_id", "formula_pretty", "band_gap", "is_gap_direct",
             "is_metal", "efermi"},
        OQMD: {"entry_id", "name", "band_gap"},
    }


def test_hidden_recall_adjunct_is_not_returned():
    session, intents = _build(hidden=("is_gap_direct",))
    plan = _compile(session, intents)
    assert plan.status == "ready" and not plan.executable_authority
    call = next(call for call in plan.calls if call.route_id == MP)
    assert "is_gap_direct" not in call.call.fields
    assert "is_gap_direct" not in {meta.name for meta in call.fields_meta}
    assert "band_gap" in call.call.fields


def test_projection_snapshot_must_match(replay):
    session, intents = replay
    stale = intents.model_copy(update={"projection_snapshot_id": "a" * 64})
    with pytest.raises(PolicyViolationError):
        _compile(session, stale)


def test_recall_group_cannot_invent_a_source_field(replay):
    session, intents = replay
    groups = {route: dict(value) for route, value in intents.route_field_groups.items()}
    groups[MP]["electronic"] += ("invented_field",)
    invalid = intents.model_copy(update={"route_field_groups": groups})
    with pytest.raises(PolicyViolationError):
        _compile(session, invalid)


@pytest.mark.asyncio
async def test_original_cross_source_schema_independent_model_boundary(replay):
    session, intents = replay
    case = FIXTURE["cases"][0]
    seen = []

    def model(payload):
        seen.append(payload)
        return {
            "intent_id": case["intent"],
            "needs": [{"concept": "band_gap"}],
            "named_tools": ["Materials Project", "OQMD"],
        }

    plan = await session.acompile_query(
        case["query"], principal=ACTOR, intent_registry=intents,
        model=model, model_visible_intent_ids=(case["intent"],),
        rank_policy=_rank_policy(session),
    )
    assert len(seen) == 1
    assert "schema_catalog" not in seen[0] and "offered_concepts" not in seen[0]
    assert plan.status == "ready" and not plan.executable_authority
    assert {call.call.tool: set(call.call.fields) for call in plan.calls} == {
        expected["tool"]: set(expected["fields"]) for expected in case["expected"]
    }

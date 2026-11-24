"""Historical conditional field projection replay, not a routing accuracy benchmark.

The original selected source and Understand intent/concept labels are fixed
inputs. The archived selected fields are assertion-only, never used to build
the current source schema or owner mappings. No gold labels, LLM or data
provider are called. The source fixture omits parameters intentionally.
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

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "original_paper_mp_projection.json").read_text(
        encoding="utf-8",
    )
)
API = FIXTURE["api"]
CASES = FIXTURE["cases"]
ACTOR = PrincipalContext(subject="historical-projection-replay")
TYPES = {"string": "string", "integer": "integer", "float": "number", "boolean": "boolean"}
ROUTE = "materials_project.search"


def _normalize(label: str) -> str:
    return label.strip().lower().replace("_", "").replace(" ", "").replace("-", "")


def _build(*, hidden: tuple[str, ...] = ()):
    """Translate the source-owned inventory, independently of recorded plan outputs."""
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="allow",
        data_rules=(DataScopeRule(
            operation=ROUTE, hidden_fields=hidden,
        ),) if hidden else (),
    ))
    fields = {
        raw["name"]: FieldSpec(
            name=raw["name"],
            semantic_id=f"materials_project.{raw['name']}",
            json_schema={"type": TYPES[raw["type"]]},
            identifier=raw["is_identifier"],
            unit=raw["unit"],
        )
        for raw in API["fields"]
    }
    source_fields = {raw["name"]: raw for raw in API["fields"]}
    concepts = []
    alias_to_concept: dict[str, str] = {}
    group_to_concept: dict[str, str] = {}
    for group in API["field_groups"]:
        if group["name"] == "identifier":
            continue
        concept_id = f"paper.mp.{group['name']}"
        group_to_concept[group["name"]] = concept_id
        aliases = [group["name"]]
        required_fields = []
        for name in group["field_names"]:
            raw = source_fields[name]
            aliases.extend([name, *raw["aliases"]])
            aliases.extend(item["field_name"] for item in raw["equivalent_to"])
            contract = CapabilityFieldContract.from_field(fields[name])
            assert contract is not None
            required_fields.append(contract)
        # Owner-reviewed group mapping from the inventory; do not infer missing aliases.
        unique_aliases = {}
        for alias in aliases:
            if len(alias) >= 2:
                unique_aliases.setdefault(alias.casefold(), alias)
        for alias in unique_aliases.values():
            normalized = _normalize(alias)
            if normalized in alias_to_concept:
                assert alias_to_concept[normalized] == concept_id
            alias_to_concept[normalized] = concept_id
        concepts.append(NativeDeclaredConcept(
            concept_id=concept_id,
            aliases=tuple(unique_aliases.values()),
            required_fields=tuple(required_fields),
            source_type=API["source_type"],
            license=API["license"],
        ))

    router.add_tool(ToolSpec(
        name=API["name"],
        source_type=API["source_type"],
        license=API["license"],
        endpoints=[EndpointSpec(
            name="search", read_only=True, output_fields=list(fields.values()),
        )],
    ))
    catalog = NativeConceptCatalog(concepts=tuple(concepts))
    intents = PaperIntentRegistry(intents=tuple(
        PaperIntentDeclaration(
            intent_id=raw["name"],
            required_concept_ids=tuple(
                group_to_concept[name] for name in raw["required_groups"]
            ),
            domains=tuple(raw["applicable_domains"]),
        )
        for raw in FIXTURE["intents"]
    ))
    session = router.prepare_field_routing(catalog=catalog)
    policy = PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id,
        route_domains={ROUTE: (API["domain"],)},
    )
    return session, intents, policy, alias_to_concept


def _hints(case, aliases):
    known, unresolved = [], []
    for label in case["concepts"]:
        concept = aliases.get(_normalize(label))
        if concept is None:
            unresolved.append(label)
        else:
            known.append(concept)
    return PaperUnderstanding(
        intent_id=case["intent"],
        concept_ids=tuple(dict.fromkeys(known)),
        unresolved_concepts=tuple(dict.fromkeys(unresolved)),
        named_tools=(API["name"],),
    )


@pytest.fixture(scope="module")
def replay():
    return _build()


def test_original_fixture_scope_and_unmapped_concepts_are_visible(replay):
    assert FIXTURE["provenance"]["source_total_queries"] == 110
    assert len(CASES) == 59
    assert len(API["fields"]) == 22
    assert len({case["query_id"] for case in CASES}) == len(CASES)
    aliases = replay[3]
    unmapped = {
        case["query_id"]: _hints(case, aliases).unresolved_concepts
        for case in CASES if _hints(case, aliases).unresolved_concepts
    }
    assert unmapped == {
        "g038": ("elastic_modulus",),
        "g039": ("magnetic_property",),
        "g043": ("elastic_modulus",),
        "g045": ("lattice_parameters",),
        "g092": ("elastic_modulus",),
        "g097": ("decomposition_energy",),
    }


@pytest.mark.parametrize("case", CASES, ids=[case["query_id"] for case in CASES])
def test_historical_field_projection(case, replay):
    session, intents, policy, aliases = replay
    hints = _hints(case, aliases)
    plan = session.compile_understood(
        hints, principal=ACTOR, intent_registry=intents, rank_policy=policy,
    )
    assert not plan.executable_authority
    if hints.unresolved_concepts:
        # Historical fallback fields must not certify an unresolved concept.
        assert plan.status == "no_proven_hit"
        assert plan.coverage is not None and not plan.coverage.complete
        for label in hints.unresolved_concepts:
            assert any(
                f"query_concept={label}" in item.qualifiers
                for item in plan.coverage.uncovered
            )
        return
    assert plan.status == "ready"
    assert [call.route_id for call in plan.calls] == [ROUTE]
    call = plan.calls[0]
    assert len(call.call.fields) == len(set(call.call.fields))
    assert set(call.call.fields) == set(case["expected_fields"])
    assert call.source_type == case["evidence"]["source_type"]
    assert call.license == case["evidence"]["license"]
    fields = {field["name"]: field for field in API["fields"]}
    assert {meta.name for meta in call.fields_meta} == set(case["expected_fields"])
    for meta in call.fields_meta:
        assert meta.unit == fields[meta.name]["unit"]
        assert meta.source_type == API["source_type"]
        assert meta.license == API["license"]


def test_original_group_cannot_be_certified_with_hidden_member():
    session, intents, policy, aliases = _build(hidden=("is_gap_direct",))
    case = next(case for case in CASES if case["query_id"] == "g001")
    plan = session.compile_understood(
        _hints(case, aliases), principal=ACTOR,
        intent_registry=intents, rank_policy=policy,
    )
    assert plan.status == "no_proven_hit"
    assert not plan.executable_authority
    assert all("is_gap_direct" not in call.call.fields for call in plan.calls)


@pytest.mark.asyncio
async def test_original_band_gap_schema_independent_understanding_smoke(replay):
    session, intents, policy, _aliases = replay
    observed = []

    def model(payload):
        observed.append(payload)
        return {
            "intent_id": "find_band_gap",
            "needs": [{"concept": "band_gap"}],
            "named_tools": ["Materials Project"],
        }

    plan = await session.acompile_query(
        FIXTURE["model_smoke"]["query"],
        principal=ACTOR,
        model=model,
        intent_registry=intents,
        model_visible_intent_ids=tuple(intent.intent_id for intent in intents.intents),
        rank_policy=policy,
    )
    assert len(observed) == 1
    assert "schema_catalog" not in observed[0]
    assert "offered_concepts" not in observed[0]
    assert plan.status == "ready"
    assert not plan.executable_authority
    assert len(plan.calls) == 1 and plan.calls[0].route_id == ROUTE
    expected = next(case["expected_fields"] for case in CASES if case["query_id"] == "g001")
    assert set(plan.calls[0].call.fields) == set(expected)

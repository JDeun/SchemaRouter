"""Historical literature projection and input/output role separation (E0).

Keep the real frozen arXiv parameter envelope, including optional parameters.
The callback is a controlled, separately authored Understand result, not a
live-model replay. No host argument or provider call is fabricated.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from schemarouter import (
    AuthorizationPolicy,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PaperIntentDeclaration,
    PaperIntentRegistry,
    PaperNativeRankPolicy,
    ParameterSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from schemarouter.errors import PolicyViolationError

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "original_paper_arxiv_input_output.json").read_text(
        encoding="utf-8",
    )
)
API = FIXTURE["api"]
ACTOR = PrincipalContext(subject="historical-literature-input-output")
ROUTE = "arxiv.search"
INTENT = "find_paper"
PAPER = "literature.record"
TYPES = {
    "string": {"type": "string"},
    "datetime": {"type": "string", "format": "date-time"},
    "list[str]": {"type": "array", "items": {"type": "string"}},
    "str": {"type": "string"},
    "int": {"type": "integer"},
}


def _session(*, aliases=True, value_alias=None, approve_direct=False):
    # Source-owned review: the frozen inventory describes summary as abstract
    # text, published as first submission date, and search_query as search
    # input. These are explicit test-host declarations, not guessed mappings
    # from the historical answer or output plan.
    fields = {
        raw["name"]: FieldSpec(
            name=raw["name"], semantic_id=f"arxiv.{raw['name']}",
            json_schema=TYPES[raw["type"]], identifier=raw["is_identifier"],
            unit=raw["unit"],
        )
        for raw in API["fields"]
    }
    parameters = []
    for raw in API["parameters"]:
        name = raw["name"]
        schema = dict(TYPES[raw["type"]])
        if name == "sortBy":
            # Exact tokens are specified in the original inventory description.
            # Natural-language "latest" is not a native wire token.
            schema["enum"] = ["relevance", "lastUpdatedDate", "submittedDate"]
        parameter_aliases = {
            "search_query": ["search topic", "search query"],
            "sortBy": ["sort order"],
        }.get(name, []) if aliases else []
        parameters.append(ParameterSpec(
            name=name, required=raw["required"], json_schema=schema,
            aliases=parameter_aliases,
        ))

    router = SchemaRouter(authorization_policy=AuthorizationPolicy(default_effect="allow"))
    router.add_tool(ToolSpec(
        name=API["name"], source_type=API["source_type"], license=API["license"],
        endpoints=[EndpointSpec(
            name="search", read_only=True, output_fields=list(fields.values()),
            parameters=parameters,
            input_schema={
                "type": "object",
                "properties": {parameter.name: parameter.json_schema for parameter in parameters},
                "required": [parameter.name for parameter in parameters if parameter.required],
                "additionalProperties": False,
            },
        )],
    ))
    meanings = (
        (PAPER, ("research papers", "paper records"), ("title", "summary")),
        ("literature.title", ("paper title", "title"), ("title",)),
        ("literature.abstract", ("abstract", "summary"), ("summary",)),
        ("literature.authors", ("authors",), ("authors",)),
        ("literature.publication_date", ("publication date", "publication_date"),
         ("published",)),
    )
    concepts = []
    for cid, names, members in meanings:
        contracts = []
        for name in members:
            contract = CapabilityFieldContract.from_field(fields[name])
            assert contract is not None
            contracts.append(contract)
        concepts.append(NativeDeclaredConcept(
            concept_id=cid, aliases=names, required_fields=tuple(contracts),
            source_type=API["source_type"], license=API["license"],
        ))
    session = router.prepare_field_routing(catalog=NativeConceptCatalog(concepts=tuple(concepts)))
    intent = FIXTURE["intent"]
    intents = PaperIntentRegistry(
        intents=(PaperIntentDeclaration(
            intent_id=intent["name"], required_concept_ids=(PAPER,),
            recall_group_ids=tuple(intent["required_groups"]),
            domains=tuple(intent["applicable_domains"]),
        ),),
        projection_snapshot_id=session.snapshot_id,
        route_parameter_value_aliases=(
            {ROUTE: {"sortBy": {"latest": value_alias}}} if value_alias is not None else {}
        ),
        approved_direct_parameter_routes=(ROUTE,) if approve_direct else (),
        route_field_groups={ROUTE: {
            group["name"]: tuple(group["field_names"]) for group in API["field_groups"]
        }},
    )
    policy = PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id, route_domains={ROUTE: (API["domain"],)},
        route_priorities={ROUTE: API["priority"]}, direct_score_mode="paper_v1", focus_direct=True,
    )
    return session, intents, policy


def _response(topic, *, sort="latest", additional_needs=()):
    # Authored from the query's roles, NOT its archived tool selection.
    return {
        "intent_id": INTENT,
        "needs": [{"concept": "research papers"}, *additional_needs],
        "named_tools": ["arXiv"],
        "parameter_hints": {"search topic": topic, "sort order": sort},
    }


async def _query(query, response, *, aliases=True, value_alias=None,
                 approve_direct=False, host=None):
    session, intents, policy = _session(
        aliases=aliases, value_alias=value_alias, approve_direct=approve_direct,
    )
    observed = []

    def model(payload):
        observed.append(payload)
        return response

    plan = await session.acompile_query(
        query, principal=ACTOR, model=model, intent_registry=intents,
        model_visible_intent_ids=(INTENT,), rank_policy=policy,
        host_source_arguments={ROUTE: host} if host is not None else None,
    )
    assert len(observed) == 1
    return plan, observed[0]


def _input_conditions(plan, *, covered):
    items = plan.coverage.covered if covered else plan.coverage.uncovered
    return {item.semantic_id: item.qualifiers for item in items
            if "query_input_condition=true" in item.qualifiers}


def test_frozen_literature_fixture_preserves_missing_original_input_evidence():
    assert len(FIXTURE["cases"]) == 10
    assert {case["query_id"] for case in FIXTURE["cases"]} == {
        f"g{i:03d}" for i in range(59, 69)
    }
    assert all(case["historical_parameters"] == {} for case in FIXTURE["cases"])
    assert {p["name"] for p in API["parameters"] if p["required"]} == {"search_query"}


@pytest.mark.asyncio
@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda case: case["query_id"])
async def test_historical_topic_is_input_not_output_and_latest_remains_unproven(case):
    plan, payload = await _query(case["query"], _response(case["topic"]))
    assert "offered_concepts" not in payload and "schema_catalog" not in payload
    assert any("search subject is not itself" in rule for rule in payload["rules"])
    assert any("latest is an ordering condition" in rule for rule in payload["rules"])
    assert plan.status == "requires_arguments" and not plan.executable_authority
    assert plan.coverage is not None and not plan.coverage.complete
    assert [call.route_id for call in plan.calls] == [ROUTE]
    call = plan.calls[0]
    assert set(call.call.fields) == set(case["historical_fields"])
    assert call.call.arguments == {}
    assert call.call.missing_required_arguments == ["search_query"]
    assert dict(call.parameter_proposals) == {"search_query": case["topic"]}
    assert call.source_type == case["evidence_requirements"]["source_type"]
    assert call.license == case["evidence_requirements"]["license"]
    assert "proof=pending_host_input" in _input_conditions(plan, covered=True)["search topic"]
    assert "proof=invalid_proposed_input" in _input_conditions(plan, covered=False)["sort order"]
    assert not any(item.semantic_id == case["topic"] for item in plan.coverage.required)
    assert plan.understanding_hints["parameter_hints"]["search topic"] == case["topic"]


@pytest.mark.asyncio
async def test_explicit_native_sort_value_proves_input_shape_but_never_binds():
    query = "Find arXiv papers on graphene with sortBy=submittedDate."
    response = _response("graphene", sort="submittedDate", additional_needs=(
        {"concept": "abstract"}, {"concept": "publication date"},
    ))
    # Preserve an explicitly named native parameter exactly.
    response["parameter_hints"]["sortBy"] = response["parameter_hints"].pop("sort order")
    plan, _ = await _query(query, response)
    assert plan.status == "requires_arguments" and plan.coverage.complete
    assert not plan.executable_authority
    assert plan.calls[0].call.arguments == {}
    assert plan.calls[0].call.missing_required_arguments == ["search_query"]
    assert {"search topic", "sortBy"} == set(_input_conditions(plan, covered=True))
    assert dict(plan.calls[0].parameter_proposals) == {
        "search_query": "graphene", "sortBy": "submittedDate",
    }


@pytest.mark.asyncio
async def test_missing_owner_input_alias_cannot_be_inferred_from_a_search_goal():
    plan, _ = await _query(
        "Find arXiv papers about graphene.",
        {"intent_id": INTENT, "needs": [{"concept": "research papers"}],
         "named_tools": ["arXiv"], "parameter_hints": {"search topic": "graphene"}},
        aliases=False,
    )
    assert not plan.coverage.complete and not plan.executable_authority
    assert "proof=unproven_source_relation" in _input_conditions(
        plan, covered=False,
    )["search topic"]
    assert plan.calls[0].call.arguments == {}


@pytest.mark.asyncio
async def test_explicit_unsupported_output_is_not_silently_reclassified_as_input():
    plan, _ = await _query(
        "Find arXiv papers about graphene and return their keywords.",
        {"intent_id": INTENT,
         "needs": [{"concept": "research papers"}, {"concept": "keywords"}],
         "named_tools": ["arXiv"], "parameter_hints": {"search topic": "graphene"}},
    )
    assert not plan.coverage.complete and not plan.executable_authority
    assert any(item.semantic_id == "keywords" for item in plan.coverage.uncovered)
    assert all("keywords" not in call.call.fields for call in plan.calls)


@pytest.mark.asyncio
async def test_input_only_model_response_does_not_certify_a_retrieval_goal():
    plan, _ = await _query(
        "Find arXiv papers about graphene.",
        {"intent_id": INTENT, "needs": [], "named_tools": ["arXiv"],
         "parameter_hints": {"search topic": "graphene"}},
    )
    assert plan.status == "no_proven_hit" and not plan.coverage.complete
    assert not plan.calls and not plan.executable_authority



@pytest.mark.asyncio
@pytest.mark.parametrize("case", FIXTURE["cases"], ids=lambda case: case["query_id"])
async def test_owner_reviewed_native_parameter_projection(case):
    plan, payload = await _query(
        case["query"], _response(case["topic"]), value_alias="submittedDate",
    )
    assert "route_parameter_value_aliases" not in payload
    assert plan.status == "requires_arguments" and plan.coverage.complete
    assert not plan.executable_authority
    call = plan.calls[0]
    assert dict(call.parameter_proposals) == {
        "search_query": case["topic"], "sortBy": "submittedDate",
    }
    assert call.call.arguments == {}
    assert plan.understanding_hints["parameter_hints"]["sort order"] == "latest"


@pytest.mark.asyncio
async def test_explicit_host_approval_binds_required_and_optional_direct_scalars():
    host = {"search_query": "graphene", "sortBy": "submittedDate"}
    plan, _ = await _query(
        "Find latest arXiv papers on graphene.", _response("graphene"),
        value_alias="submittedDate", approve_direct=True, host=host,
    )
    assert plan.status == "ready" and plan.coverage.complete
    assert not plan.executable_authority and not plan.bindings
    assert plan.calls[0].call.arguments == host
    assert plan.calls[0].call.missing_required_arguments == []
    assert plan.calls[0].parameter_proposals == ()
    assert all("proof=matching_host_input" in qualifiers for qualifiers in
               _input_conditions(plan, covered=True).values())


@pytest.mark.asyncio
async def test_optional_direct_binding_requires_separate_owner_approval():
    with pytest.raises(PolicyViolationError):
        await _query(
            "Find arXiv papers on graphene.", _response("graphene", sort="submittedDate"),
            host={"search_query": "graphene", "sortBy": "submittedDate"},
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("host", [
    {"sortBy": "submittedDate"},
    {"search_query": "graphene", "sortBy": "not-a-native-enum"},
    {"search_query": "graphene", "unknown_parameter": "value"},
    {"search_query": "graphene", "id_list": ["1234"]},
    {"search_query": True, "sortBy": "submittedDate"},
])
async def test_direct_input_approval_never_weakens_native_schema(host):
    with pytest.raises(PolicyViolationError):
        await _query(
            "Find latest arXiv papers on graphene.", _response("graphene"),
            approve_direct=True, value_alias="submittedDate", host=host,
        )


@pytest.mark.asyncio
async def test_owner_alias_must_resolve_to_a_real_native_enum_token():
    with pytest.raises(PolicyViolationError):
        await _query(
            "Find latest arXiv papers on graphene.", _response("graphene"),
            value_alias="invented-sort-token",
        )


@pytest.mark.asyncio
async def test_contradictory_parameter_aliases_produce_no_conflicting_proposal():
    response = _response("graphene")
    response["parameter_hints"]["sortBy"] = "relevance"
    plan, _ = await _query(
        "Find latest arXiv papers on graphene, sortBy=relevance.", response,
        value_alias="submittedDate",
    )
    assert not plan.coverage.complete and not plan.executable_authority
    assert dict(plan.calls[0].parameter_proposals) == {"search_query": "graphene"}
    assert "proof=conflicting_query_input" in _input_conditions(plan, covered=False)["sort order"]


@pytest.mark.asyncio
async def test_stale_owner_parameter_annotations_reject_before_model_callback():
    session, intents, policy = _session(value_alias="submittedDate", approve_direct=True)
    stale = intents.model_copy(update={"projection_snapshot_id": "a" * 64})
    with pytest.raises(PolicyViolationError, match="intent source preflight"):
        await session.acompile_query(
            "Find latest arXiv papers on graphene.", principal=ACTOR,
            model=lambda _: pytest.fail("stale owner annotation reached model"),
            intent_registry=stale, model_visible_intent_ids=(INTENT,), rank_policy=policy,
        )


@pytest.mark.asyncio
async def test_direct_parameter_declaration_cannot_expand_g5_host_root_eligibility():
    session, _, _ = _session(approve_direct=True)
    # The source has optional/array inputs. Its separate direct approval never
    # becomes a G5 source root or a legacy direct execution permission.
    assert ROUTE not in session._index.approved_host_roots
    with pytest.raises((PolicyViolationError, ValueError)):
        session.revise_catalog(
            catalog=session._require_catalog(), approved_host_roots=frozenset({ROUTE}),
        )

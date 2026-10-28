"""#1777: host-scoped model Understand(q) is wired to schema-only plans."""
from __future__ import annotations

import json

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    NativeConceptCatalog,
    NativeDeclaredConcept,
    PaperIntentDeclaration,
    PaperIntentRegistry,
)
from schemarouter.errors import ModelAnalysisError, PolicyViolationError
from scripts.benchmark_native_fork_fieldgroup_e0 import (
    ACTOR,
    RIGHT,
    ROOT,
    build_fixture,
)

CATALOG = NativeConceptCatalog(concepts=(NativeDeclaredConcept(
    concept_id="crm.owner", aliases=("customer owner", "고객 담당자", "顧客担当者"),
    source_type="crm", license="host-reviewed-synthetic",
    required_fields=(CapabilityFieldContract(
        semantic_id="crm.fork_owner", json_schema={"type": "string"},
    ),),
),))
INTENTS = PaperIntentRegistry(intents=(PaperIntentDeclaration(
    intent_id="crm.owner_lookup", required_concept_ids=("crm.owner",),
),))


@pytest.mark.asyncio
@pytest.mark.parametrize("query", [
    "Who owns customer twelve?", "고객 열둘의 담당자를 알려줘", "顧客12の担当者は誰ですか",
])
async def test_model_query_routes_multilingual_paraphrase_without_data_io(query):
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=CATALOG)
    observed = []

    async def model(payload):
        observed.append(payload)
        return json.dumps({
            "intent_id": "crm.owner_lookup",
            "concept_ids": ["crm.owner"],
            "named_tools": ["fork_owner"],
            "parameter_hints": {"customer_id": "MODEL_FORGED"},
        })

    plan = await session.acompile_query(
        query, principal=ACTOR, model=model, intent_registry=INTENTS,
        model_visible_intent_ids=("crm.owner_lookup",),
        model_visible_concept_ids=("crm.owner",),
        model_visible_tool_keys=("fork_owner",),
    )
    assert plan.status == "requires_observation"
    assert [item.route_id for item in plan.calls] == [ROOT, RIGHT]
    assert [item.call.arguments for item in plan.calls] == [{}, {}]
    assert plan.executable_authority is False
    assert len(observed) == 1
    assert observed[0]["query"] == query
    assert observed[0]["offered_tool_keys"] == ["fork_owner"]
    assert "host_source_arguments" not in observed[0]
    assert "output_fields" not in json.dumps(observed[0])


@pytest.mark.asyncio
async def test_model_query_uses_approved_root_arguments_only():
    session = build_fixture(500).prepare_field_routing(
        catalog=CATALOG, approved_host_roots=frozenset({RIGHT}),
    )

    def model(_payload):
        return {"intent_id": "crm.owner_lookup", "concept_ids": [],
                "named_tools": ["fork_owner"],
                "parameter_hints": {"customer_id": "FORGED"}}

    result = await session.acompile_query(
        "get owner", principal=ACTOR, model=model, intent_registry=INTENTS,
        model_visible_intent_ids=("crm.owner_lookup",),
        model_visible_concept_ids=("crm.owner",),
        model_visible_tool_keys=("fork_owner",),
        host_source_arguments={RIGHT: {"customer_id": "HOST"}},
    )
    assert result.status == "ready"
    assert [c.call.arguments for c in result.calls] == [{"customer_id": "HOST"}]


@pytest.mark.asyncio
async def test_model_query_with_no_live_proof_does_not_invoke_model():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=CATALOG)
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")

    def model(_payload):
        pytest.fail("model must never see hidden/unproved concepts")

    plan = await session.acompile_query(
        "owner", principal=ACTOR, model=model, intent_registry=INTENTS,
        model_visible_intent_ids=("crm.owner_lookup",),
        model_visible_concept_ids=("crm.owner",),
    )
    assert plan.status == "no_proven_hit"
    assert plan.calls == ()


@pytest.mark.asyncio
async def test_model_query_rejects_unreviewed_or_non_scoped_identity():
    session = build_fixture(500).prepare_field_routing(catalog=CATALOG)

    with pytest.raises(ValueError, match="disclosure"):
        await session.acompile_query(
            "owner", principal=ACTOR, model=lambda _: {}, intent_registry=INTENTS,
            model_visible_intent_ids=("unknown",),
            model_visible_concept_ids=("crm.owner",),
        )
    with pytest.raises(ValueError, match="disclosure"):
        await session.acompile_query(
            "owner", principal=ACTOR, model=lambda _: {}, intent_registry=INTENTS,
            model_visible_intent_ids=("crm.owner_lookup",),
            model_visible_concept_ids=("crm.owner",),
            model_visible_tool_keys=("hidden_other_tool",),
        )

    for raw in (
        '{"intent_id":"crm.owner_lookup","intent_id":"other"}',
        {"intent_id": "unreviewed"},
        {"intent_id": "crm.owner_lookup", "named_tools": ["unoffered"]},
        {"intent_id": "crm.owner_lookup", "parameter_hints": {"id": float("nan")}},
    ):
        with pytest.raises(ModelAnalysisError):
            await session.acompile_query(
                "owner", principal=ACTOR, model=lambda _, r=raw: r,
                intent_registry=INTENTS,
                model_visible_intent_ids=("crm.owner_lookup",),
                model_visible_concept_ids=("crm.owner",),
                model_visible_tool_keys=("fork_owner",),
            )


@pytest.mark.asyncio
async def test_model_error_does_not_leak_and_callback_policy_drift_fails_closed():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=CATALOG)

    def leak(_payload):
        raise RuntimeError("PRIVATE_MODEL_SECRET")

    with pytest.raises(ModelAnalysisError) as err:
        await session.acompile_query(
            "owner", principal=ACTOR, model=leak, intent_registry=INTENTS,
            model_visible_intent_ids=("crm.owner_lookup",),
            model_visible_concept_ids=("crm.owner",),
        )
    assert "PRIVATE_MODEL_SECRET" not in str(err.value)

    async def drift(_payload):
        router.authorization_policy = AuthorizationPolicy(
            default_effect="deny", rules=(AuthorizationRule(
                effect="allow", operation="fork_origin.read", roles_any=("reader",),
            ),),
        )
        return {"intent_id": "crm.owner_lookup"}

    with pytest.raises(PolicyViolationError, match="changed"):
        await session.acompile_query(
            "owner", principal=ACTOR, model=drift, intent_registry=INTENTS,
            model_visible_intent_ids=("crm.owner_lookup",),
            model_visible_concept_ids=("crm.owner",),
        )


@pytest.mark.asyncio
async def test_model_query_rejects_incompatible_intent_or_payload_budget():
    session = build_fixture(500).prepare_field_routing(catalog=CATALOG)
    other = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="other.intent", required_concept_ids=("not.offered",),
    ),))
    with pytest.raises(ValueError, match="disclosure"):
        await session.acompile_query(
            "owner", principal=ACTOR, model=lambda _: {}, intent_registry=other,
            model_visible_intent_ids=("other.intent",),
            model_visible_concept_ids=("crm.owner",),
        )
    with pytest.raises(ModelAnalysisError, match="budget"):
        await session.acompile_query(
            "owner", principal=ACTOR, model=lambda _: {}, intent_registry=INTENTS,
            model_visible_intent_ids=("crm.owner_lookup",),
            model_visible_concept_ids=("crm.owner",),
            max_model_input_bytes=32,
        )


@pytest.mark.asyncio
async def test_host_opt_in_model_query_discovers_unnamed_dependency_without_tool_disclosure():
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=CATALOG)
    policy = PaperNativeRankPolicy(snapshot_id=session.snapshot_id)
    observed = []

    async def model(payload):
        observed.append(payload)
        return {"intent_id": "crm.owner_lookup", "named_tools": []}

    plan = await session.acompile_query(
        "who owns the customer", principal=ACTOR,
        model=model, intent_registry=INTENTS,
        model_visible_intent_ids=("crm.owner_lookup",),
        model_visible_concept_ids=("crm.owner",),
        rank_policy=policy, allow_unnamed_graph_discovery=True,
    )
    assert plan.status == "requires_observation"
    assert tuple(call.route_id for call in plan.calls) == (ROOT, RIGHT)
    assert len(plan.bindings) == 1
    assert plan.ranked_unverified and not plan.executable_authority
    assert len(observed) == 1
    assert observed[0]["offered_tool_keys"] == []
    assert "allow_unnamed_graph_discovery" not in json.dumps(observed[0])
    assert ROOT not in json.dumps(observed[0])
    assert RIGHT not in json.dumps(observed[0])


@pytest.mark.asyncio
async def test_host_unnamed_graph_discovery_without_rank_is_rejected_before_model_call():
    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=CATALOG)

    def model(_payload):
        pytest.fail("non-owner-approved graph discovery must never call model")

    with pytest.raises(ValueError, match="rank|owner|approved"):
        await session.acompile_query(
            "who owns the customer", principal=ACTOR,
            model=model, intent_registry=INTENTS,
            model_visible_intent_ids=("crm.owner_lookup",),
            model_visible_concept_ids=("crm.owner",),
            allow_unnamed_graph_discovery=True,
        )


@pytest.mark.asyncio
async def test_model_unnamed_query_preserves_host_only_intent_domain_g5_filter():
    from schemarouter.paper_native_rank import PaperNativeRankPolicy

    router = build_fixture(500)
    session = router.prepare_field_routing(catalog=CATALOG)
    policy = PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id,
        route_domains={RIGHT: ("crm",)},
    )
    domain_intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="crm.owner_lookup",
        required_concept_ids=("crm.owner",), domains=("crm",),
    ),))
    disclosed = []

    async def model(payload):
        disclosed.append(payload)
        return {
            "intent_id": "crm.owner_lookup",
            "concept_ids": ["crm.owner"], "named_tools": [],
        }

    plan = await session.acompile_query(
        "Who is the customer owner?", principal=ACTOR, model=model,
        intent_registry=domain_intents,
        model_visible_intent_ids=("crm.owner_lookup",),
        model_visible_concept_ids=("crm.owner",),
        model_visible_tool_keys=(), rank_policy=policy,
        allow_unnamed_graph_discovery=True,
    )
    assert plan.status == "requires_observation"
    assert tuple(c.route_id for c in plan.calls) == (ROOT, RIGHT)
    assert plan.ranked_unverified and not plan.executable_authority
    assert len(disclosed) == 1
    assert disclosed[0]["offered_tool_keys"] == []
    assert "allow_unnamed_graph_discovery" not in json.dumps(disclosed[0])
    assert ROOT not in json.dumps(disclosed[0])
    assert RIGHT not in json.dumps(disclosed[0])

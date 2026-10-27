"""#1797: original Algorithm 1 Rank is owner-scoped, not arbitrary model ranking."""
from __future__ import annotations

import pytest
from test_native_semantic_index import ANALYST, GROUP, _router
from test_paper_understood_direct_plan import (
    _catalog as _paper_catalog,
)
from test_paper_understood_direct_plan import (
    _intents as _paper_intents,
)
from test_paper_understood_direct_plan import (
    _router as _paper_router,
)
from test_paper_understood_direct_plan import (
    _understanding as _paper_understanding,
)

from schemarouter.errors import PolicyViolationError
from schemarouter.native_semantic_index import IndexedNativeFieldCandidate, NativeSchemaPostingIndex
from schemarouter.paper_native_rank import (
    PaperNativeRankPolicy,
    rank_authorized_paper_direct,
)
from schemarouter.paper_understood_direct_plan import (
    PaperIntentDeclaration,
    PaperIntentRegistry,
)

SNAPSHOT = "a" * 64


def _candidate(route: str, field: str) -> IndexedNativeFieldCandidate:
    return IndexedNativeFieldCandidate(
        route_id=route, tool_fingerprint="t", endpoint_fingerprint="e",
        required_output_fields=(field,),
    )


def test_rank_exact_concept_then_nonweb_priority_visible_breadth_and_route_id():
    candidates = (
        _candidate("a_partial.read", "status_value"),
        _candidate("b_web.read", "case status"),
        _candidate("c_low.read", "case status"),
        _candidate("d_wide.read", "case status"),
        _candidate("e_tie.read", "case status"),
        _candidate("f_tie.read", "case status"),
        _candidate("g_priority.read", "case status"),
    )
    policy = PaperNativeRankPolicy(
        snapshot_id=SNAPSHOT,
        web_route_ids=("b_web.read",),
        route_priorities={"g_priority.read": 2},
    )
    count = {candidate.route_id: 1 for candidate in candidates}
    count["d_wide.read"] = 10
    ranking = rank_authorized_paper_direct(
        candidates, concept_aliases=(("case status",),),
        visible_field_count=count, policy=policy, k=5,
    )
    assert tuple(candidates[index].route_id for index in ranking) == (
        "g_priority.read", "c_low.read", "e_tie.read", "f_tie.read",
        "d_wide.read",
    )


def test_exact_match_dominates_two_partial_matches_for_multiple_concepts():
    candidates = (
        IndexedNativeFieldCandidate(
            route_id="exact.read", tool_fingerprint="t", endpoint_fingerprint="e",
            required_output_fields=("case status", "unrelated"),
        ),
        IndexedNativeFieldCandidate(
            route_id="partial.read", tool_fingerprint="t", endpoint_fingerprint="e",
            required_output_fields=("case status value", "case priority value"),
        ),
    )
    policy = PaperNativeRankPolicy(
        snapshot_id=SNAPSHOT, route_priorities={"partial.read": 100},
    )
    ranked = rank_authorized_paper_direct(
        candidates, concept_aliases=(("case status",), ("case priority",)),
        visible_field_count={"exact.read": 2, "partial.read": 2},
        policy=policy,
    )
    assert ranked == (0, 1)


def test_intent_domains_filter_requires_owner_approved_route_membership():
    intent = PaperIntentDeclaration(
        intent_id="case.lookup", required_concept_ids=("crm.status",),
        domains=("case",),
    )
    policy = PaperNativeRankPolicy(
        snapshot_id=SNAPSHOT,
        route_domains={"crm.read": ("case",), "finance.read": ("finance",)},
    )
    assert intent.domains == ("case",)
    assert policy.permits_domain("crm.read", intent.domains)
    assert not policy.permits_domain("finance.read", intent.domains)
    assert not policy.permits_domain("untagged.read", intent.domains)
    assert policy.permits_domain("untagged.read", ())


@pytest.mark.parametrize("kwargs", [
    {"snapshot_id": "not-a-snapshot"},
    {"snapshot_id": SNAPSHOT, "route_priorities": {"a.read": True}},
    {"snapshot_id": SNAPSHOT, "route_priorities": {"a.read": 100000}},
    {"snapshot_id": SNAPSHOT, "web_route_ids": ("x.read", "x.read")},
    {"snapshot_id": SNAPSHOT, "route_domains": {"x.read": ("bad space",)}},
])
def test_rank_policy_refuses_invalid_owner_declaration(kwargs):
    with pytest.raises(ValueError):
        PaperNativeRankPolicy(**kwargs)


def test_posting_index_ranks_six_original_qualified_routes_after_auth_and_before_k():
    router = _router(many_complete=6)
    index = NativeSchemaPostingIndex.build(router.registry)
    policy = PaperNativeRankPolicy(
        snapshot_id=index.snapshot_id,
        route_priorities={"full_5.read": 10, "denied.read": 100},
    )
    result = index.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ANALYST,
        _paper_rank_policy=policy,
        _paper_rank_aliases=(("case status",), ("case priority",)),
    )
    assert result.status == "ranked_unverified"
    assert result.qualified_count == 7
    assert result.deterministic_paper_ranked is True
    assert tuple(candidate.route_id for candidate in result.candidates) == (
        "full_5.read", "complete.read", "full_0.read", "full_1.read",
        "full_2.read",
    )
    assert not any(candidate.route_id == "denied.read" for candidate in result.candidates)


def test_domain_filter_applies_before_k_without_automatic_rank_on_named_tools():
    router = _router(many_complete=8)
    index = NativeSchemaPostingIndex.build(router.registry)
    policy = PaperNativeRankPolicy(
        snapshot_id=index.snapshot_id,
        route_domains={f"full_{i}.read": ("cases",) for i in range(5)},
    )
    result = index.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ANALYST,
        _paper_rank_policy=policy, _paper_rank_domains=("cases",),
        _paper_rank_aliases=(("case status",),),
    )
    assert result.status == "complete"
    assert result.qualified_count == 5
    assert {candidate.route_id for candidate in result.candidates} == {
        f"full_{i}.read" for i in range(5)
    }
    named = index.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ANALYST,
        allowed_tool_keys=("full_6",), _paper_rank_policy=policy,
        _paper_rank_aliases=(("case status",),),
    )
    assert named.status == "complete"
    assert tuple(candidate.route_id for candidate in named.candidates) == (
        "full_6.read",
    )
    assert not named.deterministic_paper_ranked


def test_owner_policy_refuses_nonexistent_or_stale_rank_source():
    router = _router(many_complete=6)
    index = NativeSchemaPostingIndex.build(router.registry)
    for policy in (
        PaperNativeRankPolicy(snapshot_id="b" * 64),
        PaperNativeRankPolicy(
            snapshot_id=index.snapshot_id,
            route_priorities={"invented.read": 50},
        ),
    ):
        with pytest.raises((ValueError, PolicyViolationError)):
            index.lookup(
                router, GROUP.aliases[0], group=GROUP, principal=ANALYST,
                _paper_rank_policy=policy,
                _paper_rank_aliases=(("case status",),),
            )


def test_5000_registered_routes_rank_against_independent_authorized_oracle():
    """The old research menu's 32-route ceiling is not a product Rank limit."""
    router = _router(many_complete=4993)
    index = NativeSchemaPostingIndex.build(router.registry)
    assert index.indexed_route_count == 5000
    # Priority changes only source-verified ordering; a forbidden owner
    # annotation never manufactures eligibility or provider execution.
    weights = {f"full_{i}.read": i - 4987 for i in range(4988, 4993)}
    weights["denied.read"] = 100
    policy = PaperNativeRankPolicy(
        snapshot_id=index.snapshot_id, route_priorities=weights,
    )
    result = index.lookup(
        router, GROUP.aliases[0], group=GROUP, principal=ANALYST,
        _paper_rank_policy=policy,
        _paper_rank_aliases=(("case status",), ("case priority",)),
    )
    # Independent fixture oracle: only the actual original 4,993 full_* plus
    # the original complete route satisfy the source-approved two-field AND.
    eligible = ["complete.read"] + [f"full_{i}.read" for i in range(4993)]
    oracle = sorted(eligible, key=lambda route: (-weights.get(route, 0), route))[:5]
    assert result.qualified_count == len(eligible)
    assert result.status == "ranked_unverified"
    assert result.deterministic_paper_ranked
    assert [candidate.route_id for candidate in result.candidates] == oracle
    assert all(candidate.required_output_fields == ("priority", "status")
               for candidate in result.candidates)


def test_public_understood_session_wires_reviewed_rank_into_nonexecuting_plan():
    router = _paper_router()
    session = router.prepare_field_routing(catalog=_paper_catalog())
    hints = _paper_understanding()
    assert session.compile_understood(
        hints, principal=ANALYST, intent_registry=_paper_intents(),
    ).status == "over_k_unranked"
    policy = PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id,
        route_priorities={"full_5.read": 10},
    )
    ranked = session.compile_understood(
        hints, principal=ANALYST, intent_registry=_paper_intents(),
        rank_policy=policy,
    )
    assert ranked.status == "ready"
    assert ranked.ranked_unverified is True
    assert ranked.executable_authority is False
    assert len(ranked.calls) == 5
    assert ranked.calls[0].route_id == "full_5.read"
    assert len({call.route_id for call in ranked.calls}) == 5
    assert all(call.fields_meta for call in ranked.calls)


def test_public_intent_domains_limit_ranked_routes_without_named_override_loss():
    router = _paper_router()
    session = router.prepare_field_routing(catalog=_paper_catalog())
    policy = PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id,
        route_domains={"full_3.read": ("cases",),
                       "full_4.read": ("finance",)},
        route_priorities={"full_4.read": 50},
    )
    intents = PaperIntentRegistry(intents=(PaperIntentDeclaration(
        intent_id="case.lookup",
        required_concept_ids=("crm.status", "crm.priority"),
        domains=("cases",),
    ),))
    narrowed = session.compile_understood(
        _paper_understanding(), principal=ANALYST,
        intent_registry=intents, rank_policy=policy,
    )
    assert narrowed.status == "ready"
    assert tuple(call.route_id for call in narrowed.calls) == ("full_3.read",)
    assert narrowed.ranked_unverified

    named = session.compile_understood(
        _paper_understanding(named_tools=("full_4",)),
        principal=ANALYST, intent_registry=intents, rank_policy=policy,
    )
    assert tuple(call.route_id for call in named.calls) == ("full_4.read",)
    assert not named.ranked_unverified


def test_paper_rank_public_api_exposes_only_explicit_no_execution_policy():
    import schemarouter

    assert schemarouter.PaperNativeRankPolicy is PaperNativeRankPolicy


@pytest.mark.asyncio
async def test_public_model_query_wires_rank_policy_and_refuses_owner_mutation():
    router = _paper_router()
    session = router.prepare_field_routing(catalog=_paper_catalog())
    policy = PaperNativeRankPolicy(
        snapshot_id=session.snapshot_id,
        route_priorities={"full_5.read": 10},
    )

    async def model(_payload):
        return {"intent_id": "case.lookup", "concept_ids": ["crm.status"],
                "named_tools": []}

    kwargs = dict(
        principal=ANALYST, model=model, intent_registry=_paper_intents(),
        model_visible_intent_ids=("case.lookup",),
        model_visible_concept_ids=("crm.status", "crm.priority"),
        rank_policy=policy,
    )
    plan = await session.acompile_query("show case status", **kwargs)
    assert plan.status == "ready"
    assert plan.ranked_unverified is True
    assert plan.calls[0].route_id == "full_5.read"

    async def mutate_policy(_payload):
        policy.route_priorities["full_4.read"] = 100
        return {"intent_id": "case.lookup", "concept_ids": ["crm.status"],
                "named_tools": []}

    with pytest.raises(PolicyViolationError):
        await session.acompile_query(
            "show case status", **{**kwargs, "model": mutate_policy},
        )


@pytest.mark.asyncio
async def test_public_model_callback_cannot_emit_private_rank_serialization_error():
    router = _paper_router()
    session = router.prepare_field_routing(catalog=_paper_catalog())
    policy = PaperNativeRankPolicy(snapshot_id=session.snapshot_id)

    async def forge_unserializable_owner_rank(_payload):
        policy.route_priorities["full_4.read"] = object()
        return {"intent_id": "case.lookup", "concept_ids": ["crm.status"]}

    with pytest.raises(PolicyViolationError, match="owner authority changed"):
        await session.acompile_query(
            "show case status", principal=ANALYST,
            model=forge_unserializable_owner_rank,
            intent_registry=_paper_intents(),
            model_visible_intent_ids=("case.lookup",),
            model_visible_concept_ids=("crm.status", "crm.priority"),
            rank_policy=policy,
        )


@pytest.mark.asyncio
async def test_invalid_rank_snapshot_refuses_before_any_model_disclosure():
    router = _router(many_complete=0)
    session = router.prepare_field_routing(catalog=_paper_catalog())
    policy = PaperNativeRankPolicy(snapshot_id="b" * 64)

    async def must_not_run(_payload):
        pytest.fail("untrusted model ran before owner rank preflight")

    with pytest.raises(PolicyViolationError):
        await session.acompile_query(
            "show case status", principal=ANALYST, model=must_not_run,
            intent_registry=_paper_intents(),
            model_visible_intent_ids=("case.lookup",),
            model_visible_concept_ids=("crm.status", "crm.priority"),
            rank_policy=policy,
        )

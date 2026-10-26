"""A8 opt-in paper Understand -> source-proven research Top-K5 bridge."""
from __future__ import annotations

from dataclasses import replace

import pytest
from test_research_paper_scoped_agent_real_e0 import (
    CATALOG,
    INTENTS,
    QUERY,
    source,
)

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    FieldSpec,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    PolicyViolationError,
    PrincipalContext,
    ToolSpec,
)
from schemarouter.paper_understood_direct_plan import PaperUnderstanding
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_paper_ranked_direct_a8_e0 import (
    research_rank_paper_understood_direct_e0,
)


def scoped_source(*, eligible_count=8, denied=False):
    first, _ = source()
    router = first.router
    for i in range(eligible_count - 1):
        router.add_tool(ToolSpec(
            name=f"status{i}", description=f"case status source {i}",
            source_type="crm", license="host-approved",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                output_fields=[FieldSpec(
                    name="status", semantic_id="case.status",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    if denied:
        router.add_tool(ToolSpec(
            name="denied", description="case status private",
            source_type="crm", license="host-approved",
            endpoints=[EndpointSpec(
                name="read", read_only=True,
                output_fields=[FieldSpec(
                    name="status", semantic_id="case.status",
                    json_schema={"type": "string"},
                )],
            )],
        ))
        router.authorization_policy = AuthorizationPolicy(
            default_effect="deny", rules=(
                AuthorizationRule(
                    effect="deny", operation="denied.read", roles_any=("viewer",),
                ),
                AuthorizationRule(
                    effect="allow", operation="*.read", roles_any=("viewer",),
                ),
            ),
        )
    view = capture_authorized_agent_tool_surface(
        router, QUERY,
        principal=PrincipalContext(subject="synthetic", roles=("viewer",)),
    )
    index = NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(router.registry),
    )
    return view, index


def hints(**kwargs):
    return PaperUnderstanding(intent_id="case.lookup", **kwargs)


def run(view, index, ranker, understanding=None, **kwargs):
    return research_rank_paper_understood_direct_e0(
        ranker, view=view, understanding=understanding or hints(),
        catalog=kwargs.get("catalog", CATALOG),
        intent_registry=INTENTS, index=index,
    )


def test_overflow_research_ranker_receives_actual_original_query_and_eligible_source_only():
    view, index = scoped_source(eligible_count=8, denied=True)
    offered = []

    def rank(query, candidates, k):
        assert query == QUERY  # Not the narrow host-approved alias.
        assert k == 5
        offered.extend(candidate.route_id for candidate in candidates)
        return (7, 6, 5, 4, 3)

    row = run(view, index, rank)
    assert row.status == "ranked_unverified"
    assert row.qualified_count == 8
    assert row.ranked_route_ids == tuple(offered[index] for index in (7, 6, 5, 4, 3))
    assert "denied.read" not in offered
    assert set(offered) <= set(view.visible_route_ids)
    assert row.independent_quality_evidence is False
    assert row.executable_authority is False


def test_named_source_filter_precedes_overflow_and_does_not_call_ranker():
    view, index = scoped_source(eligible_count=8)
    result = run(
        view, index, lambda *_: pytest.fail("named tool is before K"),
        hints(named_tools=("status0",)),
    )
    assert result.status == "complete"
    assert result.ranked_route_ids == ("status0.read",)


def test_original_understood_direct_plan_overflow_remains_unchanged_by_opt_in():
    from schemarouter.paper_understood_direct_plan import (
        compile_paper_understood_direct_plan,
    )

    view, index = scoped_source(eligible_count=8)
    original = compile_paper_understood_direct_plan(
        view.router, hints(), principal=view._principal,
        catalog=CATALOG, intent_registry=INTENTS, index=index,
    )
    assert original.status == "over_k_unranked"
    assert original.calls == ()
    ranked = run(view, index, lambda _q, _c, _k: (0, 1, 2, 3, 4))
    assert ranked.status == "ranked_unverified"
    assert original.status == "over_k_unranked"


def test_ranking_abstention_is_not_interpreted_as_global_absence():
    view, index = scoped_source(eligible_count=8)
    result = run(view, index, lambda _q, _c, _k: ())
    assert result.status == "ranker_abstained_unverified"
    assert result.qualified_count == 8
    assert result.ranked_route_ids == ()
    assert result.independent_quality_evidence is False


@pytest.mark.parametrize("bad", [(0, 1), (0, 1, 2, 3, 9), (True, 1, 2, 3, 4)])
def test_malformed_ranker_decisions_fail_closed(bad):
    view, index = scoped_source()
    with pytest.raises(PolicyViolationError):
        run(view, index, lambda *_: bad)


def test_over_32_authorized_source_routes_abstains_without_any_ranker_call():
    view, index = scoped_source(eligible_count=33)
    row = run(view, index, lambda *_: pytest.fail("no unbounded model disclosure"))
    assert row.status == "over_k_unranked"
    assert row.ranked_route_ids == ()


def test_unregistered_named_tool_and_source_type_mismatch_are_no_proof():
    view, index = scoped_source()

    def ranker(*_):
        pytest.fail("named/source mismatch must not rank")

    assert run(view, index, ranker, hints(named_tools=("nonexistent",))).status == "no_proven_hit"
    assert run(view, index, ranker, hints(source_type="other")).status == "no_proven_hit"


def test_owner_catalog_mutation_during_ranking_discards_result():
    view, index = scoped_source()
    catalog = CATALOG.model_copy(deep=True)

    def mutate(_q, _c, _k):
        catalog.concepts[0].aliases = ("changed",)
        return (0, 1, 2, 3, 4)

    with pytest.raises(PolicyViolationError):
        run(view, index, mutate, catalog=catalog)


def test_captured_principal_policy_mutation_during_ranking_discards_result():
    view, index = scoped_source()

    def mutate(_q, _c, _k):
        view.router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return (0, 1, 2, 3, 4)

    with pytest.raises(PolicyViolationError):
        run(view, index, mutate)


def test_untrusted_hint_mutation_and_replaced_source_view_discard_result():
    view, index = scoped_source()
    understanding = hints()

    def mutate(_q, _c, _k):
        understanding.parameter_hints["private"] = "changed"
        return (0, 1, 2, 3, 4)

    with pytest.raises(PolicyViolationError):
        run(view, index, mutate, understanding)

    forged = replace(view, visible_route_ids=("invented.read",))
    with pytest.raises(PolicyViolationError):
        run(forged, index, lambda *_: (0, 1, 2, 3, 4))

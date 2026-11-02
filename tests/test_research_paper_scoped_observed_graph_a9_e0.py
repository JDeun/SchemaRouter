"""A9 complete scoped Understand callback → real named G5 tool observation."""

from __future__ import annotations

import pytest
from test_paper_understood_graph_plan import CATALOG, INTENTS
from test_paper_understood_observed_graph_a9_e0 import _fixture

from schemarouter import AuthorizationPolicy, AuthorizationRule, PrincipalContext
from schemarouter.errors import PolicyViolationError
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)

QUERY = "Please find the case status"


def _view(router):
    return capture_authorized_agent_tool_surface(
        router, QUERY,
        principal=PrincipalContext(subject="host-a9", roles=("reader",)),
    )


def _response(*, target="target_0", hints=None):
    return {
        "intent_id": "case.lookup",
        "concept_ids": ["crm.status"],
        "named_tools": [target],
        "parameter_hints": hints or {},
    }


def _args(view, index):
    return dict(
        view=view, catalog=CATALOG, intent_registry=INTENTS, index=index,
        model_visible_intent_ids=("case.lookup",),
        model_visible_concept_ids=("crm.status",),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("hops", [1, 2])
async def test_one_actual_scoped_model_call_executes_native_named_dag(hops):
    from scripts.research_paper_scoped_observed_graph_a9_e0 import (
        run_paper_scoped_named_graph_a9_e0,
    )

    router, index, seen = _fixture(hops=hops)
    view = _view(router)
    disclosed = []

    def model(payload):
        disclosed.append(payload)
        assert payload["query"] == QUERY
        assert set(payload["offered_tool_keys"]) == (
            {"root", "target_0"} if hops == 1
            else {"root", "middle", "target_0"}
        )
        return _response(hints={"case_id": "injected-model-id"})

    decision, receipt = await run_paper_scoped_named_graph_a9_e0(
        model, **_args(view, index),
    )
    assert decision == "offer"
    assert receipt is not None
    assert len(disclosed) == 1
    assert [name for name, _args_seen in seen] == (
        ["root", "target_0"] if hops == 1
        else ["root", "middle", "target_0"]
    )
    assert seen[-1][1] == {"case_id": "case-42" if hops == 2 else "contact-7"}
    assert receipt.provider_provenance_verified is False
    assert receipt.independent_e2 is False


@pytest.mark.asyncio
async def test_missing_root_host_input_defers_without_any_tool_call():
    from scripts.research_paper_scoped_observed_graph_a9_e0 import (
        run_paper_scoped_named_graph_a9_e0,
    )

    router, index, seen = _fixture(host_root=True)
    view = _view(router)
    decision, receipt = await run_paper_scoped_named_graph_a9_e0(
        lambda payload: _response(hints={"external_id": "fake-model-value"}),
        **_args(view, index),
    )
    assert (decision, receipt) == ("request_arguments", None)
    assert seen == []
    decision, receipt = await run_paper_scoped_named_graph_a9_e0(
        lambda payload: _response(hints={"external_id": "fake-model-value"}),
        **_args(view, index),
        host_source_arguments={"root.read": {"external_id": "host-input"}},
    )
    assert decision == "offer"
    assert receipt is not None
    assert seen[0] == ("root", {"external_id": "host-input"})
    assert seen[-1] == ("target_0", {"case_id": "case-42"})


@pytest.mark.asyncio
async def test_unknown_model_named_tool_abstains_without_execution():
    from scripts.research_paper_scoped_observed_graph_a9_e0 import (
        run_paper_scoped_named_graph_a9_e0,
    )

    router, index, seen = _fixture()
    decision, receipt = await run_paper_scoped_named_graph_a9_e0(
        lambda payload: _response(target="invented_tool"),
        **_args(_view(router), index),
    )
    assert (decision, receipt) == ("abstain", None)
    assert seen == []


@pytest.mark.asyncio
async def test_empty_authorized_menu_invokes_neither_model_nor_executor():
    from scripts.research_paper_scoped_observed_graph_a9_e0 import (
        run_paper_scoped_named_graph_a9_e0,
    )

    router, index, seen = _fixture()
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    view = _view(router)

    def forbidden_model(payload):
        pytest.fail("empty scoped route set cannot invoke model")

    decision, receipt = await run_paper_scoped_named_graph_a9_e0(
        forbidden_model, **_args(view, index),
    )
    assert (decision, receipt) == ("abstain", None)
    assert seen == []


@pytest.mark.asyncio
async def test_scoped_policy_change_during_model_prevents_source_invocation():
    from scripts.research_paper_scoped_observed_graph_a9_e0 import (
        run_paper_scoped_named_graph_a9_e0,
    )

    router, index, seen = _fixture()
    view = _view(router)

    def mutate(payload):
        router.authorization_policy = AuthorizationPolicy(default_effect="deny")
        return _response()

    with pytest.raises(PolicyViolationError):
        await run_paper_scoped_named_graph_a9_e0(
            mutate, **_args(view, index),
        )
    assert seen == []


@pytest.mark.asyncio
async def test_scoped_policy_change_during_middle_stops_target_and_receipt():
    from scripts.research_paper_scoped_observed_graph_a9_e0 import (
        run_paper_scoped_named_graph_a9_e0,
    )

    def revoke(router, name):
        if name == "middle":
            router.authorization_policy = AuthorizationPolicy(
                default_effect="deny", rules=(AuthorizationRule(
                    effect="allow", operation="root.read", roles_any=("reader",),
                ),),
            )

    router, index, seen = _fixture(on_step=revoke)
    with pytest.raises(PolicyViolationError):
        await run_paper_scoped_named_graph_a9_e0(
            lambda payload: _response(), **_args(_view(router), index),
        )
    assert [name for name, _ in seen] == ["root", "middle"]


@pytest.mark.asyncio
@pytest.mark.parametrize("hops", [1, 2])
async def test_scoped_a9_explicit_owner_unnamed_graph_executes_pinned_path(hops):
    from test_paper_understood_observed_graph_a9_e0 import _ranked_fixture

    from schemarouter.paper_native_rank import PaperNativeRankPolicy
    from scripts.research_paper_scoped_observed_graph_a9_e0 import (
        run_paper_scoped_named_graph_a9_e0,
    )

    router, index, seen = _ranked_fixture(hops=hops)
    view = _view(router)
    policy = PaperNativeRankPolicy(
        snapshot_id=index.field_index.snapshot_id,
        route_priorities={"target_5.read": 100},
    )

    def model(payload):
        # Model chooses ONLY reviewed intent/concept. Host approves
        # source-owning discovery and Rank; this is not a model permission.
        return {
            "intent_id": "case.lookup", "concept_ids": ["crm.status"],
            "named_tools": [],
        }

    decision, receipt = await run_paper_scoped_named_graph_a9_e0(
        model, **_args(view, index),
        rank_policy=policy, allow_unnamed_graph_discovery=True,
    )
    assert decision == "offer"
    assert receipt is not None
    assert receipt.plan.ranked_unverified
    assert not receipt.executable_authority
    assert [name for name, _ in seen] == (
        ["root", "target_5"] if hops == 1
        else ["root", "middle", "target_5"]
    )


@pytest.mark.asyncio
async def test_scoped_a9_unnamed_graph_requires_host_rank_before_model_call():
    from scripts.research_paper_scoped_observed_graph_a9_e0 import (
        run_paper_scoped_named_graph_a9_e0,
    )

    router, index, seen = _fixture()
    def model(_payload):
        pytest.fail("host proof preflight must precede model disclosure")

    with pytest.raises(ValueError, match="owner|Rank|host"):
        await run_paper_scoped_named_graph_a9_e0(
            model, **_args(_view(router), index),
            allow_unnamed_graph_discovery=True,
        )
    assert seen == []

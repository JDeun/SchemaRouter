"""E0-only model-visible ranked order checks for principal-scoped fixed K5.

These tests intentionally use a scripted generator, not actual model quality
or calibrated unsupported/no-fit evidence. Frozen conditions are immutable.
"""
from __future__ import annotations

import json

import pytest

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    PrincipalContext,
    SchemaRouter,
    ToolSpec,
)
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    run_generated_episode,
)
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)

QUERY = "marine public papers read values"
ACTOR = PrincipalContext(subject="ranked-e0-viewer", roles=("viewer",))
RANKED = ["papers.read", "marine.read"]


class RecordingNoCallAgent:
    def __init__(self) -> None:
        self.visible_orders: list[tuple[str, ...]] = []

    def generate(self, _messages, tools):
        self.visible_orders.append(tuple(item["name"] for item in tools))
        return {
            "text": "REQUEST_MORE_TOOLS",
            "input_tokens": 3,
            "tool_tokens": 2,
            "output_tokens": 1,
            "latency_ms": 0.0,
            "context_overflow": False,
        }


def _scoped_source():
    router = SchemaRouter(authorization_policy=AuthorizationPolicy(
        default_effect="deny",
        rules=(
            AuthorizationRule(
                name="deny-private", effect="deny",
                operation="archive.*", roles_any=("viewer",),
            ),
            AuthorizationRule(
                name="allow-read", effect="allow",
                operation="*.*", roles_any=("viewer",),
            ),
        ),
    ))
    for name in ("marine", "papers", "archive"):
        router.add_tool(ToolSpec(
            name=name,
            description=f"public {name} records PRIVATE_CANARY",
            endpoints=[
                EndpointSpec(
                    name="read",
                    description=f"read public {name} values",
                    read_only=True,
                ),
            ],
        ))
    view = capture_authorized_agent_tool_surface(
        router, QUERY, principal=ACTOR,
    )
    assert set(view.visible_route_ids) == set(RANKED)
    assert "archive.read" not in view.visible_route_ids
    return view


def _unsupported_task():
    return {
        "semantic_task_id": "ranked-order-no-call-e0",
        "task_stratum": "unsupported_no_fit",
        "language": "en",
        "query": QUERY,
        "supported": False,
        "required_routes": [],
        "executor_fixture": {"steps": []},
    }


def _run(view, agent, *, preserve=False, selected=None, condition=None):
    return run_generated_episode(
        agent, view.router.registry, _unsupported_task(),
        condition or EXPERIMENTAL_FIXED5_CONDITION,
        experimental_candidate_selector=lambda _query, _offered: (
            list(RANKED) if selected is None else selected
        ),
        experimental_agent_tool_surface=view,
        experimental_preserve_candidate_order=preserve,
    )


def test_optin_exposes_validated_rank_instead_of_legacy_alphabetical_order():
    view = _scoped_source()
    original = RecordingNoCallAgent()
    ordered = RecordingNoCallAgent()
    base = _run(view, original)
    trial = _run(view, ordered, preserve=True)

    assert original.visible_orders == [("marine__read", "papers__read")]
    assert ordered.visible_orders == [("papers__read", "marine__read")]
    assert base["visible_candidate_counts"] == [2]
    assert trial["visible_candidate_counts"] == [2]
    assert base["tool_call_count"] == trial["tool_call_count"] == 0
    assert base["passed"] is trial["passed"] is True
    assert "papers.read" not in json.dumps(trial)
    assert "PRIVATE_CANARY" not in json.dumps(trial)
    assert not view.executable_authority
    assert not view.independent_quality_evidence


def test_ranked_order_cannot_be_enabled_without_scoped_source_and_isolated_arm():
    view = _scoped_source()
    for condition in ("FULL", "SR-5", "SR-10", "SR-PROGRESSIVE", "ORACLE"):
        agent = RecordingNoCallAgent()
        with pytest.raises(ValueError, match="isolated principal-scoped fixed5"):
            _run(view, agent, preserve=True, condition=condition)
        assert agent.visible_orders == []

    agent = RecordingNoCallAgent()
    with pytest.raises(ValueError, match="isolated principal-scoped fixed5"):
        run_generated_episode(
            agent, view.router.registry, _unsupported_task(),
            EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=lambda _query, _ids: list(RANKED),
            experimental_preserve_candidate_order=True,
        )
    assert agent.visible_orders == []


@pytest.mark.parametrize("bad_flag", (1, None, "true", [], {}))
def test_ranked_order_flag_requires_exact_bool(bad_flag):
    view = _scoped_source()
    agent = RecordingNoCallAgent()
    with pytest.raises(ValueError, match="flag must be boolean"):
        _run(view, agent, preserve=bad_flag)
    assert agent.visible_orders == []


@pytest.mark.parametrize("forged", (
    ["archive.read"],
    ["papers.read", "papers.read"],
    ["papers.read", "foreign.read"],
    RANKED + ["papers.read"],
))
def test_ranked_mode_rejects_denied_unknown_or_duplicate_source_before_model(forged):
    view = _scoped_source()
    agent = RecordingNoCallAgent()
    with pytest.raises(ValueError, match="invalid experimental source-native"):
        _run(view, agent, preserve=True, selected=forged)
    assert agent.visible_orders == []


def test_ranked_mode_aborts_on_authorization_mutation_before_model_disclosure():
    view = _scoped_source()
    agent = RecordingNoCallAgent()

    def invalidating_selector(_query, _source_ids):
        view.router.authorization_policy = AuthorizationPolicy(
            default_effect="deny",
        )
        return list(RANKED)

    with pytest.raises(Exception, match="(authorization|authority|source)"):
        run_generated_episode(
            agent, view.router.registry, _unsupported_task(),
            EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=invalidating_selector,
            experimental_agent_tool_surface=view,
            experimental_preserve_candidate_order=True,
        )
    assert agent.visible_orders == []


def test_empty_ranked_candidate_set_stays_empty_not_auto_refilled():
    view = _scoped_source()
    agent = RecordingNoCallAgent()
    result = _run(view, agent, preserve=True, selected=[])
    assert agent.visible_orders == [()]
    assert result["visible_candidate_counts"] == [0]
    assert result["tool_call_count"] == 0
    assert result["passed"] is True

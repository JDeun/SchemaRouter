"""E0 source-locked baseline/paper pairing via the existing agent executor."""
from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import asdict

import pytest
from test_research_paper_scoped_agent_real_e0 import (
    CATALOG,
    INTENTS,
    QUERY,
    Agent,
    model_result,
    source,
)

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    CapabilityFieldContract,
    EndpointSpec,
    FieldSpec,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    PolicyViolationError,
    PrincipalContext,
    ToolSpec,
)
from schemarouter.errors import ModelAnalysisError
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_paper_measured_episode_e0 import PaperProviderUsageResponse
from scripts.research_paper_paired_agent_e0 import (
    HostAgentPairConfiguration,
    run_paper_counterbalanced_agent_e0,
    run_paper_paired_agent_e0,
)


def task(*, supported=True):
    return {
        "semantic_task_id": "a7-pair-synthetic-dev-only",
        "query": QUERY, "language": "en", "supported": supported,
        "required_routes": ["complete.read"] if supported else [],
        "executor_fixture": {"steps": [{
            "route_id": "complete.read", "argument_rules": {},
            "observation": {"status": "ok", "status_value": "open"},
        }]} if supported else {"steps": []},
    }


CONFIG = HostAgentPairConfiguration(
    agent_revision="synthetic-agent-1", model_revision="synthetic-model-1", seed=17,
    sampling_parameters=(("temperature", "0.0"), ("top_p", "1.0")),
)


def factory():
    return Agent(), CONFIG


def kwargs(view, index, t):
    return {
        "view": view, "task": t,
        "catalog": CATALOG, "intent_registry": INTENTS,
        "index": index, "model_visible_intent_ids": ("case.lookup",),
        "model_visible_concept_ids": ("case.status",),
    }


@pytest.mark.asyncio
async def test_counterbalanced_a7_executes_both_actual_orders_with_fresh_agents():
    view, index = source()
    events = []
    created = []
    callbacks = []

    class LoggingAgent(Agent):
        def __init__(self, position):
            super().__init__()
            self.position = position

        def generate(self, messages, tools):
            events.append(f"agent-{self.position}")
            return super().generate(messages, tools)

    def agents():
        agent = LoggingAgent(len(created))
        created.append(agent)
        return agent, CONFIG

    def models():
        trial = len(callbacks)

        def model(payload):
            events.append(f"understand-{trial}")
            return PaperProviderUsageResponse(model_result(), 41, 7)

        callbacks.append(model)
        return model

    report = await run_paper_counterbalanced_agent_e0(
        models, agents, **kwargs(view, index, task()),
    )
    assert len(created) == 4 and len(set(map(id, created))) == 4
    assert len(callbacks) == 2 and callbacks[0] is not callbacks[1]
    assert all(agent.turns == 2 for agent in created)
    assert events.index("agent-0") < events.index("understand-0")
    assert events.index("understand-0") < events.index("agent-1")
    assert events.index("understand-1") < events.index("agent-3")
    assert events.index("agent-3") < events.index("agent-2")
    assert report.baseline_first.execution_order == "baseline_first"
    assert report.paper_first.execution_order == "paper_first"
    assert report.baseline_first.baseline["passed"] is True
    assert report.paper_first.baseline["passed"] is True
    assert report.baseline_first.paper.episode["passed"] is True
    assert report.paper_first.paper.episode["passed"] is True
    assert report.baseline_first.paper.measurement.understand_input_tokens_provider_reported == 41
    assert report.paper_first.paper.measurement.understand_output_tokens_provider_reported == 7
    assert report.independent_e2_qualified is False
    exposed = json.dumps(asdict(report), ensure_ascii=False)
    assert QUERY not in exposed
    assert "complete.read" not in exposed
    assert "required_routes" not in exposed
    assert '"supported"' not in exposed


@pytest.mark.asyncio
async def test_a7_invalid_execution_order_cannot_invoke_agent_or_understand():
    view, index = source()
    calls = []

    def agents():
        calls.append("agent")
        return Agent(), CONFIG

    def model(payload):
        calls.append("model")
        return model_result()

    with pytest.raises(ValueError, match="execution order"):
        await run_paper_paired_agent_e0(
            model, agents, execution_order="paper-and-baseline-in-parallel",
            **kwargs(view, index, task()),
        )
    assert calls == []


@pytest.mark.asyncio
async def test_a7_paper_first_single_pair_really_runs_before_baseline():
    view, index = source()
    events = []

    class LoggingAgent(Agent):
        def __init__(self, role):
            super().__init__()
            self.role = role

        def generate(self, messages, tools):
            events.append(self.role)
            return super().generate(messages, tools)

    created = []

    def make():
        agent = LoggingAgent(("baseline", "paper")[len(created)])
        created.append(agent)
        return agent, CONFIG

    def model(payload):
        events.append("understand")
        return model_result()

    report = await run_paper_paired_agent_e0(
        model, make, execution_order="paper_first", **kwargs(view, index, task()),
    )
    assert events.index("understand") < events.index("paper") < events.index("baseline")
    assert report.execution_order == "paper_first"
    assert report.independent_e2_qualified is False


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ("reused", "different_callable_type"))
async def test_a7_counterbalance_rejects_nonfresh_or_incomparable_models_before_agents(failure):
    view, index = source()

    def same_callback(payload):
        return model_result()

    calls = []

    class CallableModel:
        def __call__(self, payload):
            raise AssertionError("invalid model must never execute")

    def model_factory():
        calls.append("model_factory")
        if failure == "reused":
            return same_callback
        return same_callback if len(calls) == 1 else CallableModel()

    def unused_agent_factory():
        calls.append("agent_factory")
        return Agent(), CONFIG

    with pytest.raises(ValueError, match="Understand callback"):
        await run_paper_counterbalanced_agent_e0(
            model_factory, unused_agent_factory, **kwargs(view, index, task()),
        )
    assert calls == ["model_factory", "model_factory"]


@pytest.mark.asyncio
async def test_a7_counterbalance_invalid_scoped_task_refused_before_creating_models():
    view, index = source()
    calls = []

    def model_factory():
        calls.append("model_factory")
        return lambda payload: model_result()

    def agent_factory():
        calls.append("agent_factory")
        return Agent(), CONFIG

    bad_task = task()
    bad_task["query"] = "different private query"
    with pytest.raises(ValueError, match="paired task/query mismatch"):
        await run_paper_counterbalanced_agent_e0(
            model_factory, agent_factory, **kwargs(view, index, bad_task),
        )
    assert calls == []


@pytest.mark.asyncio
async def test_a7_counterbalance_model_factory_cannot_rewrite_private_gold_before_first_pair():
    view, index = source()
    original_task = task()
    calls = []

    def model_factory():
        calls.append("model_factory")
        original_task["supported"] = False
        original_task["required_routes"] = []
        return lambda payload: model_result()

    def agent_factory():
        calls.append("agent_factory")
        return Agent(), CONFIG

    with pytest.raises(ValueError, match="task evidence changed"):
        await run_paper_counterbalanced_agent_e0(
            model_factory, agent_factory, **kwargs(view, index, original_task),
        )
    assert "agent_factory" not in calls


@pytest.mark.asyncio
async def test_a7_counterbalance_model_factory_cannot_mutate_owner_catalog_before_first_pair():
    view, index = source()
    private_catalog = CATALOG.model_copy(deep=True)
    calls = []

    def model_factory():
        calls.append("model_factory")
        private_catalog.concepts[0].required_fields = (
            CapabilityFieldContract(
                semantic_id="case.secret", json_schema={"type": "string"},
            ),
        )
        return lambda payload: model_result()

    def agent_factory():
        calls.append("agent_factory")
        return Agent(), CONFIG

    with pytest.raises(PolicyViolationError, match="owner declarations changed"):
        await run_paper_counterbalanced_agent_e0(
            model_factory, agent_factory,
            **{**kwargs(view, index, task()), "catalog": private_catalog},
        )
    assert "agent_factory" not in calls


@pytest.mark.asyncio
@pytest.mark.parametrize("violation", ("config_drift", "reused_agent"))
async def test_a7_counterbalance_rejects_cross_trial_agent_drift_without_receipt(violation):
    view, index = source()
    agents = []

    def agent_factory():
        position = len(agents)
        if violation == "reused_agent" and position == 2:
            agents.append(agents[0])
            return agents[0], CONFIG
        agent = Agent()
        agents.append(agent)
        cfg = CONFIG if position < 2 else HostAgentPairConfiguration(
            agent_revision=CONFIG.agent_revision,
            model_revision="second-trial-unmatched-model",
            seed=CONFIG.seed,
            sampling_parameters=CONFIG.sampling_parameters,
        )
        return agent, cfg

    def model_factory():
        return lambda payload: model_result()

    with pytest.raises(ValueError, match="matching fresh agent"):
        await run_paper_counterbalanced_agent_e0(
            model_factory, agent_factory, **kwargs(view, index, task()),
        )
    assert agents[0].turns == agents[1].turns == 2


@pytest.mark.asyncio
async def test_a7_counterbalance_paper_first_source_revocation_blocks_baseline_and_output():
    view, index = source()
    agents = []
    created_models = 0

    def agent_factory():
        agent = Agent()
        agents.append(agent)
        return agent, CONFIG

    def model_factory():
        nonlocal created_models
        position = created_models
        created_models += 1

        def model(payload):
            if position == 1:
                view.router.authorization_policy = AuthorizationPolicy(default_effect="deny")
            return model_result()

        return model

    with pytest.raises(PolicyViolationError):
        await run_paper_counterbalanced_agent_e0(
            model_factory, agent_factory, **kwargs(view, index, task()),
        )
    assert len(agents) == 4
    assert agents[0].turns == agents[1].turns == 2
    assert agents[2].turns == 0  # second trial baseline cannot run after revocation


@pytest.mark.asyncio
async def test_a7_counterbalance_understand_failure_in_second_trial_discards_both():
    view, index = source()
    created = 0

    def model_factory():
        nonlocal created
        i = created
        created += 1

        def model(payload):
            if i == 1:
                raise RuntimeError("synthetic provider unavailable")
            return model_result()

        return model

    # Existing scoped Understand intentionally redacts raw provider exceptions.
    with pytest.raises(ModelAnalysisError, match="model understanding failed"):
        await run_paper_counterbalanced_agent_e0(
            model_factory, factory, **kwargs(view, index, task()),
        )


@pytest.mark.asyncio
async def test_real_same_factory_runs_baseline_and_paper_on_identical_task():
    view, index = source()
    original = task()
    immutable = deepcopy(original)
    created = []
    payloads = []

    class RecordingAgent(Agent):
        def __init__(self):
            super().__init__()
            self.offered_tools = []

        def generate(self, messages, tools):
            self.offered_tools.append(deepcopy(tools))
            return super().generate(messages, tools)

    def two_agents():
        agent, cfg = RecordingAgent(), CONFIG
        created.append(agent)
        return agent, cfg

    async def understanding(payload):
        payloads.append(payload)
        return PaperProviderUsageResponse(model_result(), 33, 5)

    row = await run_paper_paired_agent_e0(
        understanding, two_agents, **kwargs(view, index, original),
    )
    assert len(created) == 2 and created[0] is not created[1]
    assert all(x.turns == 2 for x in created)
    assert original == immutable
    assert row.baseline["passed"] is True
    assert row.paper.episode["passed"] is True
    assert row.baseline["tool_call_count"] == row.paper.episode["tool_call_count"] == 1
    assert row.baseline["visible_candidate_counts"][0] <= 5
    assert row.paper.measurement.understand_input_tokens_provider_reported == 33
    baseline_bytes = sum(len(json.dumps(
        offered, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")) for offered in created[0].offered_tools)
    assert baseline_bytes > 0
    assert row.baseline_tool_schema_utf8_bytes_exposed == baseline_bytes
    assert row.host_declared_matching_agent_configuration is True
    assert row.independent_e2_qualified is False
    assert len(payloads) == 1
    assert "required_routes" not in payloads[0]
    assert "executor_fixture" not in payloads[0]
    assert "final_text" not in row.baseline
    assert "candidate_history" not in row.baseline
    assert "supported" not in row.baseline
    assert "supported" not in row.paper.episode


@pytest.mark.asyncio
async def test_unproven_paper_tool_yields_empty_menu_without_fake_e2_score():
    view, index = source()
    row = await run_paper_paired_agent_e0(
        lambda payload: model_result("nonexistent"), factory,
        **kwargs(view, index, task(supported=False)),
    )
    assert row.paper.decision == "abstain"
    assert row.paper.episode["host_empty_menu_terminal"] is True
    assert row.paper.episode["tool_call_count"] == 0
    assert row.independent_e2_qualified is False


@pytest.mark.asyncio
async def test_empty_principal_source_calls_neither_understand_nor_agent():
    original, _ = source()
    router = original.router
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    view = capture_authorized_agent_tool_surface(
        router, QUERY, principal=PrincipalContext(subject="synthetic"),
    )
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))

    class NeverAgent(Agent):
        def generate(self, messages, tools):
            raise AssertionError("empty menu must be host-terminated")

    def never_factory():
        return NeverAgent(), CONFIG

    def never_model(payload):
        raise AssertionError("empty source must not invoke Understand")

    row = await run_paper_paired_agent_e0(
        never_model, never_factory, **kwargs(view, index, task(supported=False)),
    )
    assert row.baseline["host_empty_menu_terminal"] is True
    assert row.paper.episode["host_empty_menu_terminal"] is True
    assert row.paper.measurement.understand_called is False
    assert row.baseline["tool_call_count"] == row.paper.episode["tool_call_count"] == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["same_instance", "different_class", "different_config"])
async def test_invalid_host_agent_pair_never_runs_either_episode(mutation):
    view, index = source()
    calls = []
    first = Agent()

    class DifferentAgent(Agent):
        pass

    def wrong_factory():
        calls.append(1)
        if len(calls) == 1:
            return first, CONFIG
        if mutation == "same_instance":
            return first, CONFIG
        if mutation == "different_class":
            return DifferentAgent(), CONFIG
        return Agent(), HostAgentPairConfiguration(
            agent_revision=CONFIG.agent_revision,
            model_revision="changed-model", seed=CONFIG.seed,
            sampling_parameters=CONFIG.sampling_parameters,
        )

    def forbidden_model(payload):
        raise AssertionError("pair invalid: do not invoke model")

    with pytest.raises(ValueError, match="matching fresh agent"):
        await run_paper_paired_agent_e0(
            forbidden_model, wrong_factory, **kwargs(view, index, task()),
        )
    assert len(calls) == 2
    assert first.turns == 0


@pytest.mark.asyncio
async def test_baseline_task_mutation_cannot_corrupt_paper_confirmation():
    view, index = source()
    t = task()
    calls = []

    class Mutator(Agent):
        def generate(self, messages, tools):
            t["supported"] = False
            return super().generate(messages, tools)

    def make():
        calls.append(1)
        return Mutator(), CONFIG

    with pytest.raises(ValueError, match="evidence changed"):
        await run_paper_paired_agent_e0(
            lambda payload: model_result(), make, **kwargs(view, index, t),
        )
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_policy_revoke_in_baseline_does_not_return_a_partial_paired_result():
    view, index = source()
    calls = []

    class RevokingAgent(Agent):
        def generate(self, messages, tools):
            view.router.authorization_policy = AuthorizationPolicy(default_effect="deny")
            return super().generate(messages, tools)

    def make():
        calls.append(1)
        return RevokingAgent(), CONFIG

    with pytest.raises(PolicyViolationError):
        await run_paper_paired_agent_e0(
            lambda payload: model_result(), make,
            **kwargs(view, index, task()),
        )
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_invalid_understand_usage_aborts_pair_without_second_agent_execution():
    view, index = source()
    agents = []

    def make():
        agent = Agent()
        agents.append(agent)
        return agent, CONFIG

    with pytest.raises(ModelAnalysisError):
        await run_paper_paired_agent_e0(
            lambda payload: PaperProviderUsageResponse(model_result(), True, 1),
            make, **kwargs(view, index, task()),
        )
    assert len(agents) == 2
    assert agents[0].turns == 2
    assert agents[1].turns == 0


@pytest.mark.asyncio
async def test_nonfinite_task_data_is_refused_before_agent_factory_or_scoring():
    view, index = source()
    untrusted = task()
    untrusted["unstable_evidence"] = float("nan")
    calls = []

    def unused_factory():
        calls.append("factory")
        return Agent(), CONFIG

    def unused_model(payload):
        raise AssertionError("nonfinite task must never reach model")

    with pytest.raises(ValueError, match="task cannot be frozen"):
        await run_paper_paired_agent_e0(
            unused_model, unused_factory, **kwargs(view, index, untrusted),
        )
    assert calls == []


@pytest.mark.asyncio
async def test_baseline_owner_catalog_drift_cannot_change_paper_gold_or_proof():
    view, index = source()
    private_catalog = CATALOG.model_copy(deep=True)
    model_calls = []

    class ChangingAgent(Agent):
        def generate(self, messages, tools):
            private_catalog.concepts[0].required_fields = (
                CapabilityFieldContract(
                    semantic_id="other.hidden", json_schema={"type": "string"},
                ),
            )
            return super().generate(messages, tools)

    def agents():
        return ChangingAgent(), CONFIG

    def model(payload):
        model_calls.append(payload)
        return model_result()

    with pytest.raises(PolicyViolationError, match="owner declarations changed"):
        await run_paper_paired_agent_e0(
            model, agents,
            **{**kwargs(view, index, task()), "catalog": private_catalog},
        )
    assert model_calls == []


@pytest.mark.asyncio
async def test_host_declared_sampling_drift_refuses_misleading_same_agent_pair():
    view, index = source()
    calls = []

    def different_sampling():
        calls.append(1)
        if len(calls) == 1:
            return Agent(), CONFIG
        return Agent(), HostAgentPairConfiguration(
            agent_revision="synthetic-agent-1",
            model_revision="synthetic-model-1",
            seed=17,
            sampling_parameters=(("temperature", "0.99"), ("top_p", "1.0")),
        )

    with pytest.raises(ValueError, match="matching fresh agent"):
        await run_paper_paired_agent_e0(
            lambda payload: model_result(), different_sampling,
            **kwargs(view, index, task()),
        )
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_baseline_exact_first_five_come_from_ranked_authorized_source_only():
    original, _ = source()
    router = original.router
    for i in range(7):
        router.add_tool(ToolSpec(
            name=f"additional{i}", description="case status lookup",
            source_type="crm", license="host-approved",
            endpoints=[EndpointSpec(
                name="read", read_only=True, description="case status lookup",
                output_fields=[FieldSpec(
                    name="note", semantic_id=f"note.{i}",
                    json_schema={"type": "string"},
                )],
            )],
        ))
    router.add_tool(ToolSpec(
        name="denied", source_type="crm", license="host-approved",
        endpoints=[EndpointSpec(name="read", read_only=True)],
    ))
    router.authorization_policy = AuthorizationPolicy(
        default_effect="deny", rules=(
            AuthorizationRule(effect="deny", operation="denied.read", roles_any=("viewer",)),
            AuthorizationRule(effect="allow", operation="*.read", roles_any=("viewer",)),
        ),
    )
    view = capture_authorized_agent_tool_surface(
        router, QUERY, principal=PrincipalContext(subject="synthetic", roles=("viewer",)),
    )
    assert len(view.visible_route_ids) >= 6
    assert "denied.read" not in view.visible_route_ids
    index = NativeSchemaGraphIndex.build(NativeSchemaPostingIndex.build(router.registry))
    captures = []

    class MenuRecordingAgent:
        def generate(self, messages, tools):
            captures.append([tool["name"] for tool in tools])
            return {
                "text": "REQUEST_MORE_TOOLS", "input_tokens": 2, "output_tokens": 2,
                "tool_tokens": 2, "latency_ms": 0.0, "context_overflow": False,
            }

    def agents():
        return MenuRecordingAgent(), CONFIG

    pair = await run_paper_paired_agent_e0(
        lambda payload: model_result(), agents, **kwargs(view, index, task()),
    )
    expected = {
        name.replace(".", "__") for name in view.visible_route_ids[:5]
    }
    assert len(captures[0]) == 5
    assert set(captures[0]) == expected
    assert "denied__read" not in captures[0]
    assert pair.baseline["visible_candidate_counts"] == [5]
    assert pair.independent_e2_qualified is False

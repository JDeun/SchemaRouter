"""Prospective synthetic FULL pairing, never independent qualification."""
import json
from copy import deepcopy
from dataclasses import asdict

import pytest
from test_research_paper_paired_agent_e0 import CONFIG, kwargs, task
from test_research_paper_scoped_agent_real_e0 import QUERY, model_result, source

from schemarouter import (
    AuthorizationPolicy,
    AuthorizationRule,
    EndpointSpec,
    NativeSchemaGraphIndex,
    NativeSchemaPostingIndex,
    PolicyViolationError,
    PrincipalContext,
    ToolSpec,
)
from schemarouter.field_routing_session import SchemaFieldRoutingSession
from schemarouter.models import QueryIntent
from scripts.agent_utility_generated_common import (
    EXPERIMENTAL_FIXED5_CONDITION,
    EXPERIMENTAL_FULL_CONDITION,
    run_generated_episode,
)
from scripts.research_agent_stage_evidence_e0 import E0TraceProvenance
from scripts.research_authorized_agent_tool_surface import capture_authorized_agent_tool_surface
from scripts.research_paper_measured_episode_e0 import PaperProviderUsageResponse
from scripts.research_paper_paired_agent_e0 import (
    run_paper_counterbalanced_agent_e0,
    run_paper_paired_agent_e0,
)
from scripts.research_private_final_answer_e0 import private_structured_final_result


def gold_task():
    original = task()
    original.update({
        "required_facts": [{"key": "case.status", "value": "ok", "unit": None,
                            "source_id": "complete.read"}],
        "numeric_tolerances": {}, "accepted_units": {},
        "allowed_source_ids": ["complete.read"], "forbidden_facts": [],
        "mandatory_answer_fields": ["case.status"],
    })
    return original


def answer(**changes):
    fact = {**gold_task()["required_facts"][0], **changes}
    return json.dumps({"answer": "Private final prose", "facts": [fact],
                       "sources": [fact["source_id"]]})


def full_source():
    original, _ = source()
    for i in range(6):
        # No query overlap: FULL must include authorized zero-score endpoints.
        original.router.add_tool(ToolSpec(
            name=f"z{i}", endpoints=[EndpointSpec(name="read", read_only=True)],
        ))
    original.router.add_tool(ToolSpec(
        name="secret", endpoints=[EndpointSpec(name="read", read_only=True)],
    ))
    original.router.authorization_policy = AuthorizationPolicy(
        default_effect="deny", rules=(
            AuthorizationRule(effect="deny", operation="secret.*", roles_any=("viewer",)),
            AuthorizationRule(effect="allow", operation="*.read", roles_any=("viewer",)),
        ),
    )
    view = capture_authorized_agent_tool_surface(
        original.router, QUERY,
        principal=PrincipalContext(subject="synthetic", roles=("viewer",)),
        experimental_full_catalog=True,
    )
    return view, NativeSchemaGraphIndex.build(
        NativeSchemaPostingIndex.build(original.router.registry),
    )


class RecordingAgent:
    def __init__(self, text, captured, *, mutation=None, missing_usage=False):
        self.text, self.captured, self.mutation = text, captured, mutation
        self.turns = 0
        self.missing_usage = missing_usage

    def generate(self, messages, tools):
        self.captured.append((messages.copy(), [t["name"] for t in tools]))
        if self.mutation:
            self.mutation()
        text = ('<tool_call>{"name":"complete__read","arguments":{}}</tool_call>'
                if not self.turns else self.text)
        self.turns += 1
        return {"text": text, "input_tokens": None if self.missing_usage else 2,
                "output_tokens": 2, "tool_tokens": 2, "latency_ms": 0.0,
                "context_overflow": False}


async def run(text, *, original=None, order="baseline_first", missing_usage=False,
              mutation=None, provider_usage=True):
    view, index = full_source()
    captures, agents, model_payloads = [], [], []

    def factory():
        agent = RecordingAgent(text, captures, mutation=mutation, missing_usage=missing_usage)
        agents.append(agent)
        return agent, CONFIG

    def model(payload):
        model_payloads.append(payload)
        response = model_result()
        return PaperProviderUsageResponse(response, 11, 3) if provider_usage else response

    result = await run_paper_paired_agent_e0(
        model, factory, **kwargs(view, index, original if original is not None else gold_task()),
        execution_order=order, experimental_full_final_oracle=True,
    )
    return result, captures, agents, model_payloads


@pytest.mark.asyncio
@pytest.mark.parametrize("order", ("baseline_first", "paper_first"))
async def test_full_original_authorized_catalog_and_private_oracle(order):
    result, captured, agents, payloads = await run(answer(), order=order)
    menus = [menu for _, menu in captured]
    assert max(map(len, menus)) == 7 and min(map(len, menus)) == 1
    assert all("secret__read" not in menu for menu in menus)
    assert len(agents) == 2 and agents[0] is not agents[1]
    assert all(agent.turns == 2 for agent in agents)
    assert len(menus[0]) == (7 if order == "baseline_first" else 1)
    for row in (result.baseline, result.paper.episode):
        assert row["passed"] is True  # Legacy execution-only metric retained.
        assert row["execution_and_structured_final_passed"] is True
        assert row["free_text_final_answer_verified"] is False
    public = json.dumps(asdict(result))
    assert "Private final prose" not in public and "required_facts" not in public
    assert "complete.read" not in public and "case.status" not in public
    assert "required_facts" not in json.dumps(payloads)
    assert all("required_facts" not in json.dumps(messages) for messages, _ in captured)
    assert result.independent_e2_qualified is False
    assert result.full_catalog_comparison is True
    assert result.all_model_usage_complete is True
    assert captured[0][0][0] == captured[-1][0][0]  # Same system prompt.


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ({"value": "wrong"}, {"unit": "seconds"},
                                  {"source_id": "forged"}))
async def test_correct_execution_does_not_pass_wrong_final_fact_unit_or_source(change):
    result, *_ = await run(answer(**change))
    for row in (result.baseline, result.paper.episode):
        assert row["passed"] is True
        assert row["execution_and_structured_final_passed"] is False


@pytest.mark.asyncio
async def test_missing_gold_and_usage_remain_unverified():
    result, *_ = await run(answer(), original=task(), missing_usage=True, provider_usage=False)
    for row in (result.baseline, result.paper.episode):
        assert row["execution_and_structured_final_passed"] is None
        assert row["input_tokens"] is None
    assert result.paper.measurement.understand_input_tokens_provider_reported is None
    assert result.paper.measurement.agent_input_tokens_reported is None
    assert result.all_model_usage_complete is False


@pytest.mark.asyncio
async def test_full_agent_cannot_mutate_original_gold():
    original = gold_task()
    with pytest.raises(ValueError, match="task evidence changed"):
        await run(answer(), original=original,
                  mutation=lambda: original["required_facts"][0].update(value="forged"))


@pytest.mark.asyncio
async def test_full_paper_arm_really_uses_public_field_session(monkeypatch):
    calls = []
    original = SchemaFieldRoutingSession.compile_understood

    def observe(session, understanding, **options):
        calls.append(understanding)
        return original(session, understanding, **options)

    monkeypatch.setattr(SchemaFieldRoutingSession, "compile_understood", observe)
    await run(answer())
    assert len(calls) == 1


def test_full_capture_preserves_data_scope_availability_and_fixed5_cap():
    from test_research_authorized_agent_tool_surface import SECRET, VIEWER, fixture_router

    router = fixture_router()
    router.planner.availability_predicate = lambda tool, _: tool.name != "papers"
    view = capture_authorized_agent_tool_surface(
        router, "unmatched query", principal=VIEWER, experimental_full_catalog=True,
    )
    assert view.visible_route_ids == ("marine.read",)
    exposed = json.dumps(view.full_tool_definitions())
    assert SECRET not in exposed and "secret_field" not in exposed
    assert "archive" not in exposed and "papers" not in exposed
    many, _ = full_source()
    with pytest.raises((PolicyViolationError, ValueError)):
        many.tool_definitions(list(many.visible_route_ids))
    with pytest.raises(ValueError, match="fixed K"):
        many.tool_definitions(list(many.visible_route_ids), k=7)


def test_full_rejects_incomplete_capture_and_cannot_be_truncated_by_selector():
    view, _ = source()
    agent = RecordingAgent(answer(), [])
    with pytest.raises(ValueError, match="complete scoped capture"):
        run_generated_episode(
            agent, view.router.registry, gold_task(), EXPERIMENTAL_FULL_CONDITION,
            experimental_candidate_selector=lambda _q, ids: list(ids),
            experimental_agent_tool_surface=view, experimental_final_answer_oracle=True,
        )
    many, _ = full_source()
    with pytest.raises(ValueError, match="invalid experimental"):
        run_generated_episode(
            agent, many.router.registry, gold_task(), EXPERIMENTAL_FULL_CONDITION,
            experimental_candidate_selector=lambda _q, ids: list(ids[:5]),
            experimental_agent_tool_surface=many, experimental_final_answer_oracle=True,
        )
    assert agent.turns == 0


def test_full_hidden_call_is_blocked_before_private_fixture_observation():
    view, _ = full_source()
    seen = []

    class HiddenCallAgent(RecordingAgent):
        def generate(self, messages, tools):
            response = super().generate(messages, tools)
            if self.turns == 1:
                response["text"] = '<tool_call>{"name":"secret__read","arguments":{}}</tool_call>'
            seen.append(json.dumps(messages))
            return response

    original = gold_task()
    # Even a fixture containing the hidden provider response cannot disclose it.
    original["executor_fixture"]["steps"] = [{
        "route_id": "secret.read", "argument_rules": {},
        "observation": {"status": "ok", "private": "PRIVATE_PROVIDER_CANARY"},
    }]
    result = run_generated_episode(
        HiddenCallAgent(answer(), []), view.router.registry, original,
        EXPERIMENTAL_FULL_CONDITION,
        experimental_candidate_selector=lambda _q, ids: list(ids),
        experimental_agent_tool_surface=view, experimental_final_answer_oracle=True,
        experimental_block_unavailable_observation=True,
    )
    # The frozen executor classifies unavailable-menu guesses separately from
    # policy-blocked schema-valid calls; keep that historical denominator.
    assert result["tool_call_count"] == 1
    assert result["policy_blocks"] == 0
    assert result["task_complete"] is False
    assert result["execution_and_structured_final_passed"] is False
    assert "PRIVATE_PROVIDER_CANARY" not in json.dumps(seen)
    assert "PRIVATE_PROVIDER_CANARY" not in json.dumps(result)


@pytest.mark.asyncio
async def test_full_capture_receipt_cannot_be_flipped_on_legacy_partial_view():
    view, index = source()
    object.__setattr__(view, "full_catalog_captured", True)
    with pytest.raises(PolicyViolationError, match="source|contents|modified"):
        await run_paper_paired_agent_e0(
            lambda payload: model_result(), lambda: (RecordingAgent(answer(), []), CONFIG),
            **kwargs(view, index, gold_task()), experimental_full_final_oracle=True,
        )


def test_full_capture_cannot_silently_use_analyzer_that_ignores_source_enumeration():
    view, _ = source()

    class Analyzer:
        def analyze(self, request, registry):
            return QueryIntent(concepts=[])

    view.router.planner.analyzer = Analyzer()
    with pytest.raises(ValueError, match="native keyword analyzer"):
        capture_authorized_agent_tool_surface(
            view.router, QUERY, principal=view._principal, experimental_full_catalog=True,
        )


@pytest.mark.asyncio
async def test_full_counterbalanced_orders_and_same_config_are_preserved():
    view, index = full_source()
    agents, captured, payloads = [], [], []

    def factory():
        agent = RecordingAgent(answer(), captured)
        agents.append(agent)
        return agent, CONFIG

    def models():
        def model(payload):
            payloads.append(payload)
            return PaperProviderUsageResponse(model_result(), 11, 3)
        return model

    report = await run_paper_counterbalanced_agent_e0(
        models, factory, **kwargs(view, index, gold_task()),
        experimental_full_final_oracle=True,
    )
    assert len(agents) == len({id(agent) for agent in agents}) == 4
    assert [len(menu) for _, menu in captured] == [7, 7, 1, 1, 1, 1, 7, 7]
    assert len(payloads) == 2
    assert report.baseline_first.all_model_usage_complete is True
    assert report.paper_first.all_model_usage_complete is True
    assert report.independent_e2_qualified is False


@pytest.mark.asyncio
async def test_full_mismatched_configuration_fails_before_callbacks():
    from dataclasses import replace

    view, index = full_source()
    calls = []

    def factory():
        calls.append("factory")
        return RecordingAgent(answer(), []), replace(CONFIG, seed=len(calls))

    with pytest.raises(ValueError, match="matching fresh"):
        await run_paper_paired_agent_e0(
            lambda payload: calls.append("model"), factory,
            **kwargs(view, index, gold_task()), experimental_full_final_oracle=True,
        )
    assert calls == ["factory", "factory"]


def test_oracle_requires_execution_and_does_not_check_free_text_prose():
    valid = private_structured_final_result(gold_task(), answer(), execution_passed=False)
    assert valid["structured_final_answer_passed"] is True
    assert valid["execution_and_structured_final_passed"] is False
    assert valid["free_text_final_answer_verified"] is False
    envelope = json.loads(answer())
    envelope["answer"] = "Untrue prose deliberately outside structured scorer scope"
    result = private_structured_final_result(
        gold_task(), json.dumps(envelope), execution_passed=True,
    )
    assert result["structured_final_answer_passed"] is True
    assert result["free_text_final_answer_verified"] is False


@pytest.mark.parametrize("bad_gold", ({"required_facts": []}, {"accepted_units": []},
                                      {"mandatory_answer_fields": ["unknown"]}))
def test_incomplete_gold_does_not_create_vacuous_final_success(bad_gold):
    result = private_structured_final_result(
        {**gold_task(), **bad_gold}, answer(), execution_passed=True,
    )
    assert result["execution_and_structured_final_passed"] is None


def test_numeric_tolerance_and_units_reuse_existing_424_gold_contract():
    original = gold_task()
    original["required_facts"][0].update(value=10.0, unit="m")
    original["numeric_tolerances"] = {"case.status": {"absolute": 0.01}}
    original["accepted_units"] = {"case.status": ["m"]}
    for value, unit, passed in ((10.005, "m", True), (11.0, "m", False), (10.0, "km", False)):
        result = private_structured_final_result(
            original, answer(value=value, unit=unit), execution_passed=True,
        )
        assert result["execution_and_structured_final_passed"] is passed
    missing = deepcopy(original)
    missing["numeric_tolerances"] = {}
    assert private_structured_final_result(
        missing, answer(value=10.0, unit="m"), execution_passed=True,
    )["execution_and_structured_final_passed"] is None


def test_missing_usage_cannot_be_exported_as_zero_in_legacy_stage_receipt():
    view, _ = source()
    with pytest.raises(ValueError, match="complete reported agent usage"):
        run_generated_episode(
            RecordingAgent(answer(), [], missing_usage=True), view.router.registry,
            gold_task(), EXPERIMENTAL_FIXED5_CONDITION,
            experimental_candidate_selector=lambda _q, ids: list(ids),
            experimental_agent_tool_surface=view, experimental_final_answer_oracle=True,
            experimental_e0_trace_provenance=E0TraceProvenance(
                source_revision="a" * 40, source_sha256="b" * 64,
                hmac_key=b"private-test-key-000", seed=17,
            ),
        )


@pytest.mark.parametrize(("expected", "actual", "tolerance", "passed"), [
    (2**53, 2**53, {"absolute": 0}, True),
    (2**53, 2**53 + 1, {"absolute": 0}, False),
    (2**53, 2**53 + 1, {"relative": 0}, False),
    (2**53, 2**53 + 1, {"absolute": 1}, True),
    (10**400, 10**400, {"absolute": 0}, True),
    (10**400, 10**400 + 1, {"absolute": 0}, False),
    (10**400, 10**400 + 1, {"absolute": 1}, True),
    (10**400, 10**400 + 1, {"relative": 0}, False),
    (10**400, 10**400 + 1, {"relative": 1e-20}, True),
    (2**53 + 1, float(2**53), {"absolute": 0}, False),
    (2**53, 2**53 + 1, {"absolute": 0, "relative": 1e-10}, True),
    (1e308, -1e308, {"relative": 1.9}, False),
    (0, 1e-13, {"relative": 1}, True),
])
def test_private_numeric_oracle_preserves_integer_precision(expected, actual, tolerance, passed):
    original = gold_task()
    original["required_facts"][0]["value"] = expected
    original["numeric_tolerances"] = {"case.status": tolerance}
    before = deepcopy(original)
    result = private_structured_final_result(original, answer(value=actual), execution_passed=True)
    assert result["structured_final_answer_passed"] is passed
    assert result["execution_and_structured_final_passed"] is passed
    assert original == before


@pytest.mark.parametrize(("value", "forbidden", "passed"), [
    (10**400, 10**400, False),
    (10**400, 10**400 + 1, True),
    (10, 0, True),
    (1, True, False),
])
def test_private_numeric_copies_preserve_original_forbidden_values(value, forbidden, passed):
    original = gold_task()
    original["required_facts"][0]["value"] = value
    original["numeric_tolerances"] = {"case.status": {"absolute": 0}}
    original["forbidden_facts"] = [{"key": "case.status", "value": forbidden}]
    before = deepcopy(original)
    result = private_structured_final_result(original, answer(value=value), execution_passed=True)
    assert result["execution_and_structured_final_passed"] is passed
    assert original == before

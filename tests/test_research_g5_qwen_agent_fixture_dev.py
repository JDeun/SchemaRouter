"""E0 only: real existing executor, no injected-model scores promoted to E2."""
from __future__ import annotations

import json

import pytest

from schemarouter import AuthorizationPolicy, NativeDeclaredFieldGroup, PolicyViolationError
from schemarouter.decisions import CallableDecisionBackend
from scripts.research_authorized_agent_tool_surface import (
    capture_authorized_agent_tool_surface,
)
from scripts.research_g5_decision_backend_ranker_e0 import (
    ResearchAuthorizedG5DecisionRanker,
)
from scripts.research_g5_e5_overflow_cpu_dev import (
    ACTOR,
    SERVICE_NAMES,
    _source,
)
from scripts.research_g5_qwen_agent_fixture_dev import (
    ACCOUNT_ID,
    ARMS,
    BALANCED_PROMPT_ORDER,
    GROUNDED_PROMPT,
    INJECTED_EVIDENCE,
    PROMPT_ARMS,
    SYSTEM_PROMPT,
    GraderOnlyAttemptObserver,
    _candidate_selector,
    _cases,
    _first_five,
    _private_rank_diagnostic,
    run_fixture,
    summarize_balanced_prompt_runs,
)


class RefusingAgent:
    def __init__(self):
        self.generated = []

    def generate(self, messages, tools):
        self.generated.append((messages, tools))
        return {
            "text": "REQUEST_MORE_TOOLS",
            "input_tokens": 5,
            "tool_tokens": 2 * len(tools),
            "output_tokens": 1,
            "latency_ms": 0.0,
            "context_overflow": False,
        }


def test_paired_native_g5_agent_fixture_is_scored_only_after_real_agent_loop():
    agent = RefusingAgent()
    report = run_fixture(
        CallableDecisionBackend(_first_five), agent,
        source_revision="1" * 40,
    )
    assert len(agent.generated) == len(_cases()) * len(ARMS) == 12
    assert report["evidence_tier"] == INJECTED_EVIDENCE
    assert report["real_qwen_generation_measured"] is False
    assert report["real_e5_ranking_measured"] is False
    assert report["independent_e2_qualified"] is False
    assert report["real_native_provider_execution"] is False
    assert report["actual_final_answer_correctness_measured"] is False
    assert report["calibrated_no_fit"] is False
    assert report["product_default_promoted"] is False
    assert report["case_count"] == 6
    assert report["supported_cases"] == report["unsupported_cases"] == 3
    assert report["typed_native_consumer_paths"] == 24
    assert report["fixed_k"] == 5
    assert report["arms"] == list(ARMS)
    for arm in ARMS:
        funnel = report["post_execution_e0_stage_funnel"][arm]
        assert funnel["supported_cases"] == funnel["unsupported_cases"] == 3
        assert funnel["supported_required_route_visible"] == 0
        assert funnel["supported_correct_tool_attempts_not_proven"] == 0
        assert funnel["supported_wrong_operation_observed"] == 0
        assert funnel["supported_schema_rejections"] == 0
        assert funnel["supported_argument_mismatches"] == 0
        assert funnel["supported_fixture_completed"] == 0
        assert funnel["supported_completed_with_final_turn"] == 0
        assert funnel["supported_completed_given_route_visible_denominator"] == 0
        assert funnel["unsupported_no_call"] == 3
        assert funnel["unsupported_correct_terminal_refusal"] == 3
        assert funnel["unsupported_terminal_mismatch"] == 0
        for lang in ("en", "ko", "ja"):
            c = report["by_arm_language"][arm][lang]
            assert c["supported_count"] == c["unsupported_count"] == 1
            assert c["supported_fixture_completed"] == 0
            assert c["supported_required_route_visible"] == 0
            assert c["supported_tool_call_attempted"] == 0
            assert c["supported_completed_with_final_turn"] == 0
            assert c["unsupported_strict_no_call"] == 1
            assert c["unsupported_no_call"] == 1
            assert c["unsupported_terminal_mismatch"] == 0
            assert c["unsupported_tool_calls"] == 0
            assert c["policy_blocks"] == 0
            assert c["stage_counts"]["supported_no_fit_refusal_observed"] == 1
            assert c["stage_counts"]["passed"] == 1
            assert c["candidate_selection_ms_p50"] >= 0
            assert c["episode_ms_p95"] >= 0
    # The only agent prompts are user requests and original registered,
    # selected scoped tools, never fixture gold/executor fields.
    for messages, tools in agent.generated:
        assert len(tools) == 5
        assert all(isinstance(m, dict) for m in messages)
        assert all("executor_fixture" not in json.dumps(m) for m in messages)
        assert all("expected_route" not in json.dumps(x) for x in tools)
        assert all("required_routes" not in json.dumps(x) for x in tools)
    rendered = json.dumps(report, ensure_ascii=False)
    assert ACCOUNT_ID not in rendered
    assert all(query not in rendered for _lang, query, _gold in _cases())
    assert "required_routes" not in rendered
    assert "executor_fixture" not in rendered


def test_adapter_g5_native_source_before_ranker_rejects_revoked_permission():
    router, graph, concept = _source()
    query = "refund request status for account " + ACCOUNT_ID
    view = capture_authorized_agent_tool_surface(router, query, principal=ACTOR)
    demand = NativeDeclaredFieldGroup(
        aliases=(query,), required_fields=concept.required_fields,
        source_type=concept.source_type, license=concept.license,
    )
    def model(_request):
        pytest.fail("untrusted model invoked despite revocation")
    selector = _candidate_selector(
        view, graph, demand,
        ResearchAuthorizedG5DecisionRanker(CallableDecisionBackend(model)),
    )
    assert len(view.visible_route_ids) == len(SERVICE_NAMES) + 1
    router.authorization_policy = AuthorizationPolicy(default_effect="deny")
    with pytest.raises(PolicyViolationError):
        selector(query, view.visible_route_ids)
    assert len(view.visible_route_ids) == 25


def test_scripted_source_only_agent_separates_retrieval_from_fixture_completion():
    """Fake source-name matching sanity check, NEVER model-quality evidence."""

    def semantic_target(query):
        if "refund" in query:
            return "service_refund.read"
        if "청구서" in query:
            return "service_invoice.read"
        if "配達" in query:
            return "service_delivery.read"
        return None

    def source_only_backend(request):
        selected = semantic_target(request.query)
        rankable = list(request.options)
        if selected:
            rankable.sort(key=lambda option: option.label != selected)
        return {"selections": [
            {"option_id": opt.id} for opt in rankable[:5]
        ]}

    class ScriptedSourceAgent:
        """Reads only current user request and advertised scoped tool names."""

        def generate(self, messages, tools):
            selected = semantic_target(messages[1]["content"])
            if len(messages) > 2:
                answer = "Fixture query completed."
            elif selected is None:
                answer = "REQUEST_MORE_TOOLS"
            elif selected.replace(".", "__") not in {
                tool["name"] for tool in tools
            }:
                answer = "REQUEST_MORE_TOOLS"
            else:
                payload = {
                    "name": selected.replace(".", "__"),
                    "arguments": {"account_id": ACCOUNT_ID},
                }
                answer = "<tool_call>" + json.dumps(payload) + "</tool_call>"
            return {
                "text": answer, "input_tokens": 10,
                "tool_tokens": 2 * len(tools),
                "output_tokens": 4, "latency_ms": 0.0,
                "context_overflow": False,
            }

    report = run_fixture(
        CallableDecisionBackend(source_only_backend),
        ScriptedSourceAgent(),
        source_revision="2" * 40,
    )
    assert report["evidence_tier"] == INJECTED_EVIDENCE
    assert not report["real_qwen_generation_measured"]
    assert not report["real_e5_ranking_measured"]
    source_first5 = report["post_execution_e0_stage_funnel"]["source_first5"]
    synthetic_ranked = report["post_execution_e0_stage_funnel"]["e5_fixed5"]
    assert source_first5["supported_required_route_visible"] == 0
    assert source_first5["supported_fixture_completed"] == 0
    assert synthetic_ranked["supported_required_route_visible"] == 3
    assert synthetic_ranked["supported_fixture_completed"] == 3
    assert synthetic_ranked["supported_completed_with_final_turn"] == 3
    assert synthetic_ranked["supported_wrong_operation_observed"] == 0
    for stage in (source_first5, synthetic_ranked):
        assert stage["unsupported_no_call"] == 3
        assert stage["unsupported_correct_terminal_refusal"] == 3
        assert stage["unsupported_terminal_mismatch"] == 0
    assert report["real_native_provider_execution"] is False
    assert report["actual_final_answer_correctness_measured"] is False


def test_invalid_hardcoded_tool_example_is_prompt_only_not_a_source_route():
    router, _graph, _group = _source()
    source_names = {
        f"{tool.key}.{endpoint.name}".replace(".", "__")
        for tool in router.registry.tools()
        for endpoint in tool.endpoints
    }
    assert "service__read" not in source_names
    assert len(source_names) == 25
    assert "service__read" in SYSTEM_PROMPT
    assert "service__read" not in GROUNDED_PROMPT
    assert "REQUEST_MORE_TOOLS" in SYSTEM_PROMPT
    assert "REQUEST_MORE_TOOLS" in GROUNDED_PROMPT


def test_inventory_grounded_prompt_still_uses_same_source_executor_and_gold_separation():
    agent = RefusingAgent()
    r = run_fixture(
        CallableDecisionBackend(_first_five), agent,
        source_revision="4" * 40, system_prompt=GROUNDED_PROMPT,
    )
    assert r["prompt_condition"] == PROMPT_ARMS[1]
    assert r["evidence_tier"] == INJECTED_EVIDENCE
    assert r["case_count"] == 6
    assert len(agent.generated) == 12
    for messages, advertised_tools in agent.generated:
        assert messages[0]["content"] == GROUNDED_PROMPT
        assert len(advertised_tools) == 5
        assert all(item["name"] != "service__read" for item in advertised_tools)
        assert "required_routes" not in json.dumps(messages)
        assert "executor_fixture" not in json.dumps(advertised_tools)
    assert r["post_execution_e0_stage_funnel"]["e5_fixed5"][
        "unsupported_correct_terminal_refusal"
    ] == 3
    assert r["real_qwen_generation_measured"] is False
    assert r["real_e5_ranking_measured"] is False
    with pytest.raises(ValueError, match="provenance"):
        run_fixture(
            CallableDecisionBackend(_first_five), RefusingAgent(),
            source_revision="4" * 40, system_prompt="Use oracle gold.",
        )


def test_abba_order_has_two_original_and_two_grounded_model_calls():
    assert BALANCED_PROMPT_ORDER == (
        "legacy_unregistered_example", "grounded_inventory_only",
        "grounded_inventory_only", "legacy_unregistered_example",
    )
    agent = RefusingAgent()
    backend = CallableDecisionBackend(_first_five)
    runs = tuple(
        run_fixture(
            backend, agent, source_revision="3" * 40,
            system_prompt=(
                SYSTEM_PROMPT if name == PROMPT_ARMS[0] else GROUNDED_PROMPT
            ),
        )
        for name in BALANCED_PROMPT_ORDER
    )
    assert len(agent.generated) == 48  # 4 × 6 cases × 2 source arms.
    report = summarize_balanced_prompt_runs(runs)
    assert report["sequence"] == list(BALANCED_PROMPT_ORDER)
    assert report["evidence_tier"] == (
        "PUBLIC_SYNTHETIC_DEV_ABBA_PROMPT_ORDER_DIAGNOSTIC"
    )
    assert report["order_balanced_for_two_blocks"] is True
    assert report["randomized"] is False
    assert report["model_prompt_tuning_on_public_dev"] is True
    assert report["independent_e2_qualified"] is False
    assert report["scoring_authority"] is False
    assert report["calibrated_no_fit"] is False
    for prompt in PROMPT_ARMS:
        for arm in ARMS:
            cell = report["by_prompt_and_source_arm"][prompt][arm]
            assert cell["supported_denominator"] == 6
            assert cell["unsupported_denominator"] == 6
            assert len(cell["by_position"]) == 2
            assert cell["two_position_pooled_counts"][
                "unsupported_correct_terminal_refusal"
            ] == 6
            assert cell["two_position_pooled_counts"][
                "supported_fixture_completed"
            ] == 0
    assert "executor_fixture" not in json.dumps(report)
    assert "required_routes" not in json.dumps(report)
    assert ACCOUNT_ID not in json.dumps(report)
    assert "query" not in json.dumps(report)


def test_abba_aggregator_rejects_wrong_prompt_order_source_or_status():
    backend = CallableDecisionBackend(_first_five)
    baseline = run_fixture(
        backend, RefusingAgent(), source_revision="a" * 40,
    )
    grounded = run_fixture(
        backend, RefusingAgent(), source_revision="a" * 40,
        system_prompt=GROUNDED_PROMPT,
    )
    valid = (baseline, grounded, grounded, baseline)
    assert summarize_balanced_prompt_runs(valid)["sequence"] == list(
        BALANCED_PROMPT_ORDER
    )
    from copy import deepcopy
    for field, value in (
        ("evidence_tier", "REAL_PINNED_MODEL_NOT_INJECTED"),
        ("real_qwen_generation_measured", True),
        ("independent_e2_qualified", True),
        ("source_snapshot_sha256", "0" * 64),
        ("prompt_condition", PROMPT_ARMS[1]),
    ):
        forged = list(valid)
        forged[0] = deepcopy(forged[0])
        forged[0][field] = value
        with pytest.raises(ValueError):
            summarize_balanced_prompt_runs(tuple(forged))
    for wrong in (
        valid[:3], (grounded, baseline, grounded, baseline),
        (baseline, baseline, grounded, grounded),
    ):
        with pytest.raises(ValueError):
            summarize_balanced_prompt_runs(wrong)
    tampered = list(valid)
    tampered[2] = deepcopy(tampered[2])
    tampered[2]["post_execution_e0_stage_funnel"]["e5_fixed5"][
        "supported_fixture_completed"
    ] = 4
    with pytest.raises(ValueError):
        summarize_balanced_prompt_runs(tuple(tampered))


def test_agent_common_source_description_ablation_keeps_exact_tool_view_and_gold():
    """6 original deterministic tasks; fake model never grants real E2 evidence."""
    full_agent = RefusingAgent()
    omit_agent = RefusingAgent()
    backend = CallableDecisionBackend(_first_five)
    baseline = run_fixture(
        backend, full_agent, source_revision="f" * 40,
        system_prompt=GROUNDED_PROMPT,
    )
    omitted = run_fixture(
        backend, omit_agent, source_revision="f" * 40,
        system_prompt=GROUNDED_PROMPT,
        source_arms=("e5_fixed5",),
        omit_identical_descriptions=True,
    )
    assert baseline["arms"] == list(ARMS)
    assert baseline["identical_descriptions_omitted"] is False
    assert omitted["arms"] == ["e5_fixed5"]
    assert omitted["identical_descriptions_omitted"] is True
    assert omitted["source_snapshot_sha256"] == baseline["source_snapshot_sha256"]
    assert len(full_agent.generated) == 12
    assert len(omit_agent.generated) == 6
    # Tool call result/fixture verdicts remain synthetic and private;
    # no additional tool definition is leaked by the short text condition.
    assert all(
        all(item["name"] in {
            tool["name"] for _messages, listed in full_agent.generated
            for tool in listed
        } for item in tools)
        for _messages, tools in omit_agent.generated
    )
    for messages, tools in omit_agent.generated:
        assert messages[0]["content"] == GROUNDED_PROMPT
        assert len(tools) == 5
        assert "required_routes" not in json.dumps(messages)
        assert all(tool["name"] != "service__read" for tool in tools)
    assert omitted["independent_e2_qualified"] is False
    assert omitted["real_qwen_generation_measured"] is False
    assert omitted["real_e5_ranking_measured"] is False
    assert omitted["real_native_provider_execution"] is False
    assert omitted["calibrated_no_fit"] is False
    assert omitted["product_default_promoted"] is False
    with pytest.raises(ValueError, match="provenance"):
        run_fixture(
            backend, RefusingAgent(), source_revision="f" * 40,
            omit_identical_descriptions=True,
        )
    with pytest.raises(ValueError, match="provenance"):
        run_fixture(
            backend, RefusingAgent(), source_revision="f" * 40,
            system_prompt=GROUNDED_PROMPT,
            source_arms=ARMS, omit_identical_descriptions=True,
        )


def test_post_run_rank_scoring_separates_e5_selector_order_from_agent_tool_order():
    ranking = (
        "service_z.read", "service_a.read", "service_u.read",
        "service_c.read", "service_v.read",
    )
    visible = tuple(sorted(ranking))
    assert visible != ranking
    matched = _private_rank_diagnostic(
        ranked=ranking, model_visible=visible,
        attempted=["service_u.read"], gold="service_u.read",
        observed_count=1,
    )
    assert matched == {
        "expected_rank_in_selector_order": 3,
        "first_attempt_rank_in_selector_order": 3,
        "first_attempt_slot_in_model_visible_order": 3,
        "first_attempt_was_expected_operation": True,
        "first_attempt_outside_top5": False,
    }
    wrong = _private_rank_diagnostic(
        ranked=ranking, model_visible=visible,
        attempted=["service_a.read"], gold="service_z.read",
        observed_count=1,
    )
    assert wrong["expected_rank_in_selector_order"] == 1
    assert wrong["first_attempt_rank_in_selector_order"] == 2
    assert wrong["first_attempt_slot_in_model_visible_order"] == 1
    assert wrong["first_attempt_was_expected_operation"] is False
    missing = _private_rank_diagnostic(
        ranked=ranking, model_visible=visible,
        attempted=["unlisted_tool.read"], gold="missing_source.read",
        observed_count=1,
    )
    assert missing["expected_rank_in_selector_order"] is None
    assert missing["first_attempt_rank_in_selector_order"] is None
    assert missing["first_attempt_slot_in_model_visible_order"] is None
    assert missing["first_attempt_was_expected_operation"] is False
    assert missing["first_attempt_outside_top5"] is True
    nothing = _private_rank_diagnostic(
        ranked=ranking, model_visible=visible,
        attempted=[], gold=None, observed_count=0,
    )
    assert nothing["first_attempt_was_expected_operation"] is None
    assert not nothing["first_attempt_outside_top5"]
    for bad in (
        {"ranked": ranking[:4]},
        {"ranked": (ranking[0],) * 5},
        {"model_visible": ranking},
        {"attempted": ["service_a.read"], "observed_count": 2},
    ):
        kwargs = {
            "ranked": ranking, "model_visible": visible,
            "attempted": [], "gold": "service_z.read",
            "observed_count": 0,
        }
        kwargs.update(bad)
        with pytest.raises(ValueError, match="invalid private G5"):
            _private_rank_diagnostic(**kwargs)


def test_post_execution_model_generator_observer_retains_no_arguments_or_raw_answer():
    class DeterministicGenerator:
        def generate(self, _messages, _tools):
            return {
                "text": (
                    '<tool_call>{"name":"service_z__read",'
                    '"arguments":{"account_id":"SECRET_NOT_EXPORTED"}}</tool_call>'
                ),
                "input_tokens": 1, "tool_tokens": 1, "output_tokens": 1,
                "latency_ms": 0.0, "context_overflow": False,
            }

    observer = GraderOnlyAttemptObserver(DeterministicGenerator())
    tools = [{"name": "service_a__read"}, {"name": "service_z__read"}]
    result = observer.generate([{"role": "user", "content": "ask"}], tools)
    assert "SECRET_NOT_EXPORTED" in result["text"]  # unchanged to original runner
    assert observer.first_visible_tools == (
        "service_a.read", "service_z.read",
    )
    assert observer.attempted == ["service_z.read"]
    assert "SECRET_NOT_EXPORTED" not in repr(observer.__dict__)
    assert not hasattr(observer, "raw_outputs")


def test_original_six_fixture_rank_receipts_emit_no_names_or_gold():
    report = run_fixture(
        CallableDecisionBackend(_first_five),
        RefusingAgent(), source_revision="c" * 40,
    )
    ranks = report["post_execution_private_rank_diagnostic"]
    assert ranks["selector_rank_is_model_visible_order"] is False
    assert ranks["tool_or_query_names_exported"] is False
    assert ranks["attempt_arguments_or_generated_text_exported"] is False
    assert ranks["independent_e2_qualified"] is False
    assert ranks["model_visible_order"] == "lexical_sorted_selected_route_names"
    assert set(ranks["by_arm_language"]) == set(ARMS)
    for arm in ARMS:
        assert set(ranks["by_arm_language"][arm]) == {"en", "ko", "ja"}
        for item in ranks["by_arm_language"][arm].values():
            assert item["first_attempt_rank_in_selector_order"] is None
            assert item["first_attempt_slot_in_model_visible_order"] is None
            assert item["first_attempt_was_expected_operation"] is None
            assert item["first_attempt_outside_top5"] is False
            rank = item["expected_rank_in_selector_order"]
            assert rank is None or 1 <= rank <= 5
    exported = json.dumps(ranks, ensure_ascii=False)
    assert "acct_demo_7" not in exported
    assert "service_" not in exported
    assert "required_routes" not in exported
    assert not any(query in exported for _lang, query, _gold in _cases())

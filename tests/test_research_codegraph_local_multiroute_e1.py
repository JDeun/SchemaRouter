"""Source-registered 12+ route E1 scaling control, never independent E2."""

from __future__ import annotations

import json

import pytest

from scripts import research_codegraph_local_multiroute_e1 as local

SCHEMA = (
    '<tool_call>{"name":"research__request_scoped_source_schema",'
    '"arguments":{"route_ids":["contacts.read","cases.read"]}}</tool_call>'
)
CONTACT = '<tool_call>{"name":"contacts__read","arguments":{}}</tool_call>'
CASE = (
    '<tool_call>{"name":"cases__read",'
    '"arguments":{"contact_id":"contact-4","region_id":"region-9"}}</tool_call>'
)
FINAL = '{"case_state":"ready"}'


class MenuAgent:
    def __init__(self, *, missing_tokens=False):
        self.missing_tokens = missing_tokens
        self.offered = []

    def generate(self, messages, tools):
        menu = {tool["name"] for tool in tools}
        self.offered.append(menu)
        source_calls = sum(
            "<tool_call>" in message["content"]
            and any(name in message["content"] for name in (
                "contacts__read", "cases__read",
            ))
            for message in messages
        )
        if menu == {"research__request_scoped_source_schema"}:
            response = SCHEMA
        elif source_calls == 0 and "contacts__read" in menu:
            response = CONTACT
        elif source_calls == 1 and "cases__read" in menu:
            response = CASE
        elif source_calls == 2:
            response = FINAL
        else:
            response = "REQUEST_MORE_TOOLS"
        result = {"text": response, "latency_ms": 1.0, "context_overflow": False}
        if not self.missing_tokens:
            result.update(input_tokens=55, tool_tokens=12, output_tokens=14)
        return result


class BareSchemaOnlyAgent(MenuAgent):
    """Same scripted original source actions, bare initial schema turn only."""

    def generate(self, messages, tools):
        result = super().generate(messages, tools)
        if {tool["name"] for tool in tools} == {
            "research__request_scoped_source_schema",
        }:
            result["text"] = SCHEMA.removeprefix("<tool_call>").removesuffix(
                "</tool_call>",
            )
        return result


@pytest.mark.asyncio
async def test_bare_schema_treatment_changes_only_surgical_host_action_shape():
    original = await local.run_local_multiroute_codegraph_e1(
        BareSchemaOnlyAgent(), language="ko", catalog_size=4,
        diagnose_model_actions=True, experimental_single_step_prompt=True,
    )
    treated = await local.run_local_multiroute_codegraph_e1(
        BareSchemaOnlyAgent(), language="ko", catalog_size=4,
        diagnose_model_actions=True, experimental_single_step_prompt=True,
        experimental_bare_schema_request=True,
    )
    assert original["source_receipt_digest"] == treated["source_receipt_digest"]
    assert original["requested_k"] == treated["requested_k"] == 5
    assert treated["bare_schema_request_treatment"] == "STRICT_HOST_OFFERED_SCHEMA_ONLY"
    assert "bare_schema_request_treatment" not in original
    for before, after in zip(original["outcomes"][:3], treated["outcomes"][:3], strict=True):
        assert before == after
    failed = original["outcomes"][3]
    assert failed["schema_requests"] == failed["actual_source_calls"] == 0
    assert failed["full_task_complete"] is False
    assert "bare_schema_request_normalizations" not in failed
    recovered = treated["outcomes"][3]
    assert recovered["schema_requests"] == recovered["bare_schema_request_normalizations"] == 1
    assert recovered["actual_source_calls"] == 2
    assert recovered["full_task_complete"] is True
    assert recovered["action_structure_labels"][0] == (
        "bare_json_offered_schema_request_shape"
    )
    assert "contact-4" not in json.dumps(treated)


@pytest.mark.parametrize(("size", "condition", "single", "bare", "cue", "schema"), (
    (12, "joined", True, False, False, True),
    (4, "denied", True, False, False, True),
    (4, "joined", False, False, False, True),
    (4, "joined", True, True, False, True),
    (4, "joined", True, False, True, True),
    (4, "joined", True, False, False, 1),
))
@pytest.mark.asyncio
async def test_bare_schema_treatment_rejects_mixed_or_unsafe_cohorts(
    size, condition, single, bare, cue, schema,
):
    with pytest.raises(ValueError, match="bare schema"):
        await local.run_local_multiroute_codegraph_e1(
            BareSchemaOnlyAgent(), language="en", condition=condition,
            catalog_size=size, experimental_single_step_prompt=single,
            experimental_bare_native_json=bare,
            experimental_g5_verified_continuation=cue,
            experimental_bare_schema_request=schema,
        )


@pytest.mark.asyncio
async def test_graph_path_order_cue_affects_only_surgical_system_prompt():
    class RecordingAgent(BareSchemaOnlyAgent):
        def __init__(self):
            super().__init__()
            self.system_messages = []

        def generate(self, messages, tools):
            self.system_messages.append(messages[0]["content"])
            return super().generate(messages, tools)

    original_agent, treated_agent = RecordingAgent(), RecordingAgent()
    original = await local.run_local_multiroute_codegraph_e1(
        original_agent, language="ja", catalog_size=4,
        experimental_single_step_prompt=True,
        experimental_bare_schema_request=True,
    )
    treated = await local.run_local_multiroute_codegraph_e1(
        treated_agent, language="ja", catalog_size=4,
        experimental_single_step_prompt=True,
        experimental_bare_schema_request=True,
        experimental_graph_path_order_prompt=True,
    )
    assert original["outcomes"] == treated["outcomes"]
    assert treated["graph_path_order_treatment"] == "STATIC_G5_DEPENDENCY_ORDER_CUE"
    assert "graph_path_order_treatment" not in original
    assert len(original_agent.system_messages) == len(treated_agent.system_messages)
    assert original_agent.system_messages[:7] == treated_agent.system_messages[:7]
    assert treated_agent.system_messages[-1] != original_agent.system_messages[-1]
    assert "route_sets" in treated_agent.system_messages[-1]


@pytest.mark.asyncio
@pytest.mark.parametrize(("size", "single", "schema", "bare", "cue", "order"), (
    (12, True, True, False, False, True),
    (4, False, True, False, False, True),
    (4, True, False, False, False, True),
    (4, True, True, True, False, True),
    (4, True, True, False, True, True),
    (4, True, True, False, False, 1),
))
async def test_graph_path_order_cue_rejects_unsafe_or_mixed_cohorts(
    size, single, schema, bare, cue, order,
):
    with pytest.raises(ValueError, match="graph path order"):
        await local.run_local_multiroute_codegraph_e1(
            BareSchemaOnlyAgent(), language="en", catalog_size=size,
            experimental_single_step_prompt=single,
            experimental_bare_schema_request=schema,
            experimental_bare_native_json=bare,
            experimental_g5_verified_continuation=cue,
            experimental_graph_path_order_prompt=order,
        )


def test_fixture_registers_at_least_ten_real_read_only_host_routes():
    source = local.build_local_multiroute_source(language="en")
    tools = source.router.registry.tools()
    routes = [endpoint for tool in tools for endpoint in tool.endpoints]
    assert len(routes) >= 12
    assert len({tool.key for tool in tools}) >= 12
    assert all(endpoint.read_only and not endpoint.destructive for endpoint in routes)
    assert all(source.router.executor is not None for _ in tools)
    assert len(source.registered_callbacks) == len(routes)
    assert source.episode.selection.status == "complete"
    assert source.episode.selection.route_ids == ("contacts.read", "cases.read")


@pytest.mark.parametrize("language", ("en", "ko", "ja"))
@pytest.mark.asyncio
async def test_en_ko_ja_two_step_calls_are_actual_registered_callbacks(language):
    result = await local.run_local_multiroute_codegraph_e1(
        MenuAgent(), language=language, condition="joined",
    )
    surgical = next(row for row in result["outcomes"]
                    if row["condition"] == "surgical_g5_e1")
    assert surgical["schema_requests"] == 1
    assert surgical["actual_source_calls"] == 2
    assert surgical["full_task_complete"] is True
    assert surgical["model_turns"] == 4
    assert surgical["total_model_tokens"] == 4 * (55 + 14)
    assert result["source_route_count"] >= 12
    assert result["evidence_tier"] == "E1_LOCAL_SOURCE_CONTROL"


@pytest.mark.asyncio
async def test_local_full_lexical_g5_surgical_share_exact_source_witness():
    result = await local.run_local_multiroute_codegraph_e1(
        MenuAgent(), language="en", condition="joined",
    )
    assert result["arms"] == (
        "all_visible", "lexical_k5", "concept_graph_optin", "surgical_g5_e1",
    )
    assert len({row["source_receipt_digest"] for row in result["outcomes"]}) == 1
    # The original scoped menu's maximum is 5; do not bypass it by splitting
    # the FULL menu into fake batches to claim a 12-route token comparison.
    full = next(row for row in result["outcomes"]
                if row["condition"] == "all_visible")
    assert full["status"] == "BLOCKED_MENU_CAP"
    assert full["total_model_tokens"] is None
    assert result["task_success_rate"] is None


@pytest.mark.parametrize("condition", ("denied", "no_fit", "over_k"))
@pytest.mark.asyncio
async def test_denied_no_fit_over_k_stop_before_source_access(condition):
    agent = MenuAgent()
    result = await local.run_local_multiroute_codegraph_e1(
        agent, language="en", condition=condition,
    )
    assert result["status"] == {
        "denied": "BLOCKED_AUTHORIZATION",
        "no_fit": "BLOCKED_NO_PROVEN_HIT",
        "over_k": "BLOCKED_OVER_K_UNRANKED",
    }[condition]
    assert result["source_call_count"] == 0
    assert result["qualified_task_denominator"] is None
    assert agent.offered == []


@pytest.mark.asyncio
async def test_fixture_cost_includes_schema_round_trip_and_all_model_turns():
    result = await local.run_local_multiroute_codegraph_e1(
        MenuAgent(), language="en", condition="joined",
    )
    surgical = next(row for row in result["outcomes"]
                    if row["condition"] == "surgical_g5_e1")
    assert surgical["tool_schema_tokens"] == 4 * 12
    assert surgical["model_input_tokens"] == 4 * 55
    assert surgical["model_output_tokens"] == 4 * 14

    no_receipts = await local.run_local_multiroute_codegraph_e1(
        MenuAgent(missing_tokens=True), language="en", condition="joined",
    )
    surgical_missing = next(row for row in no_receipts["outcomes"]
                            if row["condition"] == "surgical_g5_e1")
    assert surgical_missing["total_model_tokens"] is None


@pytest.mark.asyncio
async def test_no_claim_of_independent_or_remote_provider_evidence():
    result = await local.run_local_multiroute_codegraph_e1(
        MenuAgent(), language="en", condition="joined",
    )
    assert result["original_provider_e1"] is False
    assert result["independent_e2_qualified"] is False
    assert result["release_qualified"] is False
    assert "contact-4" not in json.dumps(result)
    assert "region-9" not in json.dumps(result)


@pytest.mark.parametrize("language", ("en", "ko", "ja"))
@pytest.mark.asyncio
async def test_k5_safe_four_route_cohort_has_genuinely_comparable_full_arm(language):
    """Never split the 12-route FULL menu; preregister a separate source."""
    source = local.build_local_multiroute_source(
        language=language, catalog_size=4,
    )
    assert len(source.registered_callbacks) == 4
    assert source.episode is not None
    assert source.episode.selection.status == "complete"
    agent = MenuAgent()
    result = await local.run_local_multiroute_codegraph_e1(
        agent, language=language, catalog_size=4,
    )
    assert result["status"] == "E1_MEASURED_LOCAL_FOUR_ARM_NOT_E2"
    assert result["source_route_count"] == 4
    assert result["qualified_task_denominator"] == {
        arm: 1 for arm in local.ARMS
    }
    assert set(result["task_success_rate"]) == set(local.ARMS)
    assert all(type(rate) is float and rate in (0.0, 1.0)
               for rate in result["task_success_rate"].values())
    rows = result["outcomes"]
    assert len(rows) == 4
    assert len({row["source_receipt_digest"] for row in rows}) == 1
    assert rows[0]["condition"] == "all_visible"
    assert rows[0]["status"] != "BLOCKED_MENU_CAP"
    assert rows[0]["model_turns"] >= 1
    assert all(row["model_turns"] >= 1 for row in rows)
    assert rows[-1]["schema_requests"] == 1
    assert rows[-1]["actual_source_calls"] == 2
    assert result["independent_e2_qualified"] is False
    assert result["release_qualified"] is False
    assert result["original_provider_e1"] is False
    assert "contact-4" not in json.dumps(result)


@pytest.mark.parametrize("size", (0, 3, 5, 13, True, "4"))
def test_local_source_refuses_unreviewed_comparison_catalog_sizes(size):
    with pytest.raises(ValueError, match="only preregistered"):
        local.build_local_multiroute_source(
            language="en", catalog_size=size,
        )


@pytest.mark.parametrize("condition", ("denied", "no_fit", "over_k"))
def test_four_route_comparable_source_does_not_relabel_negative_cohorts(condition):
    with pytest.raises(ValueError, match="requires the joined task"):
        local.build_local_multiroute_source(
            language="en", catalog_size=4, condition=condition,
        )


@pytest.mark.asyncio
async def test_frozen_twelve_route_scaling_negative_preserved():
    result = await local.run_local_multiroute_codegraph_e1(
        MenuAgent(), language="en", catalog_size=12,
    )
    assert result["status"] == "INCOMPARABLE_FULL_MENU_CAP"
    assert result["source_route_count"] == 12
    assert result["task_success_rate"] is None
    assert result["qualified_task_denominator"] is None
    assert result["outcomes"][0]["status"] == "BLOCKED_MENU_CAP"


@pytest.mark.asyncio
async def test_optin_structure_labels_do_not_change_source_calls_or_gold():
    from scripts.research_codegraph_action_shape_e1 import CATEGORIES

    baseline = await local.run_local_multiroute_codegraph_e1(
        MenuAgent(), language="ko", catalog_size=4,
    )
    diagnosed = await local.run_local_multiroute_codegraph_e1(
        MenuAgent(), language="ko", catalog_size=4,
        diagnose_model_actions=True,
    )
    assert "action_structure_labels" not in json.dumps(baseline)
    assert diagnosed["status"] == baseline["status"]
    assert diagnosed["task_success_rate"] == baseline["task_success_rate"]
    assert diagnosed["source_call_count"] == baseline["source_call_count"]
    assert diagnosed["qualified_task_denominator"] == baseline["qualified_task_denominator"]
    for first, second in zip(baseline["outcomes"], diagnosed["outcomes"], strict=True):
        assert second["action_structure_labels"]
        labels = second["action_structure_labels"]
        assert len(labels) == second["model_turns"]
        assert set(labels) <= CATEGORIES
        assert second["total_model_tokens"] == first["total_model_tokens"]
        assert second["actual_source_calls"] == first["actual_source_calls"]
    assert "contact-4" not in json.dumps(diagnosed)
    assert "region-9" not in json.dumps(diagnosed)


class BareJsonNativeMenuAgent(MenuAgent):
    """Native JSON calls; advance only on observed original host callbacks."""

    def generate(self, messages, tools):
        menu = {tool["name"] for tool in tools}
        self.offered.append(menu)
        observed_source_steps = sum(
            row["role"] == "tool" and "tool_definitions" not in row["content"]
            for row in messages
        )
        if menu == {"research__request_scoped_source_schema"}:
            response = SCHEMA
        elif observed_source_steps == 0 and "contacts__read" in menu:
            response = CONTACT[len("<tool_call>"):-len("</tool_call>")]
        elif observed_source_steps == 1 and "cases__read" in menu:
            response = CASE[len("<tool_call>"):-len("</tool_call>")]
        elif observed_source_steps == 2:
            response = FINAL
        else:
            response = "REQUEST_MORE_TOOLS"
        return {
            "text": response, "latency_ms": 1.0, "context_overflow": False,
            "input_tokens": 55, "tool_tokens": 12, "output_tokens": 14,
        }


@pytest.mark.asyncio
async def test_bare_native_treatment_is_a_distinct_four_route_scored_arm():
    # Baseline makes no original calls because strict parser sees a final JSON;
    # the opt-in calls still require the same offered route/source/arguments.
    baseline = await local.run_local_multiroute_codegraph_e1(
        BareJsonNativeMenuAgent(), language="ko", catalog_size=4,
        diagnose_model_actions=True,
    )
    trial = await local.run_local_multiroute_codegraph_e1(
        BareJsonNativeMenuAgent(), language="ko", catalog_size=4,
        diagnose_model_actions=True, experimental_bare_native_json=True,
    )
    assert baseline["source_call_count"] == 0
    assert trial["source_call_count"] >= 2
    assert trial["bare_native_json_treatment"] == "STRICT_ONE_OFFERED_NATIVE_ONLY"
    assert "bare_native_json_treatment" not in baseline
    assert trial["qualified_task_denominator"] == baseline["qualified_task_denominator"]
    assert trial["independent_e2_qualified"] is False
    assert trial["release_qualified"] is False
    assert trial["task_success_rate"]["all_visible"] == 1.0
    assert trial["task_success_rate"]["lexical_k5"] == 1.0
    assert any(
        row.get("bare_json_strict_parser_acceptances", 0) >= 2
        for row in trial["outcomes"]
    )
    assert all(
        row["action_structure_labels"][0] in (
            "bare_json_tool_action", "valid_schema_request_shape",
        )
        for row in trial["outcomes"]
    )
    assert "contact-4" not in json.dumps(trial)
    assert "region-9" not in json.dumps(trial)


@pytest.mark.parametrize("size", (12, 500, False, "4"))
@pytest.mark.asyncio
async def test_bare_native_treatment_never_widens_twelve_route_full(size):
    with pytest.raises(ValueError, match="requires four routes"):
        await local.run_local_multiroute_codegraph_e1(
            MenuAgent(), language="en", catalog_size=size,
            experimental_bare_native_json=True,
        )


class OneStepPromptCaptureAgent(MenuAgent):
    def __init__(self):
        super().__init__()
        self.system_messages = []

    def generate(self, messages, tools):
        self.system_messages.append(messages[0]["content"])
        return super().generate(messages, tools)


@pytest.mark.asyncio
async def test_single_step_prompt_is_new_treatment_without_new_parser_or_tool_access():
    from scripts.research_codegraph_surgical_agent_e1 import (
        SINGLE_STEP_PROTOCOL_E1,
    )

    original_agent = OneStepPromptCaptureAgent()
    treatment_agent = OneStepPromptCaptureAgent()
    baseline = await local.run_local_multiroute_codegraph_e1(
        original_agent, language="ja", catalog_size=4,
        diagnose_model_actions=True,
    )
    treatment = await local.run_local_multiroute_codegraph_e1(
        treatment_agent, language="ja", catalog_size=4,
        diagnose_model_actions=True, experimental_single_step_prompt=True,
    )
    assert "prompt_treatment" not in baseline
    assert treatment["prompt_treatment"] == "EXACTLY_ONE_NATIVE_ACTION_PER_TURN"
    assert baseline["source_receipt_digest"] == treatment["source_receipt_digest"]
    assert baseline["task_success_rate"] == treatment["task_success_rate"]
    assert baseline["source_call_count"] == treatment["source_call_count"]
    assert baseline["qualified_task_denominator"] == treatment["qualified_task_denominator"]
    assert baseline["requested_k"] == treatment["requested_k"] == 5
    assert baseline["max_model_turns"] == treatment["max_model_turns"]
    assert all(SINGLE_STEP_PROTOCOL_E1 not in msg for msg in original_agent.system_messages)
    assert all(SINGLE_STEP_PROTOCOL_E1 in msg for msg in treatment_agent.system_messages)
    assert "contact-4" not in json.dumps(treatment)
    assert "region-9" not in json.dumps(treatment)
    assert "bare_native_json_treatment" not in treatment
    for before, after in zip(baseline["outcomes"], treatment["outcomes"], strict=True):
        assert before["model_turns"] == after["model_turns"]
        assert before["actual_source_calls"] == after["actual_source_calls"]
        assert before["full_task_complete"] == after["full_task_complete"]
        assert after["action_structure_labels"] == before["action_structure_labels"]


@pytest.mark.parametrize(("size", "bare", "single"), (
    (12, False, True),
    (4, True, True),
    (4, False, 1),
    (4, False, "yes"),
))
@pytest.mark.asyncio
async def test_single_step_prompt_rejects_mixed_or_unsafe_research_conditions(
    size, bare, single,
):
    with pytest.raises(ValueError, match="one-step|treatments|prompt flag"):
        await local.run_local_multiroute_codegraph_e1(
            MenuAgent(), language="en", catalog_size=size,
            experimental_bare_native_json=bare,
            experimental_single_step_prompt=single,
        )


class VerifiedG5ProgressSpy(MenuAgent):
    """Tests can inspect transient model input; no prompt is persisted by E1."""

    def __init__(self):
        super().__init__()
        self.frames = []

    def generate(self, messages, tools):
        self.frames.append(tuple(
            (entry["role"], entry["content"]) for entry in messages
        ))
        return super().generate(messages, tools)


@pytest.mark.asyncio
async def test_verified_continuation_sent_only_after_first_actual_g5_callback():
    from scripts.research_codegraph_local_multiroute_e1 import (
        G5_VERIFIED_CONTINUATION_CUE_E1,
    )

    original = VerifiedG5ProgressSpy()
    treated = VerifiedG5ProgressSpy()
    base = await local._baseline_local_arm(
        original, source=local.build_local_multiroute_source(
            language="en", catalog_size=4,
        ), condition="concept_graph_optin",
        experimental_single_step_prompt=True,
    )
    trial = await local._baseline_local_arm(
        treated, source=local.build_local_multiroute_source(
            language="en", catalog_size=4,
        ), condition="concept_graph_optin",
        experimental_single_step_prompt=True,
        experimental_g5_verified_continuation=True,
    )
    assert base["full_task_complete"] == trial["full_task_complete"] is True
    assert base["actual_source_calls"] == trial["actual_source_calls"] == 2
    assert trial["verified_continuation_cues"] == 1
    assert "verified_continuation_cues" not in base
    assert all(
        G5_VERIFIED_CONTINUATION_CUE_E1 not in content
        for frame in original.frames for _, content in frame
    )
    assert all(
        G5_VERIFIED_CONTINUATION_CUE_E1 not in content
        for _, content in treated.frames[0]
    )
    assert sum(
        G5_VERIFIED_CONTINUATION_CUE_E1 == content
        for _, content in treated.frames[1]
    ) == 1
    assert "case_state" not in G5_VERIFIED_CONTINUATION_CUE_E1
    assert "contact_id" not in G5_VERIFIED_CONTINUATION_CUE_E1
    assert "contact-4" not in json.dumps(trial)


@pytest.mark.asyncio
async def test_verified_continuation_preserves_full_and_lexical_original_arms():
    before = await local.run_local_multiroute_codegraph_e1(
        MenuAgent(), language="ko", catalog_size=4,
        diagnose_model_actions=True,
        experimental_single_step_prompt=True,
    )
    after = await local.run_local_multiroute_codegraph_e1(
        MenuAgent(), language="ko", catalog_size=4,
        diagnose_model_actions=True,
        experimental_single_step_prompt=True,
        experimental_g5_verified_continuation=True,
    )
    assert after["continuation_treatment"] == "AFTER_VERIFIED_FIRST_G5_CALL"
    assert "continuation_treatment" not in before
    assert after["source_receipt_digest"] == before["source_receipt_digest"]
    assert after["requested_k"] == before["requested_k"] == 5
    assert after["qualified_task_denominator"] == before["qualified_task_denominator"]
    assert after["task_success_rate"] == before["task_success_rate"]
    assert after["source_call_count"] == before["source_call_count"]
    for original, treatment in zip(before["outcomes"], after["outcomes"], strict=True):
        assert original["condition"] == treatment["condition"]
        assert original["actual_source_calls"] == treatment["actual_source_calls"]
        assert original["full_task_complete"] == treatment["full_task_complete"]
        if original["condition"] == "concept_graph_optin":
            assert treatment["verified_continuation_cues"] == 1
        else:
            assert "verified_continuation_cues" not in treatment
    assert "contact-4" not in json.dumps(after)
    assert "region-9" not in json.dumps(after)


@pytest.mark.parametrize(("size", "condition", "bare", "one_step", "cue"), (
    (12, "joined", False, True, True),
    (4, "joined", True, True, True),
    (4, "joined", False, False, True),
    (4, "denied", False, True, True),
    (4, "joined", False, True, 1),
    (4, "joined", False, True, "true"),
))
@pytest.mark.asyncio
async def test_verified_continuation_cannot_change_cohort_or_combine_interventions(
    size, condition, bare, one_step, cue,
):
    with pytest.raises(ValueError, match="continuation"):
        await local.run_local_multiroute_codegraph_e1(
            MenuAgent(), language="ja", condition=condition, catalog_size=size,
            experimental_bare_native_json=bare,
            experimental_single_step_prompt=one_step,
            experimental_g5_verified_continuation=cue,
        )


@pytest.mark.parametrize("failure", ("native_host_denied", "non_ok_observation"))
@pytest.mark.asyncio
async def test_verified_g5_cue_refuses_failed_first_original_source(monkeypatch, failure):
    """No false verified progress after an original denied/non-ok callback."""
    async def denied_or_unavailable(*_args, **_kwargs):
        if failure == "native_host_denied":
            raise ValueError("source authorization revoked")
        return {"status": "unavailable"}

    monkeypatch.setattr(local, "execute_scoped_host_call", denied_or_unavailable)
    source = local.build_local_multiroute_source(
        language="en", catalog_size=4,
    )
    agent = VerifiedG5ProgressSpy()
    row = await local._baseline_local_arm(
        agent, source=source, condition="concept_graph_optin",
        experimental_single_step_prompt=True,
        experimental_g5_verified_continuation=True,
    )
    assert row["status"] == {
        "native_host_denied": "native_host_call_denied",
        "non_ok_observation": "non_ok_observation",
    }[failure]
    assert row["actual_source_calls"] == 0
    assert row["verified_continuation_cues"] == 0
    assert row["full_task_complete"] is False
    assert len(agent.frames) == 1
    assert source.callback_log == []
    assert "contact-4" not in json.dumps(row)


@pytest.mark.asyncio
async def test_verified_g5_cue_refuses_out_of_order_model_action():
    """No progress cue from an unbound requested second tool."""
    class WrongFirstAgent:
        def generate(self, messages, tools):
            del messages, tools
            return {
                "text": CASE, "context_overflow": False,
                "input_tokens": 12, "tool_tokens": 4, "output_tokens": 9,
            }

    source = local.build_local_multiroute_source(
        language="ko", catalog_size=4,
    )
    row = await local._baseline_local_arm(
        WrongFirstAgent(), source=source, condition="concept_graph_optin",
        experimental_single_step_prompt=True,
        experimental_g5_verified_continuation=True,
    )
    assert row["status"] == "unoffered_or_out_of_order_route"
    assert row["actual_source_calls"] == 0
    assert row["verified_continuation_cues"] == 0
    assert row["full_task_complete"] is False
    assert source.callback_log == []

@pytest.mark.asyncio
async def test_graph_frontier_fifth_arm_preserves_four_controls():
    baseline = await local.run_local_multiroute_codegraph_e1(
        MenuAgent(), language="ko", catalog_size=4,
        experimental_single_step_prompt=True,
        experimental_bare_schema_request=True,
        experimental_graph_path_order_prompt=True,
    )
    treated = await local.run_local_multiroute_codegraph_e1(
        MenuAgent(), language="ko", catalog_size=4,
        experimental_single_step_prompt=True,
        experimental_bare_schema_request=True,
        experimental_graph_path_order_prompt=True,
        experimental_graph_frontier=True,
    )
    assert tuple(baseline["arms"]) == local.ARMS
    assert tuple(treated["arms"]) == (*local.ARMS, "graph_frontier_g5_e1")
    assert len(baseline["outcomes"]) == 4
    assert len(treated["outcomes"]) == 5
    assert baseline["source_receipt_digest"] == treated["source_receipt_digest"]
    assert treated["status"] == "E1_MEASURED_LOCAL_FIVE_ARM_NOT_E2"
    assert treated["qualified_task_denominator"] == {
        arm: 1 for arm in treated["arms"]
    }
    frontier = treated["outcomes"][-1]
    assert frontier["frontier_sizes"] == [1, 1, 0]
    assert frontier["schema_requests"] == 0
    assert frontier["actual_source_calls"] == 2
    assert frontier["full_task_complete"] is True
    assert treated["independent_e2_qualified"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("flags", [
    {},
    {"experimental_single_step_prompt": True},
    {"experimental_single_step_prompt": True,
     "experimental_bare_schema_request": True},
])
async def test_graph_frontier_rejects_unsafe_partial_flag_combinations(flags):
    with pytest.raises(ValueError, match="frontier"):
        await local.run_local_multiroute_codegraph_e1(
            MenuAgent(), language="ko", catalog_size=4,
            experimental_graph_frontier=True, **flags,
        )


@pytest.mark.asyncio
async def test_e1_final_taxonomy_preserves_exact_existing_scoring():
    baseline = await local.run_local_multiroute_codegraph_e1(
        MenuAgent(), language="en", catalog_size=4,
    )
    observed = await local.run_local_multiroute_codegraph_e1(
        MenuAgent(), language="en", catalog_size=4,
        diagnose_model_actions=True,
    )
    assert baseline["task_success_rate"] == observed["task_success_rate"]
    assert baseline["source_call_count"] == observed["source_call_count"]
    for row in observed["outcomes"]:
        assert row["full_task_complete"] is True
        assert row["final_outcome_category"] == "strict_correct"


@pytest.mark.asyncio
async def test_e1_final_taxonomy_distinguishes_formatting_from_wrong_final():
    class FencedFinal(MenuAgent):
        def generate(self, messages, tools):
            row = super().generate(messages, tools)
            if row["text"] == FINAL:
                row["text"] = "```json\\n" + FINAL + "\\n```"
            return row

    observed = await local.run_local_multiroute_codegraph_e1(
        FencedFinal(), language="en", catalog_size=4,
        diagnose_model_actions=True,
    )
    assert all(row["actual_source_calls"] == 2 for row in observed["outcomes"])
    assert all(row["full_task_complete"] is False for row in observed["outcomes"])
    assert all(
        row["final_outcome_category"] == "markdown_fenced_not_strict_json"
        for row in observed["outcomes"]
    )


@pytest.mark.asyncio
async def test_e1_final_taxonomy_repeated_tool_after_real_two_hop_is_denied():
    class ExtraTool(MenuAgent):
        def generate(self, messages, tools):
            row = super().generate(messages, tools)
            if row["text"] == FINAL:
                row["text"] = CONTACT
            return row

    observed = await local.run_local_multiroute_codegraph_e1(
        ExtraTool(), language="en", catalog_size=4,
        diagnose_model_actions=True,
        experimental_single_step_prompt=True,
        experimental_bare_schema_request=True,
        experimental_graph_path_order_prompt=True,
        experimental_graph_frontier=True,
    )
    assert all(row["actual_source_calls"] == 2 for row in observed["outcomes"])
    assert all(row["full_task_complete"] is False for row in observed["outcomes"])
    assert all(
        row["final_outcome_category"] == "extra_native_call_after_two_source_calls"
        for row in observed["outcomes"]
    )

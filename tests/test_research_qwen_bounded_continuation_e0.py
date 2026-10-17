"""One host-attested generic incomplete-turn retry, zero gold disclosure."""
from __future__ import annotations

import json

import pytest

from scripts.research_bound_two_step_host_e0 import CANARY
from scripts.research_real_qwen_bound_two_step_e0 import (
    HOST_INCOMPLETE_PROMPT,
    run_model_selected_bound_two_step_e0,
)

FIRST = (
    '<tool_call>{"name":"marine__read",'
    '"arguments":{"place":"Seoul"}}</tool_call><|im_end|>'
)


class BoundedAgent:
    def __init__(self, *, after_reminder: str = "call", first_call=True):
        self.after_reminder = after_reminder
        self.first_call = first_call
        self.turns = 0

    def generate(self, messages, tools):
        assert CANARY not in json.dumps({"messages": messages, "tools": tools})
        assert "vault__read" not in json.dumps(tools)
        self.turns += 1
        if self.turns == 1:
            value = FIRST if self.first_call else '{"verified":true}<|im_end|>'
        elif self.turns == 2:
            assert messages[-1]["role"] == "tool"
            value = '{"verified":true}<|im_end|>'  # premature fabricated final
        elif self.turns == 3:
            assert messages[-1] == {
                "role": "user", "content": HOST_INCOMPLETE_PROMPT,
            }
            assert "papers" not in HOST_INCOMPLETE_PROMPT
            assert "record-321" not in HOST_INCOMPLETE_PROMPT
            assert "marine" not in HOST_INCOMPLETE_PROMPT
            assert "verified" not in HOST_INCOMPLETE_PROMPT
            if self.after_reminder == "final":
                value = '{"verified":true}<|im_end|>'
            else:
                prior = next(
                    msg["content"] for msg in reversed(messages)
                    if msg["role"] == "tool"
                )
                public = json.loads(prior.splitlines()[1])
                assert public["status"] == "ok"
                assert "secret" not in public
                value = (
                    "<tool_call>"
                    + json.dumps({
                        "name": "papers__read",
                        "arguments": {"record_id": public["record_id"]},
                    }) + "</tool_call><|im_end|>"
                )
        elif self.turns == 4:
            assert messages[-1]["role"] == "tool"
            final = json.loads(messages[-1]["content"].splitlines()[1])
            value = json.dumps({"verified": final["verified"]}) + "<|im_end|>"
        else:
            raise AssertionError("model invoked more than a bounded four-turn budget")
        return {"text": value, "context_overflow": False}


@pytest.mark.asyncio
@pytest.mark.parametrize("language", ("en", "ko", "ja"))
async def test_bounded_host_reminder_recovers_two_step_task_without_gold(language):
    model = BoundedAgent()
    report = await run_model_selected_bound_two_step_e0(
        model, language=language, host_continuation_budget=1,
    )
    assert model.turns == 4
    assert report["host_continuation_budget"] == 1
    assert report["host_continuations_issued"] == 1
    assert report["actual_bound_host_calls"] == 2
    assert report["correct_strict_final_answer"] is True
    assert report["full_task_correct"] is True
    assert report["termination_reason"] == "terminal_after_two_steps"
    assert report["actual_model_inference_measured"] is False
    assert report["independent_e2_qualified"] is False
    for unsafe in (CANARY, "record-321", "Seoul", "papers.read"):
        assert unsafe not in json.dumps(report)


@pytest.mark.asyncio
async def test_old_raw_behavior_remains_stable_no_host_reminder():
    result = await run_model_selected_bound_two_step_e0(
        BoundedAgent(), language="en",
    )
    assert result["host_continuation_budget"] == 0
    assert result["host_continuations_issued"] == 0
    assert result["actual_bound_host_calls"] == 1
    assert result["full_task_correct"] is False
    assert result["termination_reason"] == "premature_final"


@pytest.mark.asyncio
async def test_second_premature_final_still_fails_without_more_prompting():
    model = BoundedAgent(after_reminder="final")
    result = await run_model_selected_bound_two_step_e0(
        model, language="en", host_continuation_budget=1,
    )
    assert model.turns == 3
    assert result["host_continuations_issued"] == 1
    assert result["actual_bound_host_calls"] == 1
    assert result["full_task_correct"] is False
    assert result["termination_reason"] == "premature_final"


@pytest.mark.asyncio
async def test_host_does_not_rescue_entirely_unperformed_task_with_oracle_hint():
    model = BoundedAgent(first_call=False)
    result = await run_model_selected_bound_two_step_e0(
        model, language="ja", host_continuation_budget=1,
    )
    assert model.turns == 1
    assert result["actual_bound_host_calls"] == 0
    assert result["host_continuations_issued"] == 0
    assert result["full_task_correct"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", (True, False, -1, 2, 1.0, "1", None))
async def test_host_continuation_limit_is_strictly_one_and_not_a_boolean(invalid):
    with pytest.raises(ValueError, match="budget"):
        await run_model_selected_bound_two_step_e0(
            BoundedAgent(), language="en", host_continuation_budget=invalid,
        )


@pytest.mark.asyncio
async def test_policy_revocation_after_reminder_still_denies_second_native_call():
    from schemarouter import AuthorizationPolicy, AuthorizationRule

    def revoke(router, _view):
        router.authorization_policy = AuthorizationPolicy(
            default_effect="deny",
            rules=(AuthorizationRule(
                effect="deny", operation="*.*", roles_any=("reader",),
            ),),
        )
    result = await run_model_selected_bound_two_step_e0(
        BoundedAgent(), language="ko",
        host_continuation_budget=1, revoke_before_second=revoke,
    )
    assert result["actual_bound_host_calls"] == 1
    assert result["host_continuations_issued"] == 1
    assert result["unexpected_or_denied_model_call"] is True
    assert result["full_task_correct"] is False

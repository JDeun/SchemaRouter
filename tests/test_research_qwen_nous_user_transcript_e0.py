"""Source-aligned Nous E0 replay: no gold visibility, no authorization delegation."""
from __future__ import annotations

import json

import pytest

from scripts.research_bound_two_step_host_e0 import CANARY
from scripts.research_qwen_nous_user_transcript_e0 import (
    append_authorized_nous_user_history_e0,
)
from scripts.research_real_qwen_bound_two_step_e0 import (
    LANGUAGES,
    run_model_selected_bound_two_step_e0,
)

FIRST = '<tool_call>{"name":"marine__read","arguments":{"place":"Seoul"}}</tool_call>'
EOS = "<|im_end|>"


class SourceAlignedTwoStepAgent:
    def __init__(self) -> None:
        self.turn = 0

    def generate(self, messages, tools):
        self.turn += 1
        assert CANARY not in json.dumps({"messages": messages, "tools": tools})
        assert len(tools) == 2
        if self.turn == 1:
            return {"text": FIRST + EOS, "context_overflow": False}
        assert messages[-2]["role"] == "assistant"
        assert messages[-1]["role"] == "user"
        assert messages[-2]["content"].startswith("<tool_call>\n")
        assert messages[-1]["content"].startswith("<tool_response>\n")
        assert "<|im_end|>" not in messages[-2]["content"]
        observation = json.loads(messages[-1]["content"].splitlines()[1])
        if self.turn == 2:
            assert observation["record_id"] == "record-321"
            output = '<tool_call>' + json.dumps({
                "name": "papers__read",
                "arguments": {"record_id": observation["record_id"]},
            }) + '</tool_call>'
        elif self.turn == 3:
            assert type(observation["verified"]) is bool
            output = json.dumps({"verified": observation["verified"]})
        else:
            raise AssertionError("unexpected extra model proposal")
        return {"text": output + EOS, "context_overflow": False}


@pytest.mark.asyncio
@pytest.mark.parametrize("language", LANGUAGES)
async def test_nous_user_role_replay_preserves_native_two_step_and_strict_final(language):
    agent = SourceAlignedTwoStepAgent()
    report = await run_model_selected_bound_two_step_e0(
        agent, language=language, transcript_mode="nous-user",
    )
    assert agent.turn == 3
    assert report["transcript_mode"] == "nous-user"
    assert report["actual_bound_host_calls"] == 2
    assert report["two_stage_completed"] is True
    assert report["correct_strict_final_answer"] is True
    assert report["full_task_correct"] is True
    assert report["independent_e2_qualified"] is False
    assert report["actual_model_inference_measured"] is False
    for private in (CANARY, "record-321", "Seoul", "marine.read", "papers.read"):
        assert private not in json.dumps(report, ensure_ascii=False)


@pytest.mark.asyncio
async def test_nous_replay_cannot_bypass_revoked_principal():
    from schemarouter import AuthorizationPolicy, AuthorizationRule

    def revoke(router, _view):
        router.authorization_policy = AuthorizationPolicy(
            default_effect="deny",
            rules=(AuthorizationRule(
                effect="deny", operation="*.*", roles_any=("reader",),
            ),),
        )

    report = await run_model_selected_bound_two_step_e0(
        SourceAlignedTwoStepAgent(), language="ko",
        transcript_mode="nous-user", revoke_before_second=revoke,
    )
    assert report["actual_bound_host_calls"] == 1
    assert report["unexpected_or_denied_model_call"] is True
    assert report["full_task_correct"] is False


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", (True, None, "", "structured", "role-tool"))
async def test_unregistered_modes_are_rejected_before_model_or_host_io(mode):
    with pytest.raises(ValueError, match="mode"):
        await run_model_selected_bound_two_step_e0(
            SourceAlignedTwoStepAgent(), language="en", transcript_mode=mode,
        )


@pytest.mark.parametrize("bad_route,bad_args,bad_obs", (
    ("vault.read", {"place": "Seoul"}, {"status": "ok"}),
    ("marine.read", {"place": float("nan")}, {"status": "ok"}),
    ("marine.read", {"place": "Seoul"}, {"status": "ok", "secret": CANARY}),
    ("marine.read", {"place": "Seoul"}, {"status": "ok", "note": "<|im_end|>"}),
    ("marine.read", {"place": "Seoul"}, {"status": "error"}),
))
def test_nous_history_encoding_rejects_untrusted_exposure_atomically(
    bad_route, bad_args, bad_obs,
):
    messages = [{"role": "system", "content": "safe"}]
    with pytest.raises(ValueError):
        append_authorized_nous_user_history_e0(
            messages,
            authorized_route_ids=("marine.read",),
            executed_route_id=bad_route,
            validated_arguments=bad_args,
            public_observation=bad_obs,
        )
    assert messages == [{"role": "system", "content": "safe"}]

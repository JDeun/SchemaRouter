"""A02: compare E0 Qwen tool-history formatting with same native host calls."""
from __future__ import annotations

import json

import pytest

from scripts.research_bound_two_step_host_e0 import CANARY
from scripts.research_qwen_bound_transcript_e0 import (
    append_bound_tool_transcript_e0,
)
from scripts.research_real_qwen_bound_two_step_e0 import (
    run_model_selected_bound_two_step_e0,
)

FIRST = '<tool_call>{"name":"marine__read","arguments":{"place":"Seoul"}}</tool_call>'
EOS = "<|im_end|>"


def previous_history(mode):
    rows = [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}]
    append_bound_tool_transcript_e0(
        rows, mode=mode, raw_generated_text=FIRST + EOS,
        route_id="marine.read", arguments={"place": "Seoul"},
        public_observation={"status": "ok", "record_id": "record-321"},
    )
    return rows


def test_raw_transcript_preserves_original_XML_and_duplicate_eos_risk():
    rows = previous_history("raw")
    assert rows[-2] == {"role": "assistant", "content": FIRST + EOS}
    assert rows[-1] == {
        "role": "tool",
        "content": '<tool_response>\n{"record_id": "record-321", "status": "ok"}\n</tool_response>',
    }


def test_strip_eos_only_changes_assistant_history_and_not_tools():
    raw = previous_history("raw")
    new = previous_history("strip-eos")
    assert new[-2] == {"role": "assistant", "content": FIRST}
    assert new[-1] == raw[-1]
    assert new[:2] == raw[:2]


def test_structured_tool_calls_and_plain_tool_content_not_XML_with_EOS():
    rows = previous_history("structured")
    assert rows[-2] == {
        "role": "assistant", "content": "",
        "tool_calls": [{
            "type": "function",
            "function": {
                "name": "marine__read",
                "arguments": {"place": "Seoul"},
            },
        }],
    }
    assert rows[-1] == {
        "role": "tool",
        "content": '{"record_id": "record-321", "status": "ok"}',
    }
    assert EOS not in json.dumps(rows)
    assert CANARY not in json.dumps(rows)


@pytest.mark.parametrize("invalid", (
    "unknown",
    None,
    True,
    11,
))
def test_no_unregistered_transcript_modes(invalid):
    with pytest.raises(ValueError, match="mode"):
        append_bound_tool_transcript_e0(
            [], mode=invalid, raw_generated_text=FIRST,
            route_id="marine.read", arguments={"place": "Seoul"},
            public_observation={"status": "ok"},
        )


@pytest.mark.parametrize("malformed", (
    {"status": "error", "message": CANARY},
    {"status": "ok", "record_id": float("nan")},
    {"status": "ok", "record_id": object()},
    {"status": "ok", "record_id": "X" * 5000},
))
def test_never_place_secret_malformed_or_unbounded_observations_in_history(malformed):
    rows = [{"role": "system", "content": "system"}]
    with pytest.raises(ValueError):
        append_bound_tool_transcript_e0(
            rows, mode="structured", raw_generated_text=FIRST,
            route_id="marine.read", arguments={"place": "Seoul"},
            public_observation=malformed,
        )
    assert len(rows) == 1


class TwoStepTranscriptReader:
    def __init__(self, mode):
        self.mode = mode
        self.turns = 0

    def generate(self, messages, tools):
        assert CANARY not in json.dumps(messages, ensure_ascii=False)
        assert CANARY not in json.dumps(tools, ensure_ascii=False)
        assert len(tools) == 2
        self.turns += 1
        if self.turns == 1:
            text = FIRST + EOS
        else:
            assert messages[-1]["role"] == "tool"
            if self.mode == "structured":
                assert messages[-2]["tool_calls"][0]["function"]["name"] == (
                    "marine__read" if self.turns == 2 else "papers__read"
                )
                observation = json.loads(messages[-1]["content"])
            else:
                assert ("<|im_end|>" in messages[-2]["content"]) == (
                    self.mode == "raw"
                )
                observation = json.loads(messages[-1]["content"].splitlines()[1])
            assert "secret" not in observation
            if self.turns == 2:
                text = (
                    "<tool_call>"
                    + json.dumps({
                        "name": "papers__read",
                        "arguments": {"record_id": observation["record_id"]},
                    }) + "</tool_call>" + EOS
                )
            elif self.turns == 3:
                text = json.dumps({"verified": observation["verified"]}) + EOS
            else:
                raise AssertionError("unbounded assistant turns")
        return {"text": text, "context_overflow": False}


@pytest.mark.asyncio
@pytest.mark.parametrize("mode", ("raw", "strip-eos", "structured"))
@pytest.mark.parametrize("lang", ("en", "ko", "ja"))
async def test_same_synthetic_model_proposals_reach_real_host_two_step(mode, lang):
    model = TwoStepTranscriptReader(mode)
    report = await run_model_selected_bound_two_step_e0(
        model, language=lang, transcript_mode=mode,
    )
    assert model.turns == 3
    assert report["transcript_mode"] == mode
    assert report["actual_bound_host_calls"] == 2
    assert report["two_stage_completed"] is True
    assert report["correct_strict_final_answer"] is True
    assert report["full_task_correct"] is True
    assert report["independent_e2_qualified"] is False
    assert report["actual_model_inference_measured"] is False
    assert report["real_external_native_provider_execution"] is False
    serial = json.dumps(report)
    for private in (CANARY, "record-321", "Seoul", "marine.read", "papers.read"):
        assert private not in serial


@pytest.mark.asyncio
async def test_transcript_mode_cannot_be_injected_as_untrusted_bool():
    with pytest.raises(ValueError, match="transcript"):
        await run_model_selected_bound_two_step_e0(
            TwoStepTranscriptReader("raw"),
            language="en", transcript_mode=True,
        )

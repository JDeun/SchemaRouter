"""No raw Qwen text, source records or values in CodeGraph E1 diagnostics."""
from __future__ import annotations

import json

import pytest

from scripts.research_codegraph_action_shape_e1 import (
    CATEGORIES,
    classify_rejected_action_shape,
)
from scripts.research_codegraph_local_multiroute_e1 import (
    run_local_multiroute_codegraph_e1,
)

SECRET = "PRIVATE_SOURCE_CANARY_NEVER_EMIT_1711"


@pytest.mark.parametrize(("raw", "expected"), (
    (None, "invalid_envelope_type"),
    ("x" * 5000, "output_over_limit"),
    ('<tool_call>{"name":"contacts__read"', "unterminated_or_multiple_tool_wrapper"),
    ("<tool_call>not-json</tool_call>", "invalid_tool_json"),
    ('<tool_call>[]</tool_call>', "non_object_tool_payload"),
    ('<tool_call>{"name":"contacts__read"}</tool_call>', "invalid_tool_envelope"),
    (
        '<tool_call>{"name":"contacts__read","arguments":{"ids":[1]}}</tool_call>',
        "complex_native_arguments",
    ),
    (
        '<tool_call>{"name":"contacts__read","arguments":{}}</tool_call>',
        "rejected_canonical_tool_call",
    ),
    ('{"name":"contacts__read","arguments":{}}', "unwrapped_tool_json"),
    ("<|tool_call|>hidden native format", "unsupported_tool_markup"),
    ("I will answer now.", "plain_final_without_source"),
))
def test_rejected_action_shape_labels_are_safe_static_categories(raw, expected):
    label = classify_rejected_action_shape(raw)
    assert label == expected
    assert label in CATEGORIES
    assert SECRET not in label


def test_rejected_output_with_private_arguments_is_not_reflected():
    raw = (
        '<tool_call>{"name":"contacts__read",'
        '"arguments":{"password":"' + SECRET + '","route_id":"other-private"}}</tool_call>'
    )
    label = classify_rejected_action_shape(raw)
    assert label in CATEGORIES
    assert SECRET not in label
    assert "password" not in label
    assert "contacts" not in label


class InvalidActionAgent:
    def generate(self, _messages, _tools):
        return {
            "text": '<tool_call>{"name":"contacts__read","arguments":{"ids":['
            + json.dumps(SECRET) + ']}}</tool_call>',
            "context_overflow": False,
            "latency_ms": 1.0,
            "input_tokens": 44,
            "tool_tokens": 10,
            "output_tokens": 15,
        }


@pytest.mark.asyncio
async def test_all_four_native_paths_fail_closed_and_publish_only_shape_categories():
    report = await run_local_multiroute_codegraph_e1(
        InvalidActionAgent(), language="ko", catalog_size=4,
    )
    assert report["status"] == "E1_MEASURED_LOCAL_FOUR_ARM_NOT_E2"
    assert len(report["outcomes"]) == 4
    assert report["source_call_count"] == 0
    for row in report["outcomes"]:
        assert row["actual_source_calls"] == 0
        assert row["full_task_complete"] is False
        assert row["rejected_model_action_shape"] in CATEGORIES
    assert SECRET not in json.dumps(report, ensure_ascii=False)
    assert report["independent_e2_qualified"] is False
    assert report["release_qualified"] is False


@pytest.mark.asyncio
async def test_premature_final_is_classified_without_source_data():
    class EarlyFinal:
        def generate(self, _messages, _tools):
            return {
                "text": '{"case_state":"' + SECRET + '"}',
                "context_overflow": False,
                "latency_ms": 1.0,
                "input_tokens": 40,
                "tool_tokens": 10,
                "output_tokens": 12,
            }

    result = await run_local_multiroute_codegraph_e1(
        EarlyFinal(), language="en", catalog_size=4,
    )
    assert all(
        row["rejected_model_action_shape"] == "plain_final_without_source"
        for row in result["outcomes"]
    )
    assert SECRET not in json.dumps(result)
    assert result["source_call_count"] == 0

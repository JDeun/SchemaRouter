"""A separate opt-in intervention: exact offered bare native JSON, not repair."""
from __future__ import annotations

import json

import pytest

from scripts.research_codegraph_local_multiroute_e1 import (
    run_local_multiroute_codegraph_e1,
)
from scripts.research_codegraph_native_envelope_e1 import (
    SCHEMA_REQUEST,
    strict_native_json_envelope,
)

SECRET = "NEVER_DISCLOSE_MODEL_TOOL_ARGUMENT_1711"
OFFERED = ("contacts__read", "cases__read", SCHEMA_REQUEST)
EXACT = '{"name":"contacts__read","arguments":{}}'


def test_exact_offered_bare_json_is_wrapped_then_passes_original_parser():
    from scripts.research_real_qwen_bound_two_step_e0 import parse_one_model_action

    converted, changed = strict_native_json_envelope(
        EXACT, offered_tool_names=OFFERED,
    )
    assert changed is True
    kind, action = parse_one_model_action(converted)
    assert kind == "tool"
    assert action == {"route": "contacts.read", "arguments": {}}
    assert "<tool_call>" in converted


@pytest.mark.parametrize("invalid", (
    '{"name":"unknown__read","arguments":{}}',
    '{"name":"contacts__read","arguments":{"a":[1]}}',
    '{"name":"contacts__read","arguments":{"nested":{"x":1}}}',
    '{"name":"contacts__read","arguments":{},"name":"cases__read"}',
    '{"name":"contacts__read","arguments":',
    '{"name":"contacts__read","arguments":{"unsafe":NaN}}',
    '{"name":"contacts__read","arguments":{}} extra',
    '<tool_call>{"name":"contacts__read","arguments":{}}</tool_call>',
    '{"name":"contacts__read","arguments":{"payload":"<' + SECRET + '>"}}',
    '{"name":"research__request_scoped_source_schema","arguments":{"route_ids":[]}}',
    '{"name":"research__request_scoped_source_schema",'
    '"arguments":{"route_ids":["contacts.read","contacts.read"]}}',
))
def test_malformed_unoffered_or_unsafe_native_call_is_never_normalized(invalid):
    original, changed = strict_native_json_envelope(
        invalid, offered_tool_names=OFFERED,
    )
    assert changed is False
    assert original == invalid


def test_strict_schema_request_allows_only_unique_bounded_route_list():
    raw = json.dumps({
        "name": SCHEMA_REQUEST,
        "arguments": {"route_ids": ["contacts.read", "cases.read"]},
    }, sort_keys=True)
    converted, changed = strict_native_json_envelope(
        raw, offered_tool_names=(SCHEMA_REQUEST,),
    )
    assert changed is True
    assert '"route_ids"' in converted
    assert "contacts.read" in converted
    assert strict_native_json_envelope(
        raw, offered_tool_names=("contacts__read",),
    )[1] is False


class BareJsonNativeAgent:
    """Genuine source-local callbacks; this is a scripted grammar proof only."""

    def generate(self, messages, tools):
        available = {tool["name"] for tool in tools}
        calls = sum(
            row["role"] == "assistant"
            and "<tool_call>" in row["content"]
            and any(name in row["content"] for name in (
                "contacts__read", "cases__read",
            ))
            for row in messages
        )
        if SCHEMA_REQUEST in available:
            text = json.dumps({
                "name": SCHEMA_REQUEST,
                "arguments": {"route_ids": ["contacts.read", "cases.read"]},
            })
        elif calls == 0 and "contacts__read" in available:
            text = EXACT
        elif calls == 1 and "cases__read" in available:
            text = json.dumps({
                "name": "cases__read",
                "arguments": {"contact_id": "contact-4", "region_id": "region-9"},
            })
        else:
            text = '{"case_state":"ready"}'
        return {
            "text": text,
            "context_overflow": False,
            "latency_ms": 1.0,
            "input_tokens": 60,
            "tool_tokens": 10,
            "output_tokens": 20,
        }


@pytest.mark.parametrize("language", ("en", "ko", "ja"))
@pytest.mark.asyncio
async def test_only_optin_treatment_performs_original_local_two_hop(language):
    original = await run_local_multiroute_codegraph_e1(
        BareJsonNativeAgent(), language=language, catalog_size=4,
    )
    assert original["source_call_count"] == 0
    assert all(row["full_task_complete"] is False
               for row in original["outcomes"])
    treated = await run_local_multiroute_codegraph_e1(
        BareJsonNativeAgent(), language=language, catalog_size=4,
        experimental_strict_unwrapped_json=True,
    )
    assert treated["source_call_count"] == 8
    assert all(row["full_task_complete"] is True
               for row in treated["outcomes"])
    assert all(row["actual_source_calls"] == 2
               for row in treated["outcomes"])
    assert treated["outcomes"][-1]["schema_requests"] == 1
    assert treated["outcomes"][-1]["strict_unwrapped_envelope_normalizations"] == 3
    assert all(row["strict_unwrapped_envelope_normalizations"] >= 2
               for row in treated["outcomes"])
    assert treated["independent_e2_qualified"] is False
    assert treated["release_qualified"] is False
    assert SECRET not in json.dumps(treated)


@pytest.mark.parametrize("wrong_flag", (1, "true", None))
@pytest.mark.asyncio
async def test_envelope_treatment_requires_boolean_not_truthy(wrong_flag):
    with pytest.raises(ValueError, match="research strict envelope mode"):
        await run_local_multiroute_codegraph_e1(
            BareJsonNativeAgent(), language="en", catalog_size=4,
            experimental_strict_unwrapped_json=wrong_flag,
        )

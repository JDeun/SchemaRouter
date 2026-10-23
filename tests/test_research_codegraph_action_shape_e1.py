"""Privacy-safe action-shape labels; no replay, normalization or execution."""
from __future__ import annotations

import json

import pytest

from scripts.research_codegraph_action_shape_e1 import (
    CATEGORIES,
    structural_action_label,
)

OFFERED = ("contacts__read", "cases__read")
SECRET = "TOP_SECRET_DO_NOT_DISCLOSE_E1_98372"


@pytest.mark.parametrize(("response", "offered", "expected"), (
    ("REQUEST_MORE_TOOLS", OFFERED, "final_before_schema"),
    ('{"case_state":"ready"}', OFFERED, "bare_final_json"),
    ('{"name":"contacts__read","arguments":{}}', OFFERED,
     "bare_json_tool_action"),
    ('<tool_call>{"name":"contacts__read","arguments":{}}</tool_call>',
     OFFERED, "valid_native_tool_call_shape"),
    ('<tool_call>{"name":"research__request_scoped_source_schema",'
     '"arguments":{"route_ids":["contacts.read","cases.read"]}}</tool_call>',
     ("research__request_scoped_source_schema",), "valid_schema_request_shape"),
    ('<tool_call>{"name":"contacts__read","arguments":{}}', OFFERED,
     "partial_tool_call"),
    ('<tool_call>{"name":"contacts__read","arguments":{}}</tool_call>'
     '<tool_call>{"name":"cases__read","arguments":{}}</tool_call>',
     OFFERED, "multiple_tool_calls"),
    ('<tool_call>{"name":"contacts__read","arguments":{,}}</tool_call>',
     OFFERED, "invalid_json"),
    ('<tool_call>{"name":"contacts__read","name":"cases__read",'
     '"arguments":{}}</tool_call>', OFFERED, "duplicate_json_key"),
    ('<tool_call>[]</tool_call>', OFFERED, "non_object_payload"),
    ('<tool_call>{"name":"contacts__read","arguments":{},"extra":1}</tool_call>',
     OFFERED, "invalid_tool_envelope"),
    ('<tool_call>{"name":"contacts__read","arguments":"{}"}</tool_call>',
     OFFERED, "arguments_not_object"),
    ('<tool_call>{"name":"cases__read","arguments":{"id":[]}}</tool_call>',
     OFFERED, "non_scalar_arguments"),
    ('<tool_call>{"name":"cases__read","arguments":{"id":NaN}}</tool_call>',
     OFFERED, "invalid_json"),
    ('<tool_call>{"name":"cases/read","arguments":{}}</tool_call>',
     OFFERED, "invalid_tool_name"),
    ('<tool_call>{"name":"forbidden__delete","arguments":{}}</tool_call>',
     OFFERED, "unoffered_tool_name"),
    ('<|im_start|>assistant<|im_sep|>'
     '<tool_call>{"name":"contacts__read","arguments":{}}</tool_call>',
     OFFERED, "chatml_wrapped_action"),
))
def test_closed_category_enum_only(response, offered, expected):
    result = structural_action_label(response, offered_names=offered)
    assert result == expected
    assert result in CATEGORIES


@pytest.mark.parametrize(("after_schema", "native_calls", "expected"), (
    (False, 0, "final_before_schema"),
    (True, 0, "final_after_schema"),
    (True, 1, "final_after_native"),
))
def test_terminal_phase_without_private_source_values(after_schema, native_calls, expected):
    assert structural_action_label(
        "REQUEST_MORE_TOOLS", offered_names=OFFERED,
        after_schema=after_schema, native_calls=native_calls,
    ) == expected


@pytest.mark.parametrize("bad_response", (
    SECRET,
    '<tool_call>{"name":"forbidden__delete","arguments":{"secret":"' + SECRET
    + '"}}</tool_call>',
    '<tool_call>{"name":"contacts__read","arguments":{"secret":"' + SECRET
    + '"}}</tool_call>',
    "<tool_call>[" + SECRET + "]</tool_call>",
))
def test_report_never_emits_raw_canary_route_or_argument(bad_response):
    result = structural_action_label(bad_response, offered_names=OFFERED)
    published = json.dumps({"action_structure_labels": [result]})
    assert result in CATEGORIES
    assert SECRET not in published
    assert "forbidden__delete" not in published
    assert "contacts__read" not in published
    assert "<tool_call>" not in published


def test_explicit_e1_diagnostic_controls_are_type_checked():
    with pytest.raises(ValueError):
        structural_action_label("x", offered_names=OFFERED, native_calls=True)
    with pytest.raises(ValueError):
        structural_action_label("x", offered_names=["contacts__read"])
    assert structural_action_label(None, offered_names=OFFERED) == "invalid_output_type"
    assert structural_action_label("x" * 4100, offered_names=OFFERED) == "invalid_bounded_text"

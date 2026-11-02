"""A new E1 treatment must NOT relax existing native model/tool authority."""
from __future__ import annotations

import pytest

from scripts.research_codegraph_bare_json_adapter_e1 import parse_native_action_optin

OFFERED = ("contacts__read", "cases__read")


def test_optin_only_reparses_one_offered_strict_json_tool():
    raw = '{"name":"contacts__read","arguments":{}}'
    kind, value, normalized = parse_native_action_optin(
        raw, offered_names=OFFERED,
    )
    assert (kind, normalized) == ("final", False)
    assert value == raw

    kind, value, normalized = parse_native_action_optin(
        raw, offered_names=OFFERED, accept_bare_json_native=True,
    )
    assert (kind, normalized) == ("tool", True)
    assert value == {"route": "contacts.read", "arguments": {}}


def test_existing_wrapped_tool_and_final_bypass_intervention():
    wrapped = '<tool_call>{"name":"contacts__read","arguments":{}}</tool_call>'
    kind, value, changed = parse_native_action_optin(
        wrapped, offered_names=OFFERED, accept_bare_json_native=True,
    )
    assert kind == "tool" and value["route"] == "contacts.read"
    assert changed is False

    final = '{"case_state":"ready"}'
    assert parse_native_action_optin(
        final, offered_names=OFFERED, accept_bare_json_native=True,
    ) == ("final", final, False)


@pytest.mark.parametrize("raw", (
    '{"name":"forbidden__delete","arguments":{}}',
    '{"name":"contacts__delete","arguments":{}}',
    '{"name":"research__request_scoped_source_schema",'
    '"arguments":{"route_ids":["contacts.read"]}}',
    '{"name":"contacts__read","arguments":{},"extra":1}',
    '{"name":"contacts__read","name":"cases__read","arguments":{}}',
    '{"name":"contacts__read","arguments":NaN}',
))
def test_unknown_or_ambiguous_names_never_become_executable(raw):
    kind, value, normalized = parse_native_action_optin(
        raw, offered_names=OFFERED, accept_bare_json_native=True,
    )
    assert kind == "final" and normalized is False and value == raw


@pytest.mark.parametrize("raw", (
    '{"name":"cases__read","arguments":{"contact_id":[]}}',
    '{"name":"cases__read","arguments":{"contact_id":{"id":"private"}}}',
    '{"name":"cases__read","arguments":{"contact_id":null}}',
    '{"name":"cases__read","arguments":{"contact_id":Infinity}}',
))
def test_complex_or_nonfinite_arguments_never_execute(raw):
    if "Infinity" in raw:
        assert parse_native_action_optin(
            raw, offered_names=OFFERED, accept_bare_json_native=True,
        ) == ("final", raw, False)
    else:
        with pytest.raises(ValueError):
            parse_native_action_optin(
                raw, offered_names=OFFERED, accept_bare_json_native=True,
            )


def test_multiple_or_partial_native_calls_remain_strictly_rejected():
    multiple = (
        '<tool_call>{"name":"contacts__read","arguments":{}}</tool_call>'
        '<tool_call>{"name":"cases__read","arguments":{}}</tool_call>'
    )
    with pytest.raises(ValueError):
        parse_native_action_optin(
            multiple, offered_names=OFFERED, accept_bare_json_native=True,
        )
    partial = '<tool_call>{"name":"contacts__read","arguments":{}}'
    with pytest.raises(ValueError):
        parse_native_action_optin(
            partial, offered_names=OFFERED, accept_bare_json_native=True,
        )


@pytest.mark.parametrize("bad", (1, None, "true"))
def test_explicit_optin_requires_boolean(bad):
    with pytest.raises(ValueError):
        parse_native_action_optin(
            '{"name":"contacts__read","arguments":{}}',
            offered_names=OFFERED, accept_bare_json_native=bad,
        )

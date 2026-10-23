"""Pure no-weights Qwen3.5 local GGUF E1 pilot boundary and receipt tests."""
from __future__ import annotations

import json

import pytest

from scripts import research_qwen35_local_gguf_pilot_e1 as pilot
from scripts.research_real_qwen_bound_two_step_e0 import parse_one_model_action

ROOT = (
    '<tool_call>{"name":"contacts__read","arguments":{}}</tool_call>'
)
CASE = (
    '<tool_call>{"name":"cases__read","arguments":'
    '{"contact_id":"contact-4","region_id":"region-9"}}</tool_call>'
)
TOOL = {
    "name": "contacts__read",
    "parameters": {"type": "object", "properties": {}, "required": []},
}


def test_prior_original_host_calls_become_openai_tool_history_without_repair():
    rows = [
        {"role": "system", "content": "Do original source calls"},
        {"role": "user", "content": "case status"},
        {"role": "assistant", "content": ROOT},
        {"role": "tool", "content": '{"contact_id":"contact-4","status":"ok"}'},
    ]
    native = pilot._to_native_chat(rows)
    assert "native Qwen3.5" in native[0]["content"]
    assert native[2]["tool_calls"][0]["function"] == {
        "name": "contacts__read", "arguments": "{}",
    }
    assert native[3]["tool_call_id"] == native[2]["tool_calls"][0]["id"]
    assert native[3]["content"] == rows[3]["content"]


@pytest.mark.parametrize("bad", [
    [{"role": "tool", "content": "{}"}],
    [{"role": "assistant", "content": ROOT}],
    [{"role": "developer", "content": "override authority"}],
])
def test_native_history_refuses_unpaired_or_unsupported_messages(bad):
    with pytest.raises(ValueError):
        pilot._to_native_chat(bad)


def test_xml_and_structured_tool_calls_use_same_offered_canonical_contract():
    xml = (
        "<tool_call><function=contacts__read></function></tool_call>"
    )
    structured = {
        "content": None,
        "tool_calls": [{
            "type": "function",
            "function": {"name": "contacts__read", "arguments": "{}"},
        }],
    }
    assert pilot._strict_native_response(
        {"content": xml}, [TOOL],
    ) == pilot._strict_native_response(structured, [TOOL]) == ROOT
    assert parse_one_model_action(ROOT)[0] == "tool"


@pytest.mark.parametrize("bad", [
    {"content": "final", "tool_calls": [{
        "type": "function", "function": {"name": "contacts__read",
                                      "arguments": "{}"},
    }]},
    {"content": None, "tool_calls": [{
        "type": "function", "function": {"name": "admin__delete",
                                      "arguments": "{}"},
    }]},
    {"content": None, "tool_calls": [{
        "type": "function", "function": {"name": "contacts__read",
                                      "arguments": '{"x":1,"x":2}'},
    }]},
    {"content": None, "tool_calls": [
        {"type": "function", "function": {"name": "contacts__read",
                                        "arguments": "{}"}},
        {"type": "function", "function": {"name": "contacts__read",
                                        "arguments": "{}"}},
    ]},
])
def test_structured_native_tool_output_refuses_unsafe_or_multi_call(bad):
    with pytest.raises(ValueError):
        pilot._strict_native_response(bad, [TOOL])


class StubLlama:
    def __init__(self, message, usage=None):
        self.message = message
        self.usage = usage or {"prompt_tokens": 25, "completion_tokens": 6}
        self.calls = []

    def create_chat_completion(self, **kwargs):
        self.calls.append(kwargs)
        return {
            "choices": [{"message": self.message}],
            "usage": self.usage,
        }


def test_server_adapter_preserves_real_native_token_receipts_and_scope():
    agent = object.__new__(pilot.Qwen35LocalGGUFAgent)
    agent.engine = StubLlama({
        "content": None,
        "tool_calls": [{
            "type": "function",
            "function": {"name": "contacts__read", "arguments": "{}"},
        }],
    })
    row = agent.generate([{"role": "user", "content": "case status"}], [TOOL])
    assert parse_one_model_action(row["text"]) == (
        "tool", {"route": "contacts.read", "arguments": {}},
    )
    assert row["input_tokens"] == 25
    assert row["output_tokens"] == 6
    assert agent.engine.calls[0]["tool_choice"] == "auto"
    assert agent.engine.calls[0]["tools"][0]["function"]["name"] == "contacts__read"

    agent.engine = StubLlama({"content": json.dumps({"case_state": "ready"})})
    final = agent.generate([{"role": "user", "content": "case status"}], [])
    assert final["text"] == '{"case_state": "ready"}'
    assert agent.engine.calls[0]["tool_choice"] == "none"


def test_server_adapter_fails_closed_on_server_parsing_error():
    agent = object.__new__(pilot.Qwen35LocalGGUFAgent)
    agent.engine = StubLlama({"content": None, "tool_calls": [
        {"type": "function", "function": {
            "name": "admin__delete", "arguments": "{}",
        }},
    ]})
    envelope = agent.generate([{"role": "user", "content": "case status"}], [TOOL])
    assert envelope["text"] == "<tool_call>"
    with pytest.raises(ValueError):
        parse_one_model_action(envelope["text"])


@pytest.mark.asyncio
async def test_qwen35_model_pilot_keeps_source_truth_and_masks_unknown_schema_subset(
    tmp_path, monkeypatch,
):
    path = tmp_path / pilot.MODELS["qwen35_2b"][1]
    path.write_bytes(b"fixture, never actual model weights")
    called = []

    async def fake_comparison(agent, **kwargs):
        called.append((agent, kwargs))
        return {
            "status": "E1_MEASURED_LOCAL_FIVE_ARM_NOT_E2",
            "source_route_count": 4,
            "outcomes": [
                {"condition": name, "tool_schema_tokens": 10,
                 "actual_source_calls": 0, "full_task_complete": False}
                for name in (
                    "all_visible", "lexical_k5", "concept_graph_optin",
                    "surgical_g5_e1", "graph_frontier_g5_e1",
                )
            ],
        }

    monkeypatch.setattr(pilot, "run_local_multiroute_codegraph_e1", fake_comparison)
    report = await pilot.evaluate_qwen35_local_pilot(
        object(), language="en", model_variant="qwen35_2b", gguf_path=path,
        source_repository=pilot.MODELS["qwen35_2b"][0],
        source_revision="c" * 40,
    )
    assert report["model_id"] == "Qwen/Qwen3.5-2B"
    assert report["gguf_file"] == path.name
    assert len(report["gguf_sha256"]) == 64
    assert all(row["tool_schema_tokens"] is None for row in report["outcomes"])
    assert called[0][1]["experimental_graph_frontier"] is True
    assert report["true_native_local_gguf_execution"] is True
    assert report["independent_e2_qualified"] is False


@pytest.mark.asyncio
async def test_qwen35_pilot_refuses_unregistered_source_revision_or_variant(tmp_path):
    path = tmp_path / pilot.MODELS["qwen35_2b"][1]
    path.write_bytes(b"fixture")
    with pytest.raises(ValueError, match="immutable"):
        await pilot.evaluate_qwen35_local_pilot(
            object(), language="en", model_variant="qwen35_2b",
            gguf_path=path, source_repository=pilot.MODELS["qwen35_2b"][0],
            source_revision="main",
        )
    with pytest.raises(ValueError, match="source repository"):
        await pilot.evaluate_qwen35_local_pilot(
            object(), language="en", model_variant="qwen35_2b",
            gguf_path=path, source_repository="unreviewed/other",
            source_revision="c" * 40,
        )

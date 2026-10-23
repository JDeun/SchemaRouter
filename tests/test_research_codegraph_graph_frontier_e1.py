"""Original source-execution and fail-closed Graph Frontier regression tests."""
from __future__ import annotations

import json

import pytest

from scripts.research_codegraph_graph_frontier_e1 import (
    _frontier_route_ids,
    run_graph_frontier_model_episode,
)
from scripts.research_codegraph_local_multiroute_e1 import (
    ROUTES,
    _strict_final,
    build_local_multiroute_source,
)
from scripts.research_codegraph_surgical_agent_e1 import SurgicalHostContext

ROOT = '<tool_call>{"name":"contacts__read","arguments":{}}</tool_call>'
CONSUMER = (
    '<tool_call>{"name":"cases__read","arguments":'
    '{"contact_id":"contact-4","region_id":"region-9"}}</tool_call>'
)
FINAL = '{"case_state":"ready"}'


class ScriptedAgent:
    def __init__(self, texts, mutate=None):
        self.texts = texts
        self.mutate = mutate
        self.offered = []
        self.messages = []

    def generate(self, messages, tools):
        self.offered.append(tuple(row["name"] for row in tools))
        self.messages.append(json.loads(json.dumps(messages)))
        index = len(self.offered) - 1
        if self.mutate is not None:
            self.mutate(index)
        return {
            "text": self.texts[index], "context_overflow": False,
            "latency_ms": 1.0, "input_tokens": 42,
            "tool_tokens": 9 if tools else 0, "output_tokens": 10,
        }


def _setup():
    source = build_local_multiroute_source(language="ko", catalog_size=4)
    assert source.episode is not None
    context = SurgicalHostContext(
        required_output_fields={
            ROUTES[0]: ("contact_id", "region_id"),
            ROUTES[1]: ("case_state",),
        },
        final_response_instruction="Answer JSON with only case_state.",
        validate_final=_strict_final,
    )
    return source, context


@pytest.mark.asyncio
async def test_frontier_producer_consumer_then_empty_final_menu():
    source, context = _setup()
    agent = ScriptedAgent([ROOT, CONSUMER, FINAL])
    result = await run_graph_frontier_model_episode(
        agent, episode=source.episode, host_context=context,
    )
    assert agent.offered == [
        ("contacts__read",), ("cases__read",), (),
    ]
    assert source.callback_log == ["contacts.read", "cases.read"]
    assert result["frontier_sizes"] == [1, 1, 0]
    assert result["schema_requests"] == 0
    assert result["actual_source_calls"] == 2
    assert result["full_task_correct"] is True
    assert result["total_model_tokens"] == 3 * (42 + 10)
    assert "route_sets" not in json.dumps(agent.messages[0])
    assert "requires_source_schema_materialization" not in json.dumps(agent.messages[0])
    assert "contact-4" not in json.dumps(result)


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", [
    CONSUMER,
    '<tool_call>{"name":"unknown__read","arguments":{}}</tool_call>',
    '<tool_call>{"name":"contacts__read","arguments":{"extra":"x"}}</tool_call>',
    '<tool_call>{"name":"contacts__read","arguments":{"unexpected":[1]}}</tool_call>',
    '<tool_call>{"name":"research__request_scoped_source_schema",'
    '"arguments":{"route_ids":["contacts.read"]}}</tool_call>',
    ROOT + ROOT,
])
async def test_frontier_refuses_unoffered_malformed_and_argument_calls(bad):
    source, context = _setup()
    result = await run_graph_frontier_model_episode(
        ScriptedAgent([bad]), episode=source.episode, host_context=context,
    )
    assert result["actual_source_calls"] == 0
    assert source.callback_log == []
    assert result["full_task_correct"] is False


@pytest.mark.asyncio
async def test_frontier_refuses_early_final_without_callback():
    source, context = _setup()
    result = await run_graph_frontier_model_episode(
        ScriptedAgent([FINAL]), episode=source.episode, host_context=context,
    )
    assert result["termination_reason"] == "premature_final"
    assert source.callback_log == []


@pytest.mark.asyncio
async def test_frontier_refuses_wrong_consumer_arguments():
    source, context = _setup()
    agent = ScriptedAgent([
        ROOT,
        '<tool_call>{"name":"cases__read","arguments":'
        '{"contact_id":"incorrect","region_id":"region-9"}}</tool_call>',
    ])
    result = await run_graph_frontier_model_episode(
        agent, episode=source.episode, host_context=context,
    )
    assert source.callback_log == ["contacts.read"]
    assert result["actual_source_calls"] == 1
    assert result["termination_reason"] == "unbound_source_arguments"


@pytest.mark.asyncio
async def test_frontier_refuses_native_call_after_completed_path():
    source, context = _setup()
    agent = ScriptedAgent([ROOT, CONSUMER, ROOT])
    result = await run_graph_frontier_model_episode(
        agent, episode=source.episode, host_context=context,
    )
    assert agent.offered[-1] == ()
    assert source.callback_log == ["contacts.read", "cases.read"]
    assert result["actual_source_calls"] == 2
    assert result["full_task_correct"] is False


@pytest.mark.asyncio
async def test_frontier_refuses_authority_change_after_generation():
    source, context = _setup()
    def change(index):
        if index == 0:
            object.__setattr__(source.principal, "roles", ("viewer",))
    result = await run_graph_frontier_model_episode(
        ScriptedAgent([ROOT], mutate=change),
        episode=source.episode, host_context=context,
    )
    assert result["actual_source_calls"] == 0
    assert source.callback_log == []


def test_frontier_only_uses_graph_prefixes():
    source, _ = _setup()
    assert _frontier_route_ids(source.episode, ()) == ["contacts.read"]
    assert _frontier_route_ids(source.episode, ("contacts.read",)) == ["cases.read"]
    assert _frontier_route_ids(source.episode, ("contacts.read", "cases.read")) == []
    assert _frontier_route_ids(source.episode, ("cases.read",)) == []

class CueAwareAgent(ScriptedAgent):
    """Scripted model responds to a generic cue; never receives route gold."""

    def __init__(self):
        super().__init__([])

    def generate(self, messages, tools):
        if not self.offered:
            next_text = ROOT
        elif len(self.offered) == 1:
            cued = any(
                m["role"] == "user"
                and "dependency path is not yet complete" in m["content"]
                for m in messages
            )
            next_text = CONSUMER if cued else FINAL
        else:
            next_text = FINAL
        self.texts.append(next_text)
        return super().generate(messages, tools)


@pytest.mark.asyncio
async def test_cue_only_after_real_verified_first_callback():
    before, context = _setup()
    plain = CueAwareAgent()
    ordinary = await run_graph_frontier_model_episode(
        plain, episode=before.episode, host_context=context,
    )
    assert ordinary["actual_source_calls"] == 1
    assert ordinary["termination_reason"] == "premature_final"
    assert "verified_continuation_cues" not in ordinary
    assert all(
        "dependency path is not yet complete" not in m["content"]
        for turn in plain.messages for m in turn
    )

    source, context = _setup()
    cued = CueAwareAgent()
    improved = await run_graph_frontier_model_episode(
        cued, episode=source.episode, host_context=context,
        experimental_verified_continuation=True,
    )
    assert source.callback_log == ["contacts.read", "cases.read"]
    assert improved["actual_source_calls"] == 2
    assert improved["full_task_correct"] is True
    assert improved["verified_continuation_cues"] == 1
    assert improved["frontier_sizes"] == [1, 1, 0]
    assert cued.offered == [("contacts__read",), ("cases__read",), ()]
    assert not any(
        "dependency path is not yet complete" in m["content"]
        for m in cued.messages[0]
    )
    assert any(
        "dependency path is not yet complete" in m["content"]
        for m in cued.messages[1]
    )


@pytest.mark.asyncio
async def test_cue_never_emitted_without_verified_original_callback():
    source, context = _setup()
    agent = ScriptedAgent([FINAL])
    result = await run_graph_frontier_model_episode(
        agent, episode=source.episode, host_context=context,
        experimental_verified_continuation=True,
    )
    assert result["verified_continuation_cues"] == 0
    assert result["actual_source_calls"] == 0
    assert source.callback_log == []


@pytest.mark.asyncio
async def test_cue_does_not_fix_wrong_bound_consumer_argument():
    source, context = _setup()
    agent = ScriptedAgent([
        ROOT,
        '<tool_call>{"name":"cases__read","arguments":'
        '{"contact_id":"fabricated","region_id":"region-9"}}</tool_call>',
    ])
    result = await run_graph_frontier_model_episode(
        agent, episode=source.episode, host_context=context,
        experimental_verified_continuation=True,
    )
    assert result["verified_continuation_cues"] == 1
    assert result["actual_source_calls"] == 1
    assert result["termination_reason"] == "unbound_source_arguments"
    assert source.callback_log == ["contacts.read"]


@pytest.mark.asyncio
async def test_cue_option_refuses_nonboolean():
    source, context = _setup()
    with pytest.raises(ValueError, match="continuation flag"):
        await run_graph_frontier_model_episode(
            ScriptedAgent([FINAL]), episode=source.episode,
            host_context=context, experimental_verified_continuation="yes",
        )

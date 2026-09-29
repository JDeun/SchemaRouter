from __future__ import annotations

from benchmarks.agent_utility_v1_catalog import TASKS, build_registry, route_ids
from scripts.evaluate_agent_utility_phase_b_qwen import (
    _candidate_set,
    _parse_tool_calls,
    _tool_response_message,
    _visible_tools,
)


def test_qwen_tool_call_parser_accepts_multiple_calls() -> None:
    text = """
<tool_call>
{"name":"papers__search","arguments":{"query":"battery"}}
</tool_call>
<tool_call>
{"name":"papers__retrieve","arguments":{"paper_id":"P-1"}}
</tool_call>
"""
    calls = _parse_tool_calls(text)
    assert calls == [
        {
            "name": "papers__search",
            "arguments": {"query": "battery"},
        },
        {
            "name": "papers__retrieve",
            "arguments": {"paper_id": "P-1"},
        },
    ]


def test_qwen_tool_call_parser_accepts_stringified_arguments() -> None:
    text = (
        '<tool_call>{"name":"exports__export",'
        '"arguments":"{\\\"artifact_id\\\":\\\"ART-2\\\"}"}</tool_call>'
    )
    assert _parse_tool_calls(text)[0]["arguments"] == {
        "artifact_id": "ART-2"
    }


def test_candidate_sets_hide_rank_order_from_agent() -> None:
    registry = build_registry(50)
    task = next(task for task in TASKS if task.task_id == "single-paper-search")
    sr5 = _candidate_set(
        registry,
        task.query,
        "SR-5",
        task.required_routes,
    )
    assert sr5 == sorted(sr5)
    assert len(sr5) == 5
    assert "papers.search" in sr5

    full = _candidate_set(
        registry,
        task.query,
        "FULL",
        task.required_routes,
    )
    assert full == sorted(route_ids(registry))

    oracle = _candidate_set(
        registry,
        task.query,
        "ORACLE",
        task.required_routes,
    )
    assert oracle == ["papers.search"]


def test_visible_tool_schema_contains_typed_metadata() -> None:
    registry = build_registry(20)
    tools = _visible_tools(
        registry,
        ["materials.current", "inventory.delete"],
    )
    assert [tool["function"]["name"] for tool in tools] == [
        "inventory__delete",
        "materials__current",
    ]
    material = next(
        tool
        for tool in tools
        if tool["function"]["name"] == "materials__current"
    )
    description = material["function"]["description"]
    assert "material.youngs_modulus" in description
    assert "unit=GPa" in description
    assert "destructive=False" in description

    destructive = next(
        tool
        for tool in tools
        if tool["function"]["name"] == "inventory__delete"
    )
    assert "destructive=True" in destructive["function"]["description"]


def test_tool_response_format_matches_qwen_protocol_shape() -> None:
    rendered = _tool_response_message(
        [{"status": "ok", "paper_id": "P-1"}]
    )
    assert rendered.startswith("<tool_response>\n")
    assert rendered.endswith("\n</tool_response>")
    assert '"paper_id": "P-1"' in rendered

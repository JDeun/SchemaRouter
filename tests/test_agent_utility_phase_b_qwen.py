from __future__ import annotations

import re
from pathlib import Path

import pytest

from benchmarks.agent_utility_v1_catalog import TASKS, build_registry, route_ids
from scripts.evaluate_agent_utility_phase_b_qwen import (
    SYSTEM_PROMPT,
    _candidate_set,
    _parse_tool_calls,
    _tool_response_message,
    _visible_tools,
    evaluate,
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


def test_unknown_task_shard_id_fails_before_model_load() -> None:
    with pytest.raises(ValueError, match="unknown frozen task id"):
        evaluate(
            catalog_sizes=(20,),
            task_ids={"multi-inventory-create-send"},
        )


def test_b1_workflow_shards_cover_every_frozen_task_exactly_once() -> None:
    expected = {task.task_id for task in TASKS}

    task_sharded = Path(
        ".github/workflows/research-0.14-b1-task-sharded.yml"
    ).read_text(encoding="utf-8")
    legacy_groups = re.findall(
        r'(?:task_ids:\\s*"|TASK_IDS=")([^"]+)"',
        task_sharded,
    )
    legacy_task_ids = [
        task_id.strip()
        for group in legacy_groups
        for task_id in group.split(",")
        if task_id.strip()
    ]
    assert len(legacy_task_ids) == len(expected)
    assert len(set(legacy_task_ids)) == len(legacy_task_ids)
    assert set(legacy_task_ids) == expected

    micro = Path(
        ".github/workflows/research-0.14-b1-microsharded.yml"
    ).read_text(encoding="utf-8")
    rows = re.findall(
        r'catalog:\\s*(20|50|100|250),\\s*'
        r'shard:\\s*[^,}]+,\\s*task_ids:\\s*"([^"]+)"',
        micro,
    )
    assert len(rows) == 30

    by_catalog: dict[int, list[str]] = {
        20: [],
        50: [],
        100: [],
        250: [],
    }
    group_count: dict[int, int] = {20: 0, 50: 0, 100: 0, 250: 0}
    for raw_size, group in rows:
        size = int(raw_size)
        group_count[size] += 1
        by_catalog[size].extend(
            task_id.strip()
            for task_id in group.split(",")
            if task_id.strip()
        )

    assert group_count == {20: 6, 50: 6, 100: 6, 250: 12}
    for task_ids in by_catalog.values():
        assert len(task_ids) == len(expected)
        assert len(set(task_ids)) == len(task_ids)
        assert set(task_ids) == expected

def test_system_prompt_requires_observation_between_tool_calls() -> None:
    assert "at most one tool call per assistant turn" in SYSTEM_PROMPT
    assert "Wait for the tool observation" in SYSTEM_PROMPT

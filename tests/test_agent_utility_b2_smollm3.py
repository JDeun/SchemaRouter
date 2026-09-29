from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_b2_catalog import build_registry  # noqa: E402
from scripts.evaluate_agent_utility_phase_b_smollm3 import (  # noqa: E402
    _bootstrap_delta,
    _function_tool,
    _parse_tool_calls,
    _visible_tools,
)


def test_b2_smollm3_tool_schema_is_native_xml_shape() -> None:
    registry = build_registry(20)
    tool = registry.get("materials")
    endpoint = tool.endpoint("current")

    schema = _function_tool("materials.current", tool, endpoint)

    assert set(schema) == {"name", "description", "parameters"}
    assert schema["name"] == "materials__current"
    assert "Registered route: materials.current." in schema["description"]
    assert schema["parameters"]["type"] == "object"
    assert schema["parameters"]["additionalProperties"] is False
    assert schema["parameters"]["required"] == ["material_id"]
    assert "type" not in schema or schema.get("type") != "function"
    assert "function" not in schema


def test_b2_visible_tools_are_lexicographically_ordered() -> None:
    registry = build_registry(20)
    visible = _visible_tools(
        registry,
        ["materials.current", "papers.search", "inventory.list"],
    )

    assert [tool["name"] for tool in visible] == [
        "inventory__list",
        "materials__current",
        "papers__search",
    ]


def test_b2_parser_accepts_native_xml_tool_call() -> None:
    payload = {
        "name": "materials__current",
        "arguments": {"material_id": "MAT-7"},
    }
    text = (
        "prefix\n<tool_call>\n"
        + json.dumps(payload)
        + "\n</tool_call>\nsuffix"
    )

    assert _parse_tool_calls(text) == [payload]


def test_b2_parser_rejects_non_object_arguments() -> None:
    text = (
        '<tool_call>{"name":"papers__search","arguments":42}</tool_call>'
    )

    with pytest.raises(ValueError, match="arguments must be an object"):
        _parse_tool_calls(text)


def test_b2_shard_bootstrap_keeps_catalog_repeats_in_task_cluster() -> None:
    full = []
    condition = []
    for task_id, full_pass, condition_pass in (
        ("task-a", False, True),
        ("task-b", True, False),
    ):
        for catalog_size in (20, 50, 100, 250):
            full.append(
                {
                    "task_id": task_id,
                    "catalog_size": catalog_size,
                    "passed": full_pass,
                }
            )
            condition.append(
                {
                    "task_id": task_id,
                    "catalog_size": catalog_size,
                    "passed": condition_pass,
                }
            )

    result = _bootstrap_delta(full, condition, iterations=500)

    assert result["delta"] == 0.0
    assert result["cluster_unit"] == "task_id"
    assert result["unique_task_count"] == 2
    assert result["catalog_repeats_per_task"] == 4
    assert result["iterations"] == 500
    assert result["ci_low"] <= 0.0 <= result["ci_high"]

from __future__ import annotations

import pytest

pytest.importorskip("pydantic_ai")

from scripts.external_validation_pydanticai import (
    CATALOG,
    FROZEN_CATALOG_SIZES,
    _simple_baseline,
    _tool_definitions,
)


def test_scaled_catalog_preserves_real_tools_and_adds_distractors() -> None:
    tools = _tool_definitions(50)
    assert len(tools) == 50
    assert [tool.name for tool in tools[: len(CATALOG)]] == [
        str(entry["name"]) for entry in CATALOG
    ]
    assert tools[-1].name == "distractor_049"


def test_simple_baseline_is_bounded_and_deterministic() -> None:
    tools = _tool_definitions(100)
    first = _simple_baseline("electronic band gap for silicon material", tools)
    second = _simple_baseline("electronic band gap for silicon material", tools)
    assert first == second
    assert len(first) <= 3
    assert "material_band_gap" in first


def test_frozen_scaling_matrix_preserves_full_real_catalog() -> None:
    assert FROZEN_CATALOG_SIZES == (len(CATALOG), 50, 100, 250)
    assert FROZEN_CATALOG_SIZES[0] == 12
    for size in FROZEN_CATALOG_SIZES:
        tools = _tool_definitions(size)
        assert len(tools) == size
        assert [tool.name for tool in tools[: len(CATALOG)]] == [
            str(entry["name"]) for entry in CATALOG
        ]

"""Pre-model controls for source-only E5 operation identity scoring on 500 routes."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from scripts.research_source_operation_channel_e5_base_cpu_dev import (
    CASES,
    DESCRIPTION_WEIGHT,
    EXPECTED,
    K,
    OPERATION_WEIGHT,
    ROUTES,
    _passages,
    _summary,
    source_catalog,
    weighted_rank,
)


def test_original_native_no-field_catalog_and_new_language_denominators():
    router, source_sha, catalog_sha = source_catalog()
    assert len(source_sha) == 64 and len(catalog_sha) == 64
    assert ROUTES == 500 and K == 5
    assert len(CASES) == 24
    assert len(EXPECTED) == 6
    assert OPERATION_WEIGHT == 0.25
    assert DESCRIPTION_WEIGHT + OPERATION_WEIGHT == 1.0
    assert not any(
        endpoint.output_fields
        for tool in router.registry.tools()
        for endpoint in tool.endpoints
    )
    for lang in ("en", "ko", "ja"):
        assert sum(language == lang and route is not None
                   for language, _, route in CASES) == 6
        assert sum(language == lang and route is None
                   for language, _, route in CASES) == 2


def test_operation_passage_contains_only_native_route_suffix():
    rows = (
        SimpleNamespace(route_id="materials.units", description="Original public units."),
        SimpleNamespace(route_id="papers.search", description="Original public papers."),
    )
    desc, ops = _passages(rows)
    assert desc == [
        "materials.units\nOriginal public units.",
        "papers.search\nOriginal public papers.",
    ]
    assert ops == ["Operation name: units", "Operation name: search"]


def test_score_weight_is_fixed_and_cannot_inject_unknown_route():
    ids = tuple(f"tool_{i}.op_{i}" for i in range(ROUTES))
    descriptions = [[1.0, 0.0] for _ in ids]
    operations = [[0.0, 1.0] for _ in ids]
    descriptions[0] = [0.0, 1.0]
    operations[1] = [1.0, 0.0]
    before = weighted_rank(
        [1.0, 0.0], descriptions, operations, ids, weight=0.0,
    )
    after = weighted_rank(
        [1.0, 0.0], descriptions, operations, ids, weight=0.25,
    )
    assert before[0] == ids[1]
    assert after[0] == ids[1]
    assert len(before) == len(after) == K
    assert set(before + after).issubset(ids)
    with pytest.raises(ValueError):
        weighted_rank([1.0, 0.0], descriptions, operations, ids, weight=1.1)


def test_all_unsupported_fixed_k_results_are_not_no_fit_proof():
    rows = []
    for lang, _query, gold in CASES:
        chosen = [gold] if gold else []
        chosen.extend(["noise.alpha"] * (K - len(chosen)))
        rows.append({
            "language": lang,
            "supported": gold is not None,
            "expected": gold,
            "source_e5": {"route_ids": chosen, "selection_ms": 1.0},
            "operation_25": {"route_ids": chosen, "selection_ms": 2.0},
        })
    for arm in ("source_e5", "operation_25"):
        summary = _summary(rows, arm)
        for lang in ("en", "ko", "ja"):
            assert summary[lang]["top1"] == 6
            assert summary[lang]["top5"] == 6
            assert summary[lang]["unsupported_nonempty"] == 2

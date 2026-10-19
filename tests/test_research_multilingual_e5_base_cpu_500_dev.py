"""E0 prerequisite controls for newly preregistered real small/base CPU task slice."""
from __future__ import annotations

import pytest

from scripts.research_multilingual_e5_base_cpu_500_dev import (
    CASES,
    CATALOG_ROUTES,
    SUPPORTED_ROUTES,
    K,
    _report_arm,
    validate_manifest,
)


def test_original_english_only_catalog_and_fresh_case_denominators():
    catalog, checksum = validate_manifest()
    assert len(catalog["catalog"]) == 13
    assert len(checksum) == 64
    assert CATALOG_ROUTES == 500
    assert K == 5
    assert len(CASES) == 24
    assert len({query for _, query, _ in CASES}) == 24
    assert SUPPORTED_ROUTES == {
        "materials.search",
        "materials.units",
        "papers.search",
        "flights.status",
        "finance.exchange_history",
        "maps.directions",
    }
    for lang in ("en", "ko", "ja"):
        assert sum(language == lang and g is not None for language, _, g in CASES) == 6
        assert sum(language == lang and g is None for language, _, g in CASES) == 2


def test_fixed_k5_unsupported_nonempty_is_not_a_correct_no_fit():
    rows = []
    for i, (lang, _query, expected) in enumerate(CASES):
        prediction = (
            (expected, "noise.alpha", "noise.beta", "noise.gamma", "noise.delta")
            if expected
            else ("noise.alpha", "noise.beta", "noise.gamma", "noise.delta", "noise.zeta")
        )
        rows.append({
            "id": str(i),
            "language": lang,
            "supported": expected is not None,
            "expected_route": expected,
            "model": {"routes": prediction, "ms": 2.0},
        })
    summary = _report_arm(rows, "model")
    for lang in ("en", "ko", "ja"):
        s = summary[lang]
        assert (s["top1_hit"], s["top5_hit"]) == (6, 6)
        assert (s["unsupported"], s["unsupported_nonempty"]) == (2, 2)
        assert s["selection_p95_ms"] == 2.0


def test_missing_language_denominators_fail_closed():
    with pytest.raises(AssertionError):
        _report_arm([], "model")

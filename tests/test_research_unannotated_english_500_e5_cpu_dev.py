"""No-model controls for pinned 500-route English-only multilingual E5 E1 DEV."""
from __future__ import annotations

import hashlib

from scripts.research_unannotated_english_500_e5_cpu_dev import (
    CASES,
    K,
    ROUTES,
    SUPPORTED_ROUTES,
    _summary,
    validate_cases_and_source,
)


def test_predeclared_denominators_and_source_without_trusted_language_aliases():
    corpus, digest = validate_cases_and_source()
    assert len(corpus["catalog"]) == 13
    assert len(digest) == 64
    assert all(char in "0123456789abcdef" for char in digest)
    assert ROUTES == 500 and K == 5
    assert len(CASES) == 24 and len(SUPPORTED_ROUTES) == 6
    assert len(set(query for _, query, _ in CASES)) == len(CASES)
    for lang in ("en", "ko", "ja"):
        assert len([c for c in CASES if c[0] == lang and c[2]]) == 6
        assert len([c for c in CASES if c[0] == lang and c[2] is None]) == 2


def test_no_fit_metrics_do_not_treat_fixed_k_as_calibrated_abstention():
    rows = []
    for language, query, expected in CASES:
        rows.append({
            "language": language,
            "supported": expected is not None,
            "arms": {
                arm: {
                    "hit_1": expected is not None,
                    "hit_5": expected is not None,
                    "nonempty": True,
                    "selection_ms": 1.0,
                }
                for arm in ("lexical_k5", "real_e5_k5")
            },
        })
    for arm in ("lexical_k5", "real_e5_k5"):
        summary = _summary(rows, arm)
        for lang in ("en", "ko", "ja"):
            assert summary[lang]["supported_n"] == 6
            assert summary[lang]["unsupported_n"] == 2
            assert summary[lang]["unsupported_nonempty"] == 2
            assert summary[lang]["hit_at_5"] == 6
            assert summary[lang]["selection_ms_p95"] == 1.0


def test_fixed_manifest_has_nonempty_source_native_routes_only():
    expected = set(SUPPORTED_ROUTES)
    assert expected == {
        "materials.search",
        "inventory.lookup",
        "flights.status",
        "finance.exchange_history",
        "papers.citations",
        "materials.units",
    }
    assert all(route in expected or route is None for _, _, route in CASES)

from __future__ import annotations

from scripts.generate_decision_routing_quality_v4_confirmation import (
    SURFACE_VERSION,
    WRAPPERS,
    _wrapper_index,
    build_confirmation,
)


def test_confirmation_wrapper_index_is_deterministic() -> None:
    first = _wrapper_index("seed-a", "case-1", 3)
    second = _wrapper_index("seed-a", "case-1", 3)
    assert first == second
    assert 0 <= first < 3


def test_confirmation_wrappers_cover_all_v4_languages() -> None:
    assert set(WRAPPERS) == {"en", "ko", "es", "ja", "de", "mixed"}
    assert SURFACE_VERSION == "zero-false-confirmation-wrappers-v1"


def test_fresh_surface_confirmation_has_zero_exact_overlap() -> None:
    cases, metadata = build_confirmation(
        seed="operation-routing-quality-v4-zero-false-confirmation-2026-09-28-a",
        reference_seed="operation-routing-quality-v4-development-2026-09-27",
    )
    assert len(cases) == 1800
    assert metadata["normalized_exact_overlap_with_reference_dev"] == 0
    assert len({str(case["query"]) for case in cases}) == 1800

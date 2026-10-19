"""Fixed manifest/source provenance for 500-route self-authored E0 cohort."""
from __future__ import annotations

from scripts.research_multilingual_declared_phrase_500_dev import CASES, ROUTES


def test_500_route_cohort_declares_both_supported_and_negative_by_language():
    assert ROUTES == 500
    assert len(CASES) == 11
    assert len(set(case[1] for case in CASES)) == len(CASES)
    for lang in ("en", "ko", "ja"):
        positives = [case for case in CASES if case[0] == lang and case[2]]
        negatives = [case for case in CASES if case[0] == lang and case[2] is None]
        assert len(positives) == 2
        assert len(negatives) >= 1
        assert all(
            expected in (
                "z_mechanics.read", "z_thermal.read", "z_spectroscopy.read",
            )
            for _language, _text, expected in positives
        )

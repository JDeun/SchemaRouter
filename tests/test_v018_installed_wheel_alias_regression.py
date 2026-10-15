"""Source-independent checks for the installed-wheel engineering comparator."""

from __future__ import annotations

import copy

import pytest

from scripts.verify_v018_installed_wheel_alias_regression import (
    CASES,
    compare,
)


def fixture():
    base = {
        "schema_version": 1,
        "evidence_class": "zero_model_release_engineering_regression_only",
        "installed_version": "0.17.0",
        "results": {},
    }
    cand = copy.deepcopy(base)
    for mode in ("indexed", "exhaustive"):
        base["results"][mode] = {}
        cand["results"][mode] = {}
        for key in CASES:
            en = key == "en"
            local = key in {"ko", "ja", "es", "de"}
            base["results"][mode][key] = {
                "declared_route_has_lexical_evidence": en,
                "unrelated_route_has_lexical_evidence": False,
                "declared_route_outranks_unrelated": en,
            }
            cand["results"][mode][key] = {
                "declared_route_has_lexical_evidence": en or local,
                "unrelated_route_has_lexical_evidence": False,
                "declared_route_outranks_unrelated": en or local,
            }
    return base, cand


def test_complete_engineering_fixture_passes_without_any_model():
    base, candidate = fixture()
    compare(base, candidate)


@pytest.mark.parametrize("language", ["ko", "ja", "es", "de"])
def test_missing_any_localized_candidate_is_release_regression(language):
    base, candidate = fixture()
    candidate["results"]["indexed"][language][
        "declared_route_outranks_unrelated"
    ] = False
    with pytest.raises(ValueError, match=language):
        compare(base, candidate)


def test_no_invented_match_on_unsupported_query():
    base, candidate = fixture()
    candidate["results"]["exhaustive"]["unsupported"][
        "declared_route_has_lexical_evidence"
    ] = True
    with pytest.raises(ValueError, match="unsupported"):
        compare(base, candidate)


def test_baseline_is_the_actual_published_version():
    base, candidate = fixture()
    base["installed_version"] = "0.18.0"
    with pytest.raises(ValueError, match="baseline"):
        compare(base, candidate)


def test_unrelated_false_positive_or_mismatched_cases_fail():
    base, candidate = fixture()
    candidate["results"]["indexed"]["ja"][
        "unrelated_route_has_lexical_evidence"
    ] = True
    with pytest.raises(ValueError, match="unrelated"):
        compare(base, candidate)
    base, candidate = fixture()
    del candidate["results"]["exhaustive"]["ko"]
    with pytest.raises(ValueError, match="inventory"):
        compare(base, candidate)


def test_no_scientific_or_unpinned_evidence_forgery():
    base, candidate = fixture()
    candidate["evidence_class"] = "independent_agent_confirmation"
    with pytest.raises(ValueError, match="evidence"):
        compare(base, candidate)

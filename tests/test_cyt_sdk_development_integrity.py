"""Adversarial, zero-model checks for CYT indexer SDK-only DEV evidence."""
from __future__ import annotations

from copy import deepcopy

import pytest

from scripts.validate_cyt_sdk_development_result import (
    CYT_OPTIONS,
    PINNED_CYT_REVISION,
    SDK_BOUNDARY,
    SDK_NAME,
    validate_inputs,
    validate_sdk_output,
)

CATALOG_HASH = "a" * 64
CASES_HASH = "b" * 64


def fixture() -> tuple[dict, dict, dict]:
    catalog = {"tools": [
        {"name": "read_record", "description": "Read one record",
         "input_schema": {"type": "object", "properties": {}}},
        {"name": "list_records", "description": "List all records",
         "input_schema": {"type": "object", "properties": {}}},
    ]}
    cases = {"cases": [
        {"id": "dev-01", "query": "Read record"},
        {"id": "dev-02", "query": "Unanswerable unsupported query"},
    ]}
    result = {
        "schema_version": 1,
        "status": "development_unfrozen",
        "performance_evidence": False,
        "sdk_only": True,
        "full_cyt_e2e_verified": False,
        "scoring_authorized": False,
        "inputs": {
            "catalog_sha256": CATALOG_HASH,
            "cases_sha256": CASES_HASH,
        },
        "catalog_size": 2,
        "implementation": {
            "name": SDK_NAME,
            "revision": PINNED_CYT_REVISION,
            "boundary": SDK_BOUNDARY,
            "options": deepcopy(CYT_OPTIONS),
            "repeats_per_query": 3,
        },
        "results": [
            {"id": "dev-01", "candidate_tools": ["read_record"],
             "candidate_count": 1, "latency_ms": 1.25,
             "optional_chunk_count_in": None, "optional_chunk_count_out": 0},
            {"id": "dev-02",
             "candidate_tools": ["read_record", "list_records"],
             "candidate_count": 2, "latency_ms": 4.25,
             "optional_chunk_count_in": 2, "optional_chunk_count_out": 2},
        ],
    }
    return catalog, cases, result


def checked(catalog: dict, cases: dict, result: dict) -> dict:
    return validate_sdk_output(
        result, catalog, cases,
        catalog_sha256=CATALOG_HASH,
        cases_sha256=CASES_HASH,
    )


def test_valid_sdk_only_dev_report_remains_unscored() -> None:
    catalog, cases, report = fixture()
    result = checked(catalog, cases, report)
    assert result["status"] == "development_integrity_verified_unscored"
    assert result["full_cyt_e2e_verified"] is False
    assert result["scoring_authorized"] is False
    assert result["performance_evidence"] is False
    assert result["case_count"] == 2


@pytest.mark.parametrize("field,value", [
    ("schema_version", True),
    ("status", "heldout_complete"),
    ("performance_evidence", True),
    ("sdk_only", False),
    ("full_cyt_e2e_verified", True),
    ("scoring_authorized", True),
    ("catalog_size", 3),
    ("inputs", {"catalog_sha256": "0" * 64,
                "cases_sha256": CASES_HASH}),
    ("results", []),
])
def test_claims_and_source_forgery_fail_closed(field: str, value) -> None:
    catalog, cases, report = fixture()
    report[field] = value
    with pytest.raises(ValueError):
        checked(catalog, cases, report)


@pytest.mark.parametrize("field,value", [
    ("name", "full CYT proxy"),
    ("boundary", "native CYT Hook"),
    ("revision", "0" * 40),
    ("options", {"pipeline": ["llm"]}),
    ("repeats_per_query", 0),
    ("repeats_per_query", True),
])
def test_non_native_or_unpinned_implementation_rejected(field, value) -> None:
    catalog, cases, report = fixture()
    report["implementation"][field] = value
    with pytest.raises(ValueError, match="boundary/options/revision"):
        checked(catalog, cases, report)


@pytest.mark.parametrize("field,value", [
    ("candidate_tools", ["unknown_external_tool"]),
    ("candidate_tools", ["read_record", "read_record"]),
    ("candidate_tools", [42]),
    ("candidate_count", 7),
    ("candidate_count", True),
    ("latency_ms", float("nan")),
    ("latency_ms", float("inf")),
    ("latency_ms", -1),
    ("latency_ms", True),
    ("optional_chunk_count_in", -3),
    ("optional_chunk_count_out", 2.2),
])
def test_native_result_identity_and_finite_latency_enforced(field, value) -> None:
    catalog, cases, report = fixture()
    report["results"][0][field] = value
    with pytest.raises(ValueError):
        checked(catalog, cases, report)


def test_empty_candidates_are_valid_dev_negative_not_auto_success() -> None:
    catalog, cases, report = fixture()
    report["results"][1]["candidate_tools"] = []
    report["results"][1]["candidate_count"] = 0
    status = checked(catalog, cases, report)
    assert status["scoring_authorized"] is False


def test_missing_duplicate_or_reordered_rows_not_silently_accepted() -> None:
    catalog, cases, report = fixture()
    report["results"] = list(reversed(report["results"]))
    with pytest.raises(ValueError, match="order"):
        checked(catalog, cases, report)
    catalog, cases, report = fixture()
    report["results"][1]["id"] = "dev-01"
    with pytest.raises(ValueError, match="duplicate"):
        checked(catalog, cases, report)


def test_bad_source_catalog_and_query_identity_rejected() -> None:
    catalog, cases, _ = fixture()
    catalog["tools"][1]["name"] = "read_record"
    with pytest.raises(ValueError, match="duplicate"):
        validate_inputs(catalog, cases)
    catalog, cases, _ = fixture()
    cases["cases"][1]["query"] = " "
    with pytest.raises(ValueError, match="query"):
        validate_inputs(catalog, cases)


def test_revision_not_silently_selected_from_dev_results() -> None:
    catalog, cases, report = fixture()
    with pytest.raises(ValueError, match="source pin"):
        validate_sdk_output(
            report, catalog, cases,
            catalog_sha256=CATALOG_HASH,
            cases_sha256=CASES_HASH,
            expected_revision="0" * 40,
        )

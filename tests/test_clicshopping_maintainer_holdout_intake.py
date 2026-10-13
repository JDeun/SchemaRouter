"""Unscored, adversarial intake cases for #1311 (all source text synthetic)."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

from scripts.inspect_clicshopping_maintainer_holdout import (
    DECLARED_SHA256,
    EXPECTED_IDS,
    SOURCE_SHA,
    inspect_raw_holdout,
)


def synthetic() -> dict:
    return {
        "upstream_commit": SOURCE_SHA,
        "cases": [
            {"id": case_id, "query": f"SYNTHETIC ONLY request {index}"}
            for index, case_id in enumerate(EXPECTED_IDS, start=1)
        ],
    }


def as_bytes(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False).encode("utf-8")


def test_valid_shape_is_still_unscored_and_not_independently_reviewed() -> None:
    raw = as_bytes(synthetic())
    report = inspect_raw_holdout(raw)
    assert report["case_count"] == 20
    assert report["case_ids"] == list(EXPECTED_IDS)
    assert report["verbatim_file_sha256"] == hashlib.sha256(raw).hexdigest()
    assert report["maintainer_declared_sha256"] == DECLARED_SHA256
    assert report["source_pin_present_in_raw"] is True
    assert len(report["issue_declared_groups"]["supported"]) == 12
    assert len(report["issue_declared_groups"]["read_only_forbidden"]) == 3
    assert len(report["issue_declared_groups"]["unsupported"]) == 5
    assert report["digest_serialization_convention_confirmed"] is False
    assert report["gold_routes_and_permissions_verified"] is False
    assert report["independent_case_and_label_review_pending"] is True
    assert report["source_snapshot_accepted_for_scoring"] is False
    assert report["scoring_authorized"] is False
    assert report["model_calls"] == report["live_endpoint_calls"] == 0


def test_matching_declared_digest_still_does_not_certify_source() -> None:
    raw = as_bytes(synthetic())
    report = inspect_raw_holdout(raw, declared_sha256=hashlib.sha256(raw).hexdigest())
    assert "verbatim_utf8_bytes" in report["declared_sha256_matches"]
    assert report["digest_serialization_convention_confirmed"] is False
    assert report["scoring_authorized"] is False


@pytest.mark.parametrize("invalid", [
    b"",
    bytes.fromhex("efbbbf") + as_bytes(synthetic()),
    b"{",
    b"\\xff",
    b'{"cases":[]}',
    b'{"cases":null}',
    b'{"a":1,"a":2}',
    b'{"cases":[],"invalid":NaN}',
])
def test_invalid_bytes_or_duplicate_keys_fail_closed(invalid: bytes) -> None:
    with pytest.raises(ValueError):
        inspect_raw_holdout(invalid)


def test_wrong_or_duplicate_ids_are_rejected() -> None:
    changed = synthetic()
    changed["cases"][0]["id"] = changed["cases"][1]["id"]
    with pytest.raises(ValueError, match="duplicate"):
        inspect_raw_holdout(as_bytes(changed))
    changed = synthetic()
    changed["cases"][0]["id"] = "cs-h21"
    with pytest.raises(ValueError, match="cs-h01 through cs-h20"):
        inspect_raw_holdout(as_bytes(changed))


def test_query_and_revision_tampering_are_rejected() -> None:
    changed = synthetic()
    changed["cases"][0]["query"] = " "
    with pytest.raises(ValueError, match="nonblank query"):
        inspect_raw_holdout(as_bytes(changed))
    changed = synthetic()
    changed["source_commit"] = "0" * 40
    with pytest.raises(ValueError, match="source pin"):
        inspect_raw_holdout(as_bytes(changed))
    changed = synthetic()
    changed["cases"][1]["query"] = 123
    with pytest.raises(ValueError, match="nonblank query"):
        inspect_raw_holdout(as_bytes(changed))


def test_unpinned_source_is_reported_not_pretended_pinned() -> None:
    changed = deepcopy(synthetic())
    changed.pop("upstream_commit")
    report = inspect_raw_holdout(as_bytes(changed))
    assert report["source_pin_present_in_raw"] is False
    assert report["scoring_authorized"] is False


def test_input_never_mutated_and_candidate_hashes_not_a_freeze() -> None:
    original = synthetic()
    snapshot = deepcopy(original)
    raw = as_bytes(original)
    report = inspect_raw_holdout(raw)
    assert original == snapshot
    assert len(report["candidate_serialization_sha256"]) == 3
    assert all(len(x) == 64 for x in report["candidate_serialization_sha256"].values())
    assert report["digest_serialization_convention_confirmed"] is False

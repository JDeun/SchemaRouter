"""No-model synthetic abuse tests for external E2 unscored intake preflight."""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy

import pytest

from scripts.inspect_independent_native_e2_intake import (
    inspect_unscored_native_cohort,
)
from scripts.research_task_disposition_rubric_e0 import KINDS, LANGUAGES

PRIVATE = "ORIGINAL-PROVIDER-SECRET-NOT-FOR-CI"


def raw(obj: dict) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def example() -> tuple[dict, dict, dict, dict]:
    cases = {"cases": [
        {
            "id": f"ind-{i:02d}", "language": lang,
            "query": (
                f"Publisher task {lang} request for {kind} "
                f"unique-reference-{i}-record"
            ),
            "role": "reader",
            "expected_kind": kind,
        }
        for i, (lang, kind) in enumerate(
            ((lang, kind) for lang in LANGUAGES for kind in KINDS),
            start=1,
        )
    ]}
    gold = {"cases": [
        {
            "id": c["id"], "expected_kind": c["expected_kind"],
            "role": c["role"],
            "gold_reference_sha256": "a" * 64,
            "native_authority_sha256": "b" * 64,
        } for c in cases["cases"]
    ]}
    development = {"cases": [
        {"id": "prior-dev-01", "query": "Prior fixture with different task identifier"}
    ]}
    manifest = {
        "schema_version": 1,
        "intake_kind": "unscored_native_e2",
        "provider_repository": "publisher/provider-repo",
        "provider_commit": "c" * 40,
        "native_tool_inventory_sha256": "d" * 64,
        "case_bytes_sha256": sha(raw(cases)),
        "gold_bytes_sha256": sha(raw(gold)),
        "development_bytes_sha256": sha(raw(development)),
        "split_id": "original-publisher-locked-2026",
        "case_author": "independent-task-author",
        "gold_reviewer": "different-independent-reviewer",
        "license_spdx": "Apache-2.0",
        "source_permission_review": "pending",
        "case_language_origin": "publisher_original_not_translated",
    }
    return manifest, cases, gold, development


def evaluate(parts: tuple[dict, dict, dict, dict]) -> dict:
    m, c, g, d = deepcopy(parts)
    m.update(
        case_bytes_sha256=sha(raw(c)),
        gold_bytes_sha256=sha(raw(g)),
        development_bytes_sha256=sha(raw(d)),
    )
    return inspect_unscored_native_cohort(raw(m), raw(c), raw(g), raw(d))


def test_fifteen_strata_pass_structural_only_and_never_scoring():
    report = evaluate(example())
    assert report["case_count"] == 15
    assert report["dev_count_compared"] == 1
    for lang in LANGUAGES:
        assert report["by_language_and_disposition"][lang] == {
            kind: 1 for kind in KINDS
        }
    assert report["byte_sha256_match"] is True
    assert report["status"] == "STRUCTURAL_PREFLIGHT_ONLY"
    assert report["qualification_gate"] == "BLOCKED_EXTERNAL"
    assert report["scoring_authorized"] is False
    assert report["independent_e2_qualified"] is False
    assert report["source_author_license_verified"] is False
    assert report["provider_native_permission_gold_verified"] is False
    assert report["actual_provider_executions"] == 0
    serialized = json.dumps(report)
    assert "Publisher task" not in serialized
    assert "ind-01" not in serialized
    assert PRIVATE not in serialized


def test_permission_attestation_cannot_turn_into_e2_approval():
    m, c, g, d = example()
    m["source_permission_review"] = "attested"
    report = evaluate((m, c, g, d))
    assert report["scoring_authorized"] is False
    assert report["independent_e2_qualified"] is False


def test_tampering_verbatim_case_bytes_is_detected_before_scoring():
    m, c, g, d = example()
    c["cases"][0]["query"] += " changed"
    with pytest.raises(ValueError, match="verbatim bytes mismatch"):
        inspect_unscored_native_cohort(raw(m), raw(c), raw(g), raw(d))


@pytest.mark.parametrize("modify", (
    lambda m, c, g, d: m.update(provider_commit="unversioned"),
    lambda m, c, g, d: m.update(provider_repository="a"),
    lambda m, c, g, d: m.update(native_tool_inventory_sha256="bad"),
    lambda m, c, g, d: m.update(case_author=m["gold_reviewer"]),
    lambda m, c, g, d: m.update(license_spdx=""),
    lambda m, c, g, d: m.update(case_language_origin="translated_from_en"),
    lambda m, c, g, d: m.update(source_permission_review="self_approved"),
    lambda m, c, g, d: c["cases"].pop(),
    lambda m, c, g, d: c["cases"][0].update(expected_kind="foo"),
    lambda m, c, g, d: c["cases"][0].update(language="fr"),
    lambda m, c, g, d: c["cases"][0].update(role=None),
    lambda m, c, g, d: g["cases"][0].update(expected_kind="ambiguous"),
    lambda m, c, g, d: g["cases"][0].update(native_authority_sha256="broken"),
    lambda m, c, g, d: g["cases"][0].update(id="missing"),
    lambda m, c, g, d: d["cases"][0].update(id="ind-01"),
    lambda m, c, g, d: d["cases"][0].update(query=c["cases"][0]["query"]),
    lambda m, c, g, d: c["cases"][1].update(query=c["cases"][0]["query"]),
    lambda m, c, g, d: c["cases"][0].update(secret_password=PRIVATE),
))
def test_invalid_provenance_disposition_gold_or_overlap_fails_closed(modify):
    m, c, g, d = example()
    modify(m, c, g, d)
    with pytest.raises(ValueError):
        evaluate((m, c, g, d))


@pytest.mark.parametrize("raw_bytes", (
    b'{"cases":[], "cases":[]}',
    b'{"cases":[{"value":NaN}]}',
    b'{"cases":[{"value":1e309}]}',
    b'{"cases":"wrong"}',
    bytes.fromhex("efbbbf") + b'{"cases":[]}',
    b'\xff',
))
def test_malformed_raw_json_is_rejected(raw_bytes):
    m, c, g, d = example()
    m["case_bytes_sha256"] = sha(raw_bytes)
    with pytest.raises((ValueError, OverflowError)):
        inspect_unscored_native_cohort(raw(m), raw_bytes, raw(g), raw(d))


def test_duplicate_manifest_json_key_is_never_last_wins():
    m, c, g, d = example()
    b = raw(m)
    assert b.startswith(b"{")
    forged = b'{"schema_version":1,' + b[1:]
    with pytest.raises(ValueError, match="malformed JSON contents"):
        inspect_unscored_native_cohort(forged, raw(c), raw(g), raw(d))


def test_bounded_holdout_rows_prevent_adversarial_pairwise_blowup():
    m, c, g, d = example()
    for i in range(16, 258):
        source = dict(c["cases"][0])
        source["id"] = f"extra-case-{i}"
        source["query"] = f"unique source query number {i}"
        c["cases"].append(source)
    with pytest.raises(ValueError, match="excessive case cohort"):
        evaluate((m, c, g, d))


def test_bounded_dev_rows_prevent_adversarial_pairwise_blowup():
    m, c, g, d = example()
    for i in range(2, 259):
        d["cases"].append({
            "id": f"prior-{i}", "query": f"previous unique task {i}",
        })
    with pytest.raises(ValueError, match="excessive case cohort"):
        evaluate((m, c, g, d))


def test_large_query_is_denied_before_pairwise_comparison():
    m, c, g, d = example()
    c["cases"][0]["query"] = "z" * 2001
    with pytest.raises(ValueError, match="oversized"):
        evaluate((m, c, g, d))


def test_untrusted_duplicate_field_name_is_not_reflected_in_error():
    m, c, g, d = example()
    secret_key = ("sensitive-" + PRIVATE).encode("ascii")
    raw_case = b'{"' + secret_key + b'":1,"' + secret_key + b'":2}'
    m["case_bytes_sha256"] = sha(raw_case)
    with pytest.raises(ValueError, match="malformed JSON contents") as error:
        inspect_unscored_native_cohort(raw(m), raw_case, raw(g), raw(d))
    assert PRIVATE not in str(error.value)

"""No-model synthetic abuse tests for external E2 unscored intake preflight."""
from __future__ import annotations

import base64
import hashlib
import json
import subprocess
import sys
from copy import deepcopy

import pytest

from scripts.inspect_independent_native_e2_intake import (
    inspect_source_pinned_native_cohort,
    inspect_unscored_native_cohort,
    inspect_witness_pinned_native_cohort,
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


def witness_example() -> tuple[bytes, bytes, bytes, bytes, bytes, bytes, bytes]:
    """Synthetic original-byte reference collections; never real publisher gold."""
    m, c, g, d = example()
    native_inventory = b'{"source":"synthetic-original-private-inventory"}'
    m["native_tool_inventory_sha256"] = sha(native_inventory)
    authorities = {"references": []}
    gold_refs = {"references": []}
    for record in g["cases"]:
        ident = record["id"]
        auth_bytes = f"Native principal authority {ident} {PRIVATE}".encode()
        gold_bytes = f"Private original gold route/field {ident} {PRIVATE}".encode()
        record["native_authority_sha256"] = sha(auth_bytes)
        record["gold_reference_sha256"] = sha(gold_bytes)
        authorities["references"].append({
            "id": ident, "evidence_base64": base64.b64encode(auth_bytes).decode("ascii"),
        })
        gold_refs["references"].append({
            "id": ident, "evidence_base64": base64.b64encode(gold_bytes).decode("ascii"),
        })
    m["gold_bytes_sha256"] = sha(raw(g))
    return (
        raw(m), raw(c), raw(g), raw(d), native_inventory,
        raw(authorities), raw(gold_refs),
    )


def test_a6_all_source_native_and_gold_witness_bytes_are_exactly_bound():
    report = inspect_witness_pinned_native_cohort(*witness_example())
    assert report["case_count"] == 15
    assert report["native_inventory_bytes_sha256_match"] is True
    assert report["native_authority_witness_bytes_sha256_match"] is True
    assert report["gold_reference_witness_bytes_sha256_match"] is True
    assert report["case_witness_pairs_verified_structurally"] == 15
    assert report["gold_independently_reviewed"] is False
    assert report["source_author_license_verified"] is False
    assert report["scoring_authorized"] is False
    assert report["independent_e2_qualified"] is False
    serialized = json.dumps(report)
    assert "ind-01" not in serialized
    assert PRIVATE not in serialized


@pytest.mark.parametrize("which,mutation", (
    (5, lambda rows: rows["references"].pop()),
    (6, lambda rows: rows["references"].append(deepcopy(rows["references"][0]))),
    (5, lambda rows: rows["references"][0].update(id="foreign-case")),
    (6, lambda rows: rows["references"][0].update(evidence_base64="")),
    (5, lambda rows: rows["references"][0].update(evidence_base64="!bad-base64!")),
    (6, lambda rows: rows["references"][0].update(evidence_base64="QQ==\n")),
    (5, lambda rows: rows["references"][0].update(evidence_base64="QQ==")),
    (6, lambda rows: rows["references"][0].update(evidence_base64=1)),
    (5, lambda rows: rows["references"][0].update(evidence_base64=
               base64.b64encode(b"a" * 65537).decode("ascii"))),
    (6, lambda rows: rows["references"][0].update(extra="untrusted")),
))
def test_a6_incomplete_forged_noncanonical_or_wrong_case_witness_rejected(which, mutation):
    parts = list(witness_example())
    payload = json.loads(parts[which])
    mutation(payload)
    parts[which] = raw(payload)
    with pytest.raises(ValueError) as error:
        inspect_witness_pinned_native_cohort(*parts)
    assert PRIVATE not in str(error.value)


def test_a6_cross_swapped_native_vs_gold_evidence_is_not_interchangeable():
    parts = list(witness_example())
    parts[5], parts[6] = parts[6], parts[5]
    with pytest.raises(ValueError, match="witness"):
        inspect_witness_pinned_native_cohort(*parts)


def test_a6_every_private_case_hash_is_a_digest_of_supplied_original_bytes():
    parts = list(witness_example())
    gold = json.loads(parts[2])
    gold["cases"][0]["native_authority_sha256"] = "f" * 64
    parts[2] = raw(gold)
    manifest = json.loads(parts[0])
    manifest["gold_bytes_sha256"] = sha(parts[2])
    parts[0] = raw(manifest)
    with pytest.raises(ValueError, match="witness"):
        inspect_witness_pinned_native_cohort(*parts)


@pytest.mark.parametrize("index,payload", (
    (5, b'\xff'),
    (5, b'{"references":[],"references":[]}'),
    (6, b'{"references":[]}'),
    (5, b'{}'),
    (5, b'x' * (5 * 1024 * 1024 + 1)),
))
def test_a6_malformed_or_oversized_private_witnesses_fail_closed(index, payload):
    parts = list(witness_example())
    parts[index] = payload
    with pytest.raises(ValueError) as error:
        inspect_witness_pinned_native_cohort(*parts)
    assert PRIVATE not in str(error.value)


def test_a6_seven_stream_cli_returns_no_private_case_or_native_bytes(tmp_path):
    streams = witness_example()
    args = []
    for name, source_bytes in zip((
        "manifest", "cases", "gold", "development", "native-inventory",
        "native-authority-witnesses", "gold-reference-witnesses",
    ), streams, strict=True):
        path = tmp_path / f"{name}.json"
        path.write_bytes(source_bytes)
        args.extend((f"--{name}", str(path)))
    cmd = [sys.executable, "-m", "scripts.inspect_independent_native_e2_intake", *args]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    report = json.loads(result.stdout)
    assert report["case_witness_pairs_verified_structurally"] == 15
    assert report["scoring_authorized"] is False
    assert PRIVATE not in result.stdout
    assert "ind-01" not in result.stdout

    # Reject selecting only one witness collection, not silently fall back.
    partial = subprocess.run(cmd[:-2], capture_output=True, text=True)
    assert partial.returncode != 0


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


def test_non_utf8_inventory_manifest_preserves_source_neutral_legacy_parse_error():
    m, c, g, d = example()
    with pytest.raises(ValueError, match="malformed JSON contents"):
        inspect_unscored_native_cohort(b"\xff", raw(c), raw(g), raw(d))


def test_malformed_private_source_is_not_chained_as_exception_cause():
    m, c, g, d = example()
    malformed = b'{"private":"' + PRIVATE.encode("ascii") + b'",'
    with pytest.raises(ValueError) as error:
        inspect_unscored_native_cohort(malformed, raw(c), raw(g), raw(d))
    assert PRIVATE not in str(error.value)
    assert error.value.__cause__ is None
    assert error.value.__suppress_context__ is True


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


def test_actual_native_inventory_bytes_must_match_manifest_before_structural_receipt():
    m, c, g, d = example()
    source = b'{"native_tool_spec":"' + PRIVATE.encode("utf-8") + b'"}'
    m["native_tool_inventory_sha256"] = sha(source)
    report = inspect_source_pinned_native_cohort(
        raw(m), raw(c), raw(g), raw(d), source,
    )
    assert report["native_inventory_bytes_sha256_match"] is True
    assert report["status"] == "STRUCTURAL_PREFLIGHT_ONLY"
    assert report["source_author_license_verified"] is False
    assert report["provider_native_permission_gold_verified"] is False
    assert report["scoring_authorized"] is False
    assert report["independent_e2_qualified"] is False
    assert report["qualification_gate"] == "BLOCKED_EXTERNAL"
    assert PRIVATE not in json.dumps(report)


@pytest.mark.parametrize("submitted", (
    b'{"native_tool_spec":"changed"}',
    b"",
    "not-native-source-bytes",
    b"x" * (5 * 1024 * 1024 + 1),
))
def test_untrusted_or_mismatched_inventory_fails_without_source_leak(submitted):
    m, c, g, d = example()
    source = b'{"native_tool_spec":"' + PRIVATE.encode("utf-8") + b'"}'
    m["native_tool_inventory_sha256"] = sha(source)
    with pytest.raises(ValueError) as error:
        inspect_source_pinned_native_cohort(
            raw(m), raw(c), raw(g), raw(d), submitted,
        )
    assert PRIVATE not in str(error.value)


def test_incorrect_manifest_source_digest_cannot_be_promoted_to_verified():
    m, c, g, d = example()
    with pytest.raises(ValueError, match="native inventory bytes mismatch"):
        inspect_source_pinned_native_cohort(
            raw(m), raw(c), raw(g), raw(d), b"actual provider inventory",
        )


def test_cli_native_inventory_opt_in_does_not_expose_private_source(tmp_path):
    m, c, g, d = example()
    source = b'{"native":"' + PRIVATE.encode("utf-8") + b'"}'
    m["native_tool_inventory_sha256"] = sha(source)
    files = {}
    for name, value in (
        ("manifest", raw(m)), ("cases", raw(c)),
        ("gold", raw(g)), ("development", raw(d)),
        ("native-inventory", source),
    ):
        path = tmp_path / f"{name}.json"
        path.write_bytes(value)
        files[name] = path
    command = [sys.executable, "-m", "scripts.inspect_independent_native_e2_intake"]
    for name in ("manifest", "cases", "gold", "development"):
        command.extend((f"--{name}", str(files[name])))
    legacy = subprocess.run(command, check=True, capture_output=True, text=True)
    assert "native_inventory_bytes_sha256_match" not in legacy.stdout
    pinned = subprocess.run(
        [*command, "--native-inventory", str(files["native-inventory"])],
        check=True, capture_output=True, text=True,
    )
    assert json.loads(pinned.stdout)["native_inventory_bytes_sha256_match"] is True
    assert PRIVATE not in pinned.stdout + pinned.stderr

    # A failed intake must not echo original source content in stdout or
    # Python's command-line exception diagnostic on stderr.
    files["native-inventory"].write_bytes(source + b"-tampered")
    rejected = subprocess.run(
        [*command, "--native-inventory", str(files["native-inventory"])],
        check=False, capture_output=True, text=True,
    )
    assert rejected.returncode != 0
    assert rejected.stdout == ""
    assert "native inventory bytes mismatch" in rejected.stderr
    assert PRIVATE not in rejected.stderr

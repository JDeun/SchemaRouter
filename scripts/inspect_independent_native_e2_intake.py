"""Offline, never-scoring external E2 intake preflight (untrusted author claims).

Only checks exact input bytes, declared source identities, structural strata,
gold/case pairing and obvious DEV copying. It cannot verify third-party
authorship, license consent, native provider authority or task correctness.
Original requests, private gold and tool inventories remain local.
"""
from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.inspect_clicshopping_maintainer_holdout import (
    _finite_float,
    _reject_nonfinite,
    _unique_object,
)
from scripts.research_task_disposition_rubric_e0 import KINDS, LANGUAGES

MAX_BYTES = 5 * 1024 * 1024
SHA40 = re.compile(r"[0-9a-f]{40}\Z")
SHA64 = re.compile(r"[0-9a-f]{64}\Z")
PROVIDER = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+\Z")
SAFE_ID = re.compile(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,127}\Z")
MANIFEST_FIELDS = {
    "schema_version", "intake_kind", "provider_repository",
    "provider_commit", "native_tool_inventory_sha256", "case_bytes_sha256",
    "gold_bytes_sha256", "development_bytes_sha256", "split_id",
    "case_author", "gold_reviewer", "license_spdx",
    "source_permission_review", "case_language_origin",
}
CASE_FIELDS = {"id", "language", "query", "role", "expected_kind"}
GOLD_FIELDS = {
    "id", "expected_kind", "role", "native_authority_sha256",
    "gold_reference_sha256",
}
DEV_FIELDS = {"id", "query"}


def _raw_json(raw: bytes, label: str) -> dict[str, Any]:
    if type(raw) is not bytes or not raw or len(raw) > MAX_BYTES:
        raise ValueError(f"{label}: empty/oversized or non-bytes input")
    if raw.startswith(bytes.fromhex("efbbbf")):
        raise ValueError(f"{label}: UTF-8 BOM not allowed")
    try:
        data = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_nonfinite,
            parse_float=_finite_float,
        )
    except ValueError:
        raise ValueError(f"{label}: malformed JSON contents") from None
    if type(data) is not dict:
        raise ValueError(f"{label}: expected JSON object")
    return data


def _hash(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _nonempty(value: Any, name: str) -> str:
    if type(value) is not str or not value.strip() or len(value) > 512:
        raise ValueError(f"missing/invalid {name}")
    return value


def _rows(raw: bytes, label: str, fields: set[str]) -> list[dict[str, Any]]:
    data = _raw_json(raw, label)
    if set(data) != {"cases"}:
        raise ValueError(f"{label}: only a cases collection is accepted")
    rows = data["cases"]
    if type(rows) is not list or not rows or len(rows) > 256:
        raise ValueError(f"{label}: empty or excessive case cohort")
    ids: set[str] = set()
    for row in rows:
        if type(row) is not dict or set(row) != fields:
            raise ValueError(f"{label}: malformed case record")
        ident = row["id"]
        if type(ident) is not str or not SAFE_ID.fullmatch(ident):
            raise ValueError(f"{label}: malformed case identifier")
        if ident in ids:
            raise ValueError(f"{label}: duplicate case identifier")
        ids.add(ident)
    return rows


def _normalized_tokens(query: str) -> tuple[str, ...]:
    if type(query) is not str or not query.strip() or len(query) > 2000:
        raise ValueError("blank/oversized or non-text original query")
    normalized = unicodedata.normalize("NFKC", query).casefold()
    return tuple(re.findall(r"\w+", normalized, flags=re.UNICODE))


def _obvious_reuse(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    if not a or not b:
        return True
    if a == b:
        return True
    first, second = " ".join(a), " ".join(b)
    if min(len(a), len(b)) >= 3 and (first in second or second in first):
        return True
    shorter, longer = (set(a), set(b)) if len(a) <= len(b) else (set(b), set(a))
    return len(shorter) >= 4 and len(shorter & longer) / len(shorter) >= .90


def inspect_unscored_native_cohort(
    manifest_bytes: bytes,
    case_bytes: bytes,
    gold_bytes: bytes,
    development_bytes: bytes,
) -> dict[str, Any]:
    """Validate provenance *claims* and shape; never produce an E2 score."""
    manifest = _raw_json(manifest_bytes, "manifest")
    if set(manifest) != MANIFEST_FIELDS or type(manifest["schema_version"]) is not int:
        raise ValueError("manifest shape or strict schema version mismatch")
    if manifest["schema_version"] != 1 or manifest["intake_kind"] != "unscored_native_e2":
        raise ValueError("only unscored independent intake v1 allowed")
    if (
        type(manifest["provider_repository"]) is not str
        or not PROVIDER.fullmatch(manifest["provider_repository"])
        or type(manifest["provider_commit"]) is not str
        or not SHA40.fullmatch(manifest["provider_commit"])
    ):
        raise ValueError("provider source must have repository and exact commit")
    for field in (
        "native_tool_inventory_sha256", "case_bytes_sha256",
        "gold_bytes_sha256", "development_bytes_sha256",
    ):
        val = manifest[field]
        if type(val) is not str or not SHA64.fullmatch(val):
            raise ValueError(f"missing exact source digest: {field}")
    for field, raw in (
        ("case_bytes_sha256", case_bytes),
        ("gold_bytes_sha256", gold_bytes),
        ("development_bytes_sha256", development_bytes),
    ):
        if manifest[field] != _hash(raw):
            raise ValueError(f"verbatim bytes mismatch: {field}")
    for name in ("split_id", "case_author", "gold_reviewer", "license_spdx"):
        _nonempty(manifest[name], name)
    if (
        manifest["case_author"].strip().casefold()
        == manifest["gold_reviewer"].strip().casefold()
    ):
        raise ValueError("case author and gold reviewer must differ")
    if manifest["source_permission_review"] not in ("pending", "attested"):
        raise ValueError("invalid claimed permission-review status")
    if manifest["case_language_origin"] != "publisher_original_not_translated":
        raise ValueError("original language origin not declared")

    cases = _rows(case_bytes, "cases", CASE_FIELDS)
    gold = _rows(gold_bytes, "gold", GOLD_FIELDS)
    dev = _rows(development_bytes, "development", DEV_FIELDS)
    by_id = {g["id"]: g for g in gold}
    if {c["id"] for c in cases} != set(by_id):
        raise ValueError("case and gold identities are not a bijection")
    dev_ids = {d["id"] for d in dev}
    if dev_ids.intersection(by_id):
        raise ValueError("confirmation identifiers overlap development")
    dev_tokens = [_normalized_tokens(d["query"]) for d in dev]
    seen_queries: list[tuple[str, ...]] = []
    strata: Counter[tuple[str, str]] = Counter()
    for c in cases:
        if type(c["language"]) is not str or c["language"] not in LANGUAGES:
            raise ValueError("only original EN/KO/JA labels accepted")
        if type(c["expected_kind"]) is not str or c["expected_kind"] not in KINDS:
            raise ValueError("unknown five-way disposition label")
        role = _nonempty(c["role"], "case role")
        g = by_id[c["id"]]
        if g["role"] != role or g["expected_kind"] != c["expected_kind"]:
            raise ValueError("gold role/expected disposition differs from case")
        for name in ("gold_reference_sha256", "native_authority_sha256"):
            val = g[name]
            if type(val) is not str or not SHA64.fullmatch(val):
                raise ValueError("gold provenance requires exact digest claims")
        t = _normalized_tokens(c["query"])
        if any(_obvious_reuse(t, x) for x in (*seen_queries, *dev_tokens)):
            raise ValueError("obvious duplicate or copied development query")
        seen_queries.append(t)
        strata[c["language"], c["expected_kind"]] += 1
    if any(strata[language, kind] < 1 for language in LANGUAGES for kind in KINDS):
        raise ValueError("missing original-language five-class coverage")
    # This is **not a verified result**: all metadata is author supplied.
    # A shape-valid case can still have wrong gold, fake license, hidden
    # authority or posthoc translations; approval must be independent.
    return {
        "status": "STRUCTURAL_PREFLIGHT_ONLY",
        "case_count": len(cases),
        "dev_count_compared": len(dev),
        "by_language_and_disposition": {
            lang: {kind: strata[lang, kind] for kind in KINDS}
            for lang in LANGUAGES
        },
        "byte_sha256_match": True,
        "obvious_dev_copy_screen": "passed_not_semantic_independence",
        "source_author_license_verified": False,
        "provider_native_permission_gold_verified": False,
        "third_party_original_language_verified": False,
        "actual_provider_executions": 0,
        "model_inference_executed": False,
        "scoring_authorized": False,
        "independent_e2_qualified": False,
        "qualification_gate": "BLOCKED_EXTERNAL",
    }


def inspect_source_pinned_native_cohort(
    manifest_bytes: bytes,
    case_bytes: bytes,
    gold_bytes: bytes,
    development_bytes: bytes,
    native_inventory_bytes: bytes,
) -> dict[str, Any]:
    """Bind exact supplied native source bytes; never certify their origin.

    The provider revision, native authority, authorship and license remain
    self-attested. This cannot authorize scoring or provider execution.
    """
    if (
        type(native_inventory_bytes) is not bytes
        or not native_inventory_bytes
        or len(native_inventory_bytes) > MAX_BYTES
    ):
        raise ValueError("native inventory: empty, oversized or non-bytes input")
    manifest = _raw_json(manifest_bytes, "manifest")
    claimed = manifest.get("native_tool_inventory_sha256")
    if (
        type(claimed) is not str
        or not SHA64.fullmatch(claimed)
        or claimed != _hash(native_inventory_bytes)
    ):
        raise ValueError("native inventory bytes mismatch")
    receipt = inspect_unscored_native_cohort(
        manifest_bytes, case_bytes, gold_bytes, development_bytes,
    )
    return {**receipt, "native_inventory_bytes_sha256_match": True}


def _inspect_per_case_witness_bytes(
    submitted_bytes: bytes,
    expected_digests: dict[str, str],
    *,
    label: str,
) -> int:
    """Check original opaque witness bytes without exporting identifiers/gold.

    The separate expected digests already passed the v1 gold/manifest byte
    checks. Matching these bytes does not authenticate a provider or reviewer.
    """
    data = _raw_json(submitted_bytes, label)
    if set(data) != {"references"}:
        raise ValueError(f"{label}: expected one private reference collection")
    rows = data["references"]
    if type(rows) is not list or len(rows) != len(expected_digests):
        raise ValueError(f"{label}: incomplete private source references")
    seen: set[str] = set()
    for row in rows:
        if type(row) is not dict or set(row) != {"id", "evidence_base64"}:
            raise ValueError(f"{label}: malformed reference")
        case_id = row["id"]
        payload = row["evidence_base64"]
        if (
            type(case_id) is not str
            or SAFE_ID.fullmatch(case_id) is None
            or case_id not in expected_digests
            or case_id in seen
            or type(payload) is not str
            or not payload
        ):
            raise ValueError(f"{label}: malformed or foreign reference")
        seen.add(case_id)
        try:
            original = base64.b64decode(payload, validate=True)
        except (ValueError, binascii.Error):
            raise ValueError(f"{label}: invalid original witness encoding") from None
        if (
            not 1 <= len(original) <= 65536
            or base64.b64encode(original).decode("ascii") != payload
            or _hash(original) != expected_digests[case_id]
        ):
            raise ValueError(f"{label}: witness bytes do not match gold digest")
    if seen != set(expected_digests):
        raise ValueError(f"{label}: reference identities differ from cases")
    return len(seen)


def inspect_witness_pinned_native_cohort(
    manifest_bytes: bytes,
    case_bytes: bytes,
    gold_bytes: bytes,
    development_bytes: bytes,
    native_inventory_bytes: bytes,
    native_authority_witness_bytes: bytes,
    gold_reference_witness_bytes: bytes,
) -> dict[str, Any]:
    """Opt-in seven-stream A6 source-byte AND per-case digest binding.

    Untrusted external witnesses are *not* a publisher/reviewer signature,
    verified source-native semantic gold, license approval or scoring grant.
    """
    receipt = inspect_source_pinned_native_cohort(
        manifest_bytes, case_bytes, gold_bytes, development_bytes,
        native_inventory_bytes,
    )
    gold_rows = _rows(gold_bytes, "gold", GOLD_FIELDS)
    authority_count = _inspect_per_case_witness_bytes(
        native_authority_witness_bytes,
        {row["id"]: row["native_authority_sha256"] for row in gold_rows},
        label="native authority witnesses",
    )
    gold_count = _inspect_per_case_witness_bytes(
        gold_reference_witness_bytes,
        {row["id"]: row["gold_reference_sha256"] for row in gold_rows},
        label="gold reference witnesses",
    )
    if authority_count != gold_count or authority_count != receipt["case_count"]:
        raise ValueError("source evidence case count mismatch")
    return {
        **receipt,
        "native_authority_witness_bytes_sha256_match": True,
        "gold_reference_witness_bytes_sha256_match": True,
        "case_witness_pairs_verified_structurally": authority_count,
        "gold_independently_reviewed": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "cases", "gold", "development"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--native-inventory", type=Path)
    parser.add_argument("--native-authority-witnesses", type=Path)
    parser.add_argument("--gold-reference-witnesses", type=Path)
    args = parser.parse_args()
    original_files = (
        args.manifest.read_bytes(), args.cases.read_bytes(),
        args.gold.read_bytes(), args.development.read_bytes(),
    )
    witness_paths = (
        args.native_authority_witnesses, args.gold_reference_witnesses,
    )
    if any(path is not None for path in witness_paths) and (
        args.native_inventory is None or any(path is None for path in witness_paths)
    ):
        raise ValueError("paired private witness collections need a source snapshot")
    if args.native_inventory is None:
        report = inspect_unscored_native_cohort(*original_files)
    else:
        # Bound the fifth stream at the read boundary; no source bytes are
        # emitted on stdout or in failure strings.
        with args.native_inventory.open("rb") as handle:
            native_bytes = handle.read(MAX_BYTES + 1)
        if all(path is not None for path in witness_paths):
            assert args.native_authority_witnesses is not None
            assert args.gold_reference_witnesses is not None
            with args.native_authority_witnesses.open("rb") as handle:
                authority_bytes = handle.read(MAX_BYTES + 1)
            with args.gold_reference_witnesses.open("rb") as handle:
                gold_ref_bytes = handle.read(MAX_BYTES + 1)
            report = inspect_witness_pinned_native_cohort(
                *original_files, native_bytes, authority_bytes, gold_ref_bytes,
            )
        else:
            report = inspect_source_pinned_native_cohort(
                *original_files, native_bytes,
            )
    print(json.dumps(report, sort_keys=True, ensure_ascii=False))


if __name__ == "__main__":
    main()

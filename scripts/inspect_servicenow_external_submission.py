"""Read-only independent-publisher *claim* intake for real ServiceNow MCP.

No scoring, network, real tool invocation, authorization claim or held-out
confirmation. Exact native schema is pinned by the existing v1 DEV package.
The submission is NEVER rewritten to manufacture matching source hashes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

from scripts.external_validation_servicenow_platform_mcp import (
    load_package,
    validate_package,
)

MAX_RAW_BYTES = 512 * 1024
MAX_CASES = 200
MAX_QUERY_UTF8 = 2048
MAX_ID_UTF8 = 96
LANGUAGES = ("en", "ko", "ja")
LABELS = ("supported", "unsupported", "forbidden")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
CASE_ID = re.compile(r"^sn-ext-[a-z0-9][a-z0-9_-]{0,71}$")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("duplicate object key in external submission")
        out[key] = value
    return out


def _reject_nonfinite(value: str) -> Any:
    raise ValueError("nonfinite external JSON is forbidden")


def _finite_float(value: str) -> float:
    converted = float(value)
    if not math.isfinite(converted):
        raise ValueError("nonfinite or overrange external JSON")
    return converted


def _clean_query(value: Any) -> tuple[str, ...]:
    if type(value) is not str or not value.strip():
        raise ValueError("external task query must be nonblank UTF-8 text")
    if len(value.encode("utf-8")) > MAX_QUERY_UTF8:
        raise ValueError("oversized external task query")
    # Unicode token overlap is a deliberately conservative contamination
    # screen; passing it is NOT proof of publisher-independent authorship.
    words = tuple(re.findall(r"\w+", value.casefold(), flags=re.UNICODE))
    if not words:
        raise ValueError("external task query lacks searchable words")
    return words


def _obvious_overlap(a: tuple[str, ...], b: tuple[str, ...]) -> bool:
    if a == b:
        return True
    s, t = " ".join(a), " ".join(b)
    if len(a) >= 3 and s in t or len(b) >= 3 and t in s:
        return True
    sa, sb = set(a), set(b)
    if len(sa) >= 4 and len(sa & sb) / len(sa) >= 0.9:
        return True
    if len(sb) >= 4 and len(sa & sb) / len(sb) >= 0.9:
        return True
    return False


def inspect_submitted_bytes(
    raw: bytes,
    *,
    declared_sha256: str,
    manifest: dict[str, Any],
    dev_cases: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Reject unsafe source/case drift; NEVER certify independent test quality."""
    validate_package(manifest, dev_cases, snapshot)
    if (
        type(raw) is not bytes or not raw or len(raw) > MAX_RAW_BYTES
        or raw.startswith(b"\xef\xbb\xbf")
    ):
        raise ValueError("empty, oversized or BOM-prefixed submission")
    if type(declared_sha256) is not str or not DIGEST.fullmatch(declared_sha256):
        raise ValueError("unverified external submission SHA-256 syntax")
    digest = hashlib.sha256(raw).hexdigest()
    if digest != declared_sha256:
        raise ValueError("external submission original bytes SHA-256 mismatch")
    try:
        data = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_nonfinite,
            parse_float=_finite_float,
        )
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid strict external UTF-8 JSON") from exc
    if type(data) is not dict or data.get("schema_version") != 1:
        raise ValueError("external intake requires schema version 1")
    if data.get("split") != "proposed_external_unscored":
        raise ValueError("external split must remain proposed and unscored")
    if any(data.get(k) is True for k in (
        "independent_qualified", "heldout_scoring_allowed",
        "scoring_authorized", "provider_authorized_execution",
    )):
        raise ValueError("source intake cannot attest scoring or execution")
    source = data.get("source")
    if type(source) is not dict or source != {
        "repository": "Xerrion/servicenow-platform-mcp",
        "revision": manifest["source_revisions"]["servicenow_platform_mcp"],
        "package": "readonly",
        "tools_sha256": snapshot["tools_sha256"],
    }:
        raise ValueError("external source pin must exactly match native MCP snapshot")
    author = data.get("author_claim")
    if (
        type(author) is not dict
        or author.get("authorship_type") != "external_publisher_claimed"
        or author.get("review_requested") is not True
        or type(author.get("organization")) is not str
        or not 1 <= len(author["organization"].strip()) <= 128
        or author.get("verified_by_schemarouter") is not False
    ):
        raise ValueError("external authorship declaration requires independent review")
    rows = data.get("cases")
    if type(rows) is not list or not 1 <= len(rows) <= MAX_CASES:
        raise ValueError("external submission case count outside bounds")
    dev_ids = {row["id"] for row in dev_cases["cases"]}
    old_queries = [_clean_query(row["query"]) for row in dev_cases["cases"]]
    tools = {
        item["name"]: set(item.get("inputSchema", {}).get("properties", {}))
        for item in snapshot["tools"]
    }
    counts: dict[str, dict[str, int]] = {
        language: {label: 0 for label in LABELS}
        for language in LANGUAGES
    }
    ids: set[str] = set()
    seen_queries: list[tuple[str, ...]] = []
    for row in rows:
        if type(row) is not dict:
            raise ValueError("external case must be an object")
        ident = row.get("id")
        if (
            type(ident) is not str or len(ident.encode("utf-8")) > MAX_ID_UTF8
            or CASE_ID.fullmatch(ident) is None or ident in ids
            or ident in dev_ids
        ):
            raise ValueError("duplicate or invalid external case ID")
        ids.add(ident)
        language, label = row.get("language"), row.get("label")
        if language not in LANGUAGES or label not in LABELS:
            raise ValueError("external case has unsupported language/stratum")
        words = _clean_query(row.get("query"))
        if any(_obvious_overlap(words, prev) for prev in (
            *old_queries, *seen_queries,
        )):
            raise ValueError("external query overlaps public DEV or another submitted case")
        seen_queries.append(words)
        required = row.get("required_tools")
        fields = row.get("required_fields")
        if (
            type(required) is not list or not all(
                type(item) is str and item in tools for item in required
            )
            or len(required) != len(set(required))
            or type(fields) is not dict or set(fields) != set(required)
        ):
            raise ValueError("external case tool/field gold must match native source")
        if label == "supported" and not required:
            raise ValueError("supported external case needs native gold tool")
        if label == "unsupported" and (required or fields):
            raise ValueError("unsupported external case cannot include positive tool gold")
        # Forbidden claims cannot be validated from read-only MCP schema alone.
        # Even a syntactically valid forbidden row needs owner permission review.
        for tool_name, specified in fields.items():
            if (
                type(specified) is not list or not specified
                or len(specified) != len(set(specified))
                or any(type(name) is not str or name not in tools[tool_name]
                       for name in specified)
            ):
                raise ValueError("required external fields not present in native tool")
        counts[language][label] += 1
    missing = [
        f"{language}:{label}"
        for language in LANGUAGES for label in ("supported", "unsupported")
        if counts[language][label] == 0
    ]
    return {
        "schema_version": 1,
        "status": "BLOCKED_EXTERNAL_REVIEW_UNSCORED",
        "evidence_tier": "PROVISIONAL_EXTERNAL_AUTHORSHIP_CLAIM_NOT_ATTESTED",
        "submission_verbatim_sha256": digest,
        "native_upstream_revision": source["revision"],
        "native_snapshot_sha256": source["tools_sha256"],
        "original_dev_package": manifest["package_id"],
        "case_count": len(rows),
        "language_stratum_counts": counts,
        "missing_minimum_language_strata": missing,
        "permission_review_required": True,
        "author_identity_verified": False,
        "source_originality_semantically_verified": False,
        "obvious_query_overlap_detected": False,
        "independent_e2_qualified": False,
        "calibrated_no_fit": False,
        "heldout_scoring_allowed": False,
        "provider_native_tool_execution_measured": False,
        "manual_review_required": (
            "Contact original source owner out-of-band, verify authorship, "
            "source rights/role visibility, permission/forbidden cases, "
            "proposed task labels, original case bytes, and prospectively "
            "freeze scorer, K, runtime, metric and consent before scoring."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--submission", type=Path, required=True)
    parser.add_argument("--declared-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    manifest, dev_cases, snapshot = load_package(
        args.package_dir, args.snapshot,
    )
    report = inspect_submitted_bytes(
        args.submission.read_bytes(),
        declared_sha256=args.declared_sha256,
        manifest=manifest, dev_cases=dev_cases, snapshot=snapshot,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": report["status"],
        "submission_verbatim_sha256": report["submission_verbatim_sha256"],
        "case_count": report["case_count"],
        "heldout_scoring_allowed": False,
    }, sort_keys=True))


if __name__ == "__main__":
    main()

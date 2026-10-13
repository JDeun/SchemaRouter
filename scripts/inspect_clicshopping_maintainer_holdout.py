"""Read-only, unscored intake of verbatim ClicShopping maintainer holdout JSON.

The exact external JSON bytes are evidence; never reserialize or rewrite them
to force a declared SHA-256 match. This gate is deliberately NOT a scorer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SOURCE_SHA = "8ada7f1f392f3dd2800e825dac8d245dfd53944a"
DECLARED_SHA256 = "a4a3a9d1b9ef6899ca863810247c9709b4b92f8d492fcb866845052db4e7a8f0"
EXPECTED_IDS = tuple(f"cs-h{index:02d}" for index in range(1, 21))
MAX_SOURCE_BYTES = 5 * 1024 * 1024


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate keys instead of silently taking the last gold label."""
    value: dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError(f"duplicate JSON object key: {key}")
        value[key] = item
    return value


def _reject_nonfinite(value: str) -> Any:
    raise ValueError(f"nonfinite JSON constant is forbidden: {value}")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def inspect_raw_holdout(
    raw: bytes,
    *,
    declared_sha256: str = DECLARED_SHA256,
) -> dict[str, Any]:
    """Check source bytes and syntactic IDs; never certify labels or scoring."""
    if not raw or len(raw) > MAX_SOURCE_BYTES or raw.startswith(b"\\xef\\xbb\\xbf"):
        raise ValueError("empty, oversized or BOM-prefixed source bytes")
    try:
        payload = json.loads(
            raw.decode("utf-8", errors="strict"),
            object_pairs_hook=_unique_object,
            parse_constant=_reject_nonfinite,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid UTF-8 JSON source: {exc}") from exc

    if not isinstance(payload, dict):
        raise ValueError("maintainer submission must be a JSON object")
    rows = payload.get("cases")
    if not isinstance(rows, list) or len(rows) != len(EXPECTED_IDS):
        raise ValueError("require exactly 20 verbatim cases in a cases array")
    if any(not isinstance(item, dict) for item in rows):
        raise ValueError("each case must be an object")

    ids = [row.get("id") for row in rows]
    if any(not isinstance(case_id, str) for case_id in ids):
        raise ValueError("case IDs must be strings")
    if len(set(ids)) != len(ids):
        raise ValueError("duplicate maintainer holdout case ID")
    if set(ids) != set(EXPECTED_IDS):
        raise ValueError("case IDs must equal cs-h01 through cs-h20")
    if any(not isinstance(row.get("query"), str) or not row["query"].strip()
           for row in rows):
        raise ValueError("each original case must have a nonblank query")

    # Reject explicit conflicting source pins, but absence is NOT proof of pin.
    source_metadata = {
        field: payload[field]
        for field in ("upstream_commit", "source_commit", "pinned_upstream_commit")
        if field in payload
    }
    if any(value != SOURCE_SHA for value in source_metadata.values()):
        raise ValueError("source pin differs from maintainer-declared commit")

    # These candidate encodings are DIAGNOSTIC only. A matching candidate is
    # not authority to choose a serialization convention post hoc.
    representations = {
        "verbatim_utf8_bytes": raw,
        "sorted_compact_utf8": json.dumps(
            payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8"),
        "sorted_default_ascii": json.dumps(
            payload, sort_keys=True
        ).encode("utf-8"),
    }
    digests = {name: _sha256(data) for name, data in representations.items()}
    if len(declared_sha256) != 64 or any(c not in "0123456789abcdef"
                                         for c in declared_sha256):
        raise ValueError("invalid declared SHA-256")

    return {
        "status": "unscored_structural_intake_only",
        "source_repository": "ClicShopping/ClicShopping",
        "source_commit_declared": SOURCE_SHA,
        "source_pin_present_in_raw": bool(source_metadata),
        "verbatim_file_bytes": len(raw),
        "verbatim_file_sha256": digests["verbatim_utf8_bytes"],
        "maintainer_declared_sha256": declared_sha256,
        "candidate_serialization_sha256": digests,
        "declared_sha256_matches": [
            name for name, digest in digests.items()
            if digest == declared_sha256
        ],
        "digest_serialization_convention_confirmed": False,
        "case_ids": list(EXPECTED_IDS),
        "case_count": len(rows),
        "issue_declared_groups": {
            "supported": list(EXPECTED_IDS[:12]),
            "read_only_forbidden": list(EXPECTED_IDS[12:15]),
            "unsupported": list(EXPECTED_IDS[15:]),
        },
        "gold_routes_and_permissions_verified": False,
        "independent_case_and_label_review_pending": True,
        "source_snapshot_accepted_for_scoring": False,
        "scoring_authorized": False,
        "model_calls": 0,
        "live_endpoint_calls": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, required=True,
                        help="Verbatim upstream UTF-8 JSON (never rewrite it)")
    parser.add_argument("--json-out", type=Path,
                        help="Optional unscored provenance report path")
    args = parser.parse_args()
    report = inspect_raw_holdout(args.raw.read_bytes())
    rendered = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\\n"
    if args.json_out:
        args.json_out.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


if __name__ == "__main__":
    main()

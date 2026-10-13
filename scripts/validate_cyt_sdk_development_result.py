"""Fail-closed integrity check for *SDK-only* CYT development outputs (#839).

This validates source identity and tool selection structure, NOT retrieval quality,
full CYT Tiering/Proxy/Hook behavior, agent outcomes or independent held-out data.
No network, models, native CYT package or external credentials are required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path
from typing import Any

PINNED_CYT_REVISION = "9327aeb1199d15a67aee61bbd7c0d8fb4e64e8b4"
SDK_BOUNDARY = "cyt-indexer-sdk prune_catalog_bm25_and_retrieve"
SDK_NAME = "Clear Your Tools native composite BM25"
CYT_OPTIONS = {
    "score_tool": 0.4,
    "score_tool_enum": 0.1,
    "prune_enums": True,
    "pipeline": ["bm25"],
}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unique_nonblank(values: list[Any], label: str) -> list[str]:
    if any(not isinstance(v, str) or not v.strip() for v in values):
        raise ValueError(f"{label}: empty or non-string identity")
    if len(values) != len(set(values)):
        raise ValueError(f"{label}: duplicate identity")
    return values


def validate_inputs(catalog: Any, cases: Any) -> tuple[list[str], list[str]]:
    if not isinstance(catalog, dict) or not isinstance(cases, dict):
        raise ValueError("catalog and cases must be objects")
    tools, tasks = catalog.get("tools"), cases.get("cases")
    if not isinstance(tools, list) or not tools:
        raise ValueError("catalog must contain tools")
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("cases must contain tasks")
    if any(not isinstance(t, dict) for t in tools):
        raise ValueError("invalid catalog tool")
    if any(not isinstance(t, dict) for t in tasks):
        raise ValueError("invalid development case")
    names = _unique_nonblank([t.get("name") for t in tools], "catalog tools")
    ids = _unique_nonblank([t.get("id") for t in tasks], "case IDs")
    if any(
        not isinstance(t.get("description"), str)
        or not isinstance(t.get("input_schema"), dict)
        for t in tools
    ):
        raise ValueError("invalid tool description/input schema")
    if any(not isinstance(t.get("query"), str) or not t["query"].strip()
           for t in tasks):
        raise ValueError("empty or invalid query")
    return names, ids


def validate_sdk_output(
    payload: Any,
    catalog: Any,
    cases: Any,
    *,
    catalog_sha256: str,
    cases_sha256: str,
    expected_revision: str = PINNED_CYT_REVISION,
) -> dict[str, Any]:
    names, ids = validate_inputs(catalog, cases)
    if not isinstance(payload, dict):
        raise ValueError("SDK output must be an object")
    if payload.get("schema_version") != 1 or type(payload["schema_version"]) is bool:
        raise ValueError("invalid SDK schema version")
    if payload.get("status") != "development_unfrozen":
        raise ValueError("SDK result cannot claim a frozen benchmark")
    if payload.get("performance_evidence") is not False:
        raise ValueError("SDK result is not independent performance evidence")
    if payload.get("sdk_only") is not True:
        raise ValueError("SDK-only provenance must be explicit")
    if payload.get("full_cyt_e2e_verified") is not False:
        raise ValueError("SDK is not the full CYT Proxy/Hook")
    if payload.get("scoring_authorized") is not False:
        raise ValueError("unfrozen development output cannot authorize scoring")
    if payload.get("catalog_size") != len(names) or (
        type(payload["catalog_size"]) is bool
    ):
        raise ValueError("catalog-size mismatch")
    source = payload.get("inputs")
    if not isinstance(source, dict) or source != {
        "catalog_sha256": catalog_sha256,
        "cases_sha256": cases_sha256,
    }:
        raise ValueError("catalog/case source digest mismatch")
    if not re.fullmatch(r"[a-f0-9]{40}", expected_revision):
        raise ValueError("expected CYT revision must be a commit SHA")
    if expected_revision != PINNED_CYT_REVISION:
        raise ValueError("development CYT source pin is not approved")
    impl = payload.get("implementation")
    if not isinstance(impl, dict) or (
        impl.get("name") != SDK_NAME
        or impl.get("boundary") != SDK_BOUNDARY
        or impl.get("revision") != expected_revision
        or impl.get("options") != CYT_OPTIONS
        or type(impl.get("repeats_per_query")) is not int
        or impl["repeats_per_query"] < 1
    ):
        raise ValueError("native SDK boundary/options/revision drift")
    rows = payload.get("results")
    if not isinstance(rows, list) or len(rows) != len(ids):
        raise ValueError("missing or extra development result rows")
    result_ids = _unique_nonblank(
        [row.get("id") if isinstance(row, dict) else None for row in rows],
        "result case IDs",
    )
    if result_ids != ids:
        raise ValueError("result IDs/order mismatch; rows cannot be silently dropped")
    allowed = set(names)
    for row in rows:
        candidates = row.get("candidate_tools")
        if not isinstance(candidates, list):
            raise ValueError("candidate_tools must be a list")
        _unique_nonblank(candidates, "candidate tools")
        if set(candidates) - allowed:
            raise ValueError("SDK selected tool outside the shared catalog")
        count = row.get("candidate_count")
        if type(count) is not int or count != len(candidates):
            raise ValueError("candidate_count differs from candidate tools")
        latency = row.get("latency_ms")
        if (type(latency) not in (int, float)
                or not math.isfinite(latency) or latency < 0):
            raise ValueError("invalid nonfinite/negative SDK latency")
        for field in ("optional_chunk_count_in", "optional_chunk_count_out"):
            chunk_count = row.get(field)
            if chunk_count is not None and (
                type(chunk_count) is not int or chunk_count < 0
            ):
                raise ValueError(f"{field} must be an integer or null")
    return {
        "status": "development_integrity_verified_unscored",
        "case_count": len(ids),
        "catalog_size": len(names),
        "sdk_revision": expected_revision,
        "sdk_only": True,
        "full_cyt_e2e_verified": False,
        "scoring_authorized": False,
        "performance_evidence": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--expected-revision", required=True)
    args = parser.parse_args()
    output = validate_sdk_output(
        json.loads(args.result.read_text(encoding="utf-8")),
        json.loads(args.catalog.read_text(encoding="utf-8")),
        json.loads(args.cases.read_text(encoding="utf-8")),
        catalog_sha256=sha256_file(args.catalog),
        cases_sha256=sha256_file(args.cases),
        expected_revision=args.expected_revision,
    )
    print(json.dumps(output, sort_keys=True))


if __name__ == "__main__":
    main()

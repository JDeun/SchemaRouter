"""Immutable, read-only post-hoc overlap audit of published ServiceNow DEV.

This measures a VARIABLE-WIDTH union diagnostic; it neither selects product
routes nor authorizes a K5 fusion algorithm, no-fit rejection or agent success.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any

from scripts.external_validation_servicenow_platform_mcp import (
    load_package,
    validate_package,
)
from scripts.research_servicenow_native_e5_dev import (
    MODEL_REVISION,
    WIDTHS,
    case_metrics,
    strict_permutation,
    summarize,
)

PINNED_REPORT_SHA256 = "4b82ffee9b55b4f8eae86a8cde87bec28429edda7d22afddc28789a18dce0237"
PINNED_SNAPSHOT_FILE_SHA256 = "0bfddf03f20811ee8d0b5b34221e1b14868622f9350bebcf62e1003fbad6ade8"
PINNED_NATIVE_TOOL_SHA256 = "006045422791939ff603420080e2f759de38a19329eeb0c1b80e264ab4897940"
PINNED_UPSTREAM = "5bcb83b29ab5b30aee07cabaa8df974881c47126"
PINNED_RUN = 38909470584
EXPECTED_IDS = tuple(f"sn-dev-{i:03d}" for i in range(1, 25))
ORIGINAL_ARMS = (
    "static_full", "lexical_k3", "lexical_k5", "e5_k3", "e5_k5",
)


def verify_sha(raw: bytes, expected: str, *, kind: str) -> None:
    if hashlib.sha256(raw).hexdigest() != expected:
        raise ValueError(f"pinned {kind} raw SHA-256 mismatch")


def ordered_union(first: list[str], second: list[str], *, allowed: set[str]) -> list[str]:
    """Preserve original lexical K5 rank, append only genuinely new E5 K5 IDs."""
    if (
        len(first) != 5 or len(second) != 5
        or len(set(first)) != 5 or len(set(second)) != 5
        or set(first + second) - allowed
        or any(type(x) is not str for x in first + second)
    ):
        raise ValueError("invalid K5 source-preserving candidate lists")
    return list(dict.fromkeys(first + second))


def audit(
    report: dict[str, Any],
    manifest: dict[str, Any],
    cases: dict[str, Any],
    snapshot: dict[str, Any],
) -> dict[str, Any]:
    """Reconstruct source-native union without modifying original DEV labels."""
    validate_package(manifest, cases, snapshot)
    if (
        report.get("study") != "native_servicenow_original_visible_dev_e5_vs_lexical"
        or report.get("status") != "same_author_visible_dev_not_independent"
        or report.get("model_revision") != MODEL_REVISION
        or report.get("upstream_commit") != PINNED_UPSTREAM
        or report.get("native_readonly_tools_sha256") != PINNED_NATIVE_TOOL_SHA256
        or snapshot["tools_sha256"] != PINNED_NATIVE_TOOL_SHA256
        or report.get("limitations", {}).get("release_authorized") is not False
        or report.get("limitations", {}).get("original_visible_dev_only") is not True
        or report.get("limitations", {}).get("no_fit_calibrated") is not False
        or report.get("actions_run_id") != str(PINNED_RUN)
        or tuple(x.get("id") for x in report.get("cases", [])) != EXPECTED_IDS
        or tuple(x.get("id") for x in cases["cases"]) != EXPECTED_IDS
        or tuple(WIDTHS) != (3, 5)
    ):
        raise ValueError("original source, model, DEV case identities or scope drifted")

    source = {tool["name"]: tool for tool in snapshot["tools"]}
    allowed = set(source)
    original: list[dict[str, Any]] = []
    union_rows = []
    for measured, case in zip(report["cases"], cases["cases"], strict=True):
        if (
            measured.get("kind") != case["label"]
            or measured.get("original_visible_dev_query") != case["query"]
            or set(measured.get("metrics", {})) != set(ORIGINAL_ARMS)
            or set(measured.get("selected", {})) != set(ORIGINAL_ARMS)
        ):
            raise ValueError("original published DEV labels or arms drifted")
        lexical = measured["lexical_order"]
        semantic = measured["e5_order"]
        strict_permutation(lexical, allowed)
        strict_permutation(semantic, allowed)
        if measured["selected"] != {
            "static_full": list(source),
            "lexical_k3": lexical[:3],
            "lexical_k5": lexical[:5],
            "e5_k3": semantic[:3],
            "e5_k5": semantic[:5],
        }:
            raise ValueError("original ranked prefixes or native static baseline drifted")
        for arm in ORIGINAL_ARMS:
            exact = case_metrics(case, measured["selected"][arm], source)
            if measured["metrics"][arm] != exact:
                raise ValueError("published native per-case metrics were modified")
        original.append(measured)

        selected = ordered_union(lexical[:5], semantic[:5], allowed=allowed)
        metric = case_metrics(case, selected, source)
        union_rows.append({
            "id": case["id"],
            "kind": case["label"],
            "selected_original_native_ids": selected,
            "candidate_count": len(selected),
            "metrics": metric,
            "lexical_k5_required_hit": (
                measured["metrics"]["lexical_k5"]["route_hits"]
            ),
            "e5_k5_required_hit": measured["metrics"]["e5_k5"]["route_hits"],
        })
    if summarize(original, cases["cases"]) != report["summary"]:
        raise ValueError("original published macro/micro source scores changed")

    supported = [r for r in union_rows if r["kind"] == "supported"]
    unsupported = [r for r in union_rows if r["kind"] == "unsupported"]
    tool_total = sum(r["metrics"]["route_required"] for r in supported)
    field_total = sum(r["metrics"]["field_required"] for r in supported)
    if len(supported) != 20 or len(unsupported) != 4 or tool_total != 20:
        raise ValueError("union audit denominator or case balance changed")
    widths = {str(width): sum(r["candidate_count"] == width for r in union_rows)
              for width in range(5, 11)}
    return {
        "schema_version": 1,
        "study": "servicenow_visible_dev_post_hoc_k5_complementarity",
        "evidence_class": "POST_HOC_PREVIOUSLY_VISIBLE_ENGLISH_DEV_ONLY",
        "upstream_commit": PINNED_UPSTREAM,
        "model_revision": MODEL_REVISION,
        "pinned_source_run": PINNED_RUN,
        "pinned_report_sha256": PINNED_REPORT_SHA256,
        "pinned_snapshot_file_sha256": PINNED_SNAPSHOT_FILE_SHA256,
        "supported_cases": len(supported),
        "unsupported_cases": len(unsupported),
        "source_required_tool_count": tool_total,
        "observed_union_required_tool_recall": (
            sum(r["metrics"]["route_hits"] for r in supported) / tool_total
        ),
        "observed_union_native_required_field_recall": (
            sum(r["metrics"]["field_hits"] for r in supported) / field_total
            if field_total else None
        ),
        "mean_native_tool_count": mean(r["candidate_count"] for r in union_rows),
        "candidate_count_histogram": widths,
        "mean_native_canonical_visible_bytes": mean(
            r["metrics"]["visible_native_bytes"] for r in union_rows
        ),
        "mean_lexical_k5_visible_bytes": mean(
            r["metrics"]["lexical_k5"]["visible_native_bytes"] for r in original
        ),
        "original_lexical_k5_tool_recall": report["summary"]["lexical_k5"][
            "required_tool_recall_micro"
        ],
        "original_e5_k5_tool_recall": report["summary"]["e5_k5"][
            "required_tool_recall_micro"
        ],
        "unsupported_nonempty_not_no_fit": sum(
            r["metrics"]["unsupported_nonempty_not_no_fit"] for r in unsupported
        ),
        "supported_cases_still_missed": [
            r["id"] for r in supported
            if r["metrics"]["route_hits"] != r["metrics"]["route_required"]
        ],
        "raw": union_rows,
        "limitations": {
            "new_independent_query_or_gold": False,
            "exploratory_after_observing_original_e5_failure": True,
            "fixed_k5_product_equivalence": False,
            "calibrated_abstention": False,
            "measured_agent_task_completion": False,
            "measured_union_cpu_latency_p95": False,
            "may_promote_model_or_release": False,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report", type=Path, required=True)
    ap.add_argument("--snapshot", type=Path, required=True)
    ap.add_argument("--package-dir", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    raw_report, raw_snapshot = args.report.read_bytes(), args.snapshot.read_bytes()
    verify_sha(raw_report, PINNED_REPORT_SHA256, kind="report")
    verify_sha(raw_snapshot, PINNED_SNAPSHOT_FILE_SHA256, kind="snapshot")
    manifest, cases, snapshot = load_package(args.package_dir, args.snapshot)
    result = audit(json.loads(raw_report), manifest, cases, snapshot)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, sort_keys=True, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "post_hoc": True,
        "union_required_tool_recall": result["observed_union_required_tool_recall"],
        "mean_native_tools": result["mean_native_tool_count"],
        "mean_visible_bytes": result["mean_native_canonical_visible_bytes"],
        "release_authorized": False,
    }))


if __name__ == "__main__":
    main()

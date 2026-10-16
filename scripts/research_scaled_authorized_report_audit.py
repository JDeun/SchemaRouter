"""Fail-closed, read-only audit of #1428 synthetic DEV benchmark reports.

This verifies per-case output integrity and recomputes paired regressions.
A synthetically selected DEV winner is NEVER a product promotion decision.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any

from benchmarks.current_adapter_scaled_authorized_dev_v1 import SIZES, WIDTHS
from scripts.research_current_main_multilingual_dev import encoded

CONDITIONS = ("v1_k24", *(f"v3_k{width}" for width in WIDTHS))
LANGUAGES = ("en", "ko", "ja")
ROLES = ("viewer", "editor")
PER_SCALE = 27
HEX = frozenset("0123456789abcdef")


def _digest(value: Any) -> bool:
    return (type(value) is str and len(value) == 64
            and all(c in HEX for c in value))


def _finite(value: Any) -> bool:
    return type(value) in (int, float) and math.isfinite(value) and value >= 0


def _aggregate(rows: list[dict[str, Any]], condition: str) -> dict[str, int]:
    entries = [row["conditions"][condition] for row in rows]
    return {
        "cases": len(rows),
        "supported": sum(row["required_route"] is not None for row in rows),
        "required_routes_found": sum(item["route_found"] for item in entries),
        "required_fields_total": sum(item["required_field_count"] for item in entries),
        "required_fields_found": sum(
            len(item["required_fields_found"]) for item in entries
        ),
        "full_field_coverage": sum(
            item["all_required_fields_found"] for item in entries
        ),
        "unsupported_nonempty_shortlist": sum(
            item["unsupported_nonempty_shortlist"] for item in entries
        ),
        "unauthorized_candidate_count": sum(
            item["unauthorized_count"] for item in entries
        ),
    }


def _costs(rows: list[dict[str, Any]], name: str) -> dict[str, float]:
    values = [item["conditions"][name] for item in rows]
    elapsed = sorted(item["retrieval_rerank_ms"] for item in values)
    p95 = elapsed[math.ceil(len(elapsed) * 0.95) - 1]
    return {
        "p95_retrieval_rerank_ms": round(p95, 5),
        "mean_top5_schema_bytes": round(
            sum(item["schema_bytes"] for item in values) / len(values), 2,
        ),
    }


def audit(report: Any) -> dict[str, Any]:
    if not isinstance(report, dict) or report.get("schema_version") != 1:
        raise ValueError("untrusted scaled benchmark report version")
    scope = report.get("scope")
    if not isinstance(scope, dict) or any(
        scope.get(key) is not False for key in (
            "independent_confirmation", "automatic_product_promotion",
            "may_release", "actual_agent_task_success",
            "model_or_external_tools_executed",
        )
    ):
        raise ValueError("invalid or overclaimed scientific scope")
    if (report.get("id") != "author_visible_scaled_current_adapter_principal_field_dev"
            or not _digest(report.get("source_sha256"))
            or not _digest(report.get("task_manifest_sha256"))):
        raise ValueError("missing immutable DEV source or task fingerprint")
    sources = report.get("source_file_sha256")
    if (not isinstance(sources, dict) or not sources
            or any(type(k) is not str or not k or not _digest(v)
                   for k, v in sources.items())):
        raise ValueError("missing per-file source SHA manifest")
    if hashlib.sha256(encoded(sources)).hexdigest() != report["source_sha256"]:
        raise ValueError("source-manifest digest inconsistency")
    sizes = report.get("registered_sizes")
    if (not isinstance(sizes, list)
            or len(sizes) != len(set(map(str, sizes)))
            or any(type(s) is not int or s not in SIZES for s in sizes)
            or not sizes or report.get("candidate_widths") != list(WIDTHS)):
        raise ValueError("unregistered benchmark scale/width")
    rows = report.get("cases")
    if not isinstance(rows, list) or len(rows) != PER_SCALE * len(sizes):
        raise ValueError("incomplete or duplicated scaled benchmark cohort")
    required_calls = len(rows) * len(CONDITIONS)
    if (report.get("actual_authorized_router_calls") != required_calls
            or report.get("required_router_calls_expected") != required_calls):
        raise ValueError("missing real current authorized retrieval calls")

    by_scale: dict[int, set[str]] = defaultdict(set)
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("malformed benchmark case")
        size = row.get("catalog_size")
        case_id = row.get("case_id")
        lang, role = row.get("language"), row.get("role")
        gold = row.get("required_route")
        fields = row.get("required_fields")
        if (type(size) is not int or size not in sizes
                or type(case_id) is not str or not case_id
                or case_id in by_scale[size] or lang not in LANGUAGES
                or role not in ROLES or not isinstance(fields, list)
                or any(type(f) is not str or not f for f in fields)
                or len(set(fields)) != len(fields)
                or (gold is not None and (type(gold) is not str or not gold))
                or (gold is None and fields)
                or row.get("authorized_full_contains_required_route") is not
                    (gold is not None)
                or type(row.get("eligible_candidate_count")) is not int
                or row["eligible_candidate_count"] <= 0):
            raise ValueError("invalid or duplicate case label/principal")
        by_scale[size].add(case_id)
        key = f"{size}/{lang}/{role}"
        groups[key].append(row)
        variants = row.get("conditions")
        if not isinstance(variants, dict) or set(variants) != set(CONDITIONS):
            raise ValueError("missing or forged candidate-width control")
        for name in CONDITIONS:
            item = variants[name]
            if not isinstance(item, dict):
                raise ValueError("missing scored shortlist")
            ids = item.get("top5_ids")
            found_fields = item.get("required_fields_found")
            if (not isinstance(ids, list) or len(ids) > 5
                    or any(type(x) is not str or not x for x in ids)
                    or len(set(ids)) != len(ids)
                    or not isinstance(found_fields, list)
                    or any(type(x) is not str for x in found_fields)
                    or len(set(found_fields)) != len(found_fields)
                    or not set(found_fields) <= set(fields)
                    or type(item.get("required_field_count")) is not int
                    or item["required_field_count"] != len(fields)
                    or type(item.get("route_found")) is not bool
                    or item["route_found"] != (gold is not None and gold in ids)
                    or type(item.get("all_required_fields_found")) is not bool
                    or item["all_required_fields_found"] != (
                        gold is not None and gold in ids
                        and set(found_fields) == set(fields)
                    )
                    or type(item.get("unsupported_nonempty_shortlist")) is not bool
                    or item["unsupported_nonempty_shortlist"] != (
                        gold is None and bool(ids)
                    )
                    or type(item.get("unauthorized_count")) is not int
                    or item["unauthorized_count"] != 0
                    or not _finite(item.get("schema_bytes"))
                    or not _finite(item.get("retrieval_rerank_ms"))):
                raise ValueError("inconsistent or unsafe scored candidate row")

    cohorts = list(by_scale.values())
    if (any(len(cohort) != PER_SCALE for cohort in cohorts)
            or any(cohort != cohorts[0] for cohort in cohorts[1:])):
        raise ValueError("nonpaired or incomplete three-scale DEV case roster")
    all_totals = report.get("overall")
    saved_groups = report.get("by_scale_language_role")
    if not isinstance(all_totals, dict) or set(all_totals) != set(CONDITIONS):
        raise ValueError("missing scored aggregate")
    if not isinstance(saved_groups, dict) or set(saved_groups) != set(groups):
        raise ValueError("omitted language/role/scale strata")
    for name in CONDITIONS:
        recomputed = _aggregate(rows, name)
        if not isinstance(all_totals[name], dict) or any(
            all_totals[name].get(k) != v
            for k, v in {**recomputed, **_costs(rows, name)}.items()
        ):
            raise ValueError("aggregate metric does not equal case evidence")
    for key, cohort in groups.items():
        for name in CONDITIONS:
            saved = saved_groups[key].get(name)
            if not isinstance(saved, dict) or any(
                saved.get(k) != v
                for k, v in {
                    **_aggregate(cohort, name),
                    **_costs(cohort, name),
                }.items()
            ):
                raise ValueError("stratified metric does not equal case evidence")

    decisions = {}
    for name in CONDITIONS[1:]:
        control = all_totals["v1_k24"]
        candidate = all_totals[name]
        regressions = []
        for key, cohort in groups.items():
            base, newer = (_aggregate(cohort, tag) for tag in ("v1_k24", name))
            if any(newer[m] < base[m] for m in (
                "required_routes_found", "required_fields_found",
                "full_field_coverage",
            )):
                regressions.append(key + ":supported")
            if (newer["unsupported_nonempty_shortlist"]
                    > base["unsupported_nonempty_shortlist"]):
                regressions.append(key + ":unsupported")
        base_p95 = control["p95_retrieval_rerank_ms"]
        candidate_p95 = candidate["p95_retrieval_rerank_ms"]
        if not _finite(base_p95) or not _finite(candidate_p95) or base_p95 == 0:
            raise ValueError("unmeasured/invalid CPU timing in source aggregate")
        cpu_ratio = candidate_p95 / base_p95
        positive_gain = (
            candidate["required_routes_found"] > control["required_routes_found"]
            or candidate["required_fields_found"] > control["required_fields_found"]
        )
        decisions[name] = {
            "route_delta": candidate["required_routes_found"]
            - control["required_routes_found"],
            "field_delta": candidate["required_fields_found"]
            - control["required_fields_found"],
            "p95_relative_to_v1": round(cpu_ratio, 5),
            "group_regressions": regressions,
            "positive_observed_gain": positive_gain,
            "under_150ms_research_cpu_guard": candidate_p95 <= 150.0,
            "dev_diagnostic_gate": (
                not regressions and positive_gain and cpu_ratio <= 1.5
                and candidate_p95 <= 150.0
            ),
            "may_promote": False,
        }
    return {
        "scope": "EXPOSED_SYNTHETIC_DEV_AUDIT_NOT_INDEPENDENT",
        "report_sha256": hashlib.sha256(
            json.dumps(report, sort_keys=True, ensure_ascii=False,
                       allow_nan=False, separators=(",", ":")).encode()
        ).hexdigest(),
        "sizes": sizes,
        "per_scale": PER_SCALE,
        "paired_cases": len(rows),
        "source_sha256": report["source_sha256"],
        "decisions": decisions,
        "independent_confirmation": False,
        "may_release": False,
        "automatic_product_promotion": False,
    }


def verify_frozen_source(raw: bytes, manifest: dict[str, Any]) -> dict[str, Any]:
    """Pin exact archived experiment bytes; reject substitutes and missing runs."""
    if (
        not isinstance(manifest, dict)
        or manifest.get("schema_version") != 1
        or manifest.get("source_repository") != "JDeun/SchemaRouter"
        or manifest.get("source_workflow_run_id") != 38839753512
        or manifest.get("source_artifact_id") != 12020808680
        or manifest.get("source_artifact_file") != "report.json"
        or not _digest(manifest.get("source_report_raw_sha256"))
        or hashlib.sha256(raw).hexdigest() != manifest["source_report_raw_sha256"]
    ):
        raise ValueError("unverified or replaced frozen Actions report")
    report = json.loads(raw)
    if (
        report.get("source_commit") != manifest.get("source_commit")
        or report.get("source_sha256") != manifest.get("source_file_manifest_sha256")
        or report.get("task_manifest_sha256") !=
            manifest.get("query_gold_manifest_sha256")
        or report.get("registered_sizes") != manifest.get("registered_sizes")
        or len(report.get("cases", [])) != manifest.get("paired_cases")
        or report.get("actual_authorized_router_calls") !=
            manifest.get("actual_authorized_router_calls")
        or hashlib.sha256(
            json.dumps(report, sort_keys=True, ensure_ascii=False,
                       allow_nan=False, separators=(",", ":")).encode()
        ).hexdigest() != manifest.get("source_report_canonical_sha256")
    ):
        raise ValueError("frozen source contract or scientific cohort changed")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    frozen = json.loads(args.manifest.read_text(encoding="utf-8"))
    report = verify_frozen_source(args.input.read_bytes(), frozen)
    result = audit(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "status": result["scope"], "paired_cases": result["paired_cases"],
        "champions": [], "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Paired V1 incumbent vs V2 incumbent retrieval, current CPU + exposed DEV.

Both weights are frozen from actual GitHub Actions artifacts (see manifest).
The benchmark already informed both searches; results are retrospective,
NOT independent proof and never authorize product code, tool execution or release.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
from pathlib import Path
from typing import Any

from benchmarks.agent_utility_v5_catalog import (
    CATALOG_SIZES,
    LANGUAGES,
    TASKS_PER_CELL,
    build_tasks,
)
from scripts.research_actions_width_search_dev import (
    evaluate_genome,
    preload,
    validated_genome,
)
from scripts.research_autoresearch_sandbox import decide
from scripts.research_current_main_multilingual_dev import (
    KS,
    encoded,
    select_cases,
)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "benchmarks/autoresearch-v1-v2-frozen-incumbents.json"
RESEARCH_LIMITS = {
    "uses_previously_exposed_synthetic_DEV": True,
    "retrospective_comparison_of_tuned_candidates": True,
    "uses_new_independent_holdout": False,
    "field_gold": False,
    "host_execution": False,
    "agent_task_success": False,
    "may_auto_promote": False,
    "may_release": False,
}
INPUTS = (
    "benchmarks/autoresearch-v1-v2-frozen-incumbents.json",
    "scripts/research_v1_v2_paired_cpu_dev.py",
    "research/autoresearch/actions_ranker.py",
    "scripts/research_actions_width_search_dev.py",
    "scripts/research_autoresearch_sandbox.py",
    "scripts/research_current_main_multilingual_dev.py",
    "benchmarks/agent_utility_v5_catalog.py",
    "src/schemarouter/planner.py",
)


def frozen_genomes() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    source = json.loads(MANIFEST.read_text(encoding="utf-8"))
    if (
        set(source) != {
            "schema_version", "frozen_source", "source_corpus_sha256",
            "v1", "v2", "restrictions",
        }
        or source["schema_version"] != 1
        or source["source_corpus_sha256"] != hashlib.sha256(
            encoded(build_tasks())
        ).hexdigest()
        or source["restrictions"] != {
            "exposed_synthetic_dev": True,
            "independent_confirmation": False,
            "may_promote": False,
            "agent_task_success": False,
        }
    ):
        raise ValueError("unverified champion provenance or changed exposed DEV corpus")
    v1, v2 = source["v1"], source["v2"]
    expected = (
        (v1, 38828196450, 12015752983, "state.json",
         "3a28c3770210820a17ae51351f8b946fd6b44b7303d472cf34bf6c19beee9db9"),
        (v2, 38828191428, 12016545301, "report.json",
         "cd0bfe985aff06474377f6e0e6966b3ab861b492f0795e48638bc121b99fb35d"),
    )
    for obj, run_id, artifact_id, name, digest in expected:
        if (
            obj.get("run_id") != run_id
            or obj.get("artifact_id") != artifact_id
            or obj.get("artifact_file") != name
            or obj.get("content_sha256") != digest
            or not isinstance(obj.get("source_commit"), str)
            or len(obj["source_commit"]) != 40
        ):
            raise ValueError("unexpected or fabricated frozen optimizer artifact")
    if v1.get("epoch") != 12 or v1.get("trials") != 275:
        raise ValueError("V1 snapshot does not match terminal Actions chain")
    if v1["width"] != 24 or v2["width"] != 64:
        raise ValueError("candidate family drift")
    left = validated_genome({"width": v1["width"], "weights": v1["weights"]})
    right = validated_genome({"width": v2["width"], "weights": v2["weights"]})
    return left, right, source


def cohort_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        raise ValueError("empty paired DEV cohort")
    gold_total = sum(row["required_route_count"] for row in rows)
    supported = sum(bool(row["required_route_count"]) for row in rows)
    return {
        "cases": len(rows),
        "supported_cases": supported,
        "required_total": gold_total,
        "found_total": sum(row["found_required_count"] for row in rows),
        "route_recall": (
            sum(row["found_required_count"] for row in rows) / gold_total
            if gold_total else None
        ),
        "full_coverage": (
            sum(row["full_coverage"] for row in rows) / supported
            if supported else None
        ),
        "serialized_candidate_bytes": sum(
            row["candidate_json_bytes"] for row in rows
        ),
    }


def compare_pairs(
    old: list[dict[str, Any]], new: list[dict[str, Any]],
) -> dict[str, Any]:
    if len(old) != len(new) or not old:
        raise ValueError("unpaired incumbent samples")
    keys = ("task_id", "catalog_size", "language", "k", "required_route_count")
    if any(
        tuple(a[key] for key in keys) != tuple(b[key] for key in keys)
        for a, b in zip(old, new, strict=True)
    ):
        raise ValueError("metric comparison did not use identical current requests")
    cells = []
    for size in CATALOG_SIZES:
        for language in LANGUAGES:
            for k in KS:
                x = [
                    row for row in old if row["catalog_size"] == size
                    and row["language"] == language and row["k"] == k
                ]
                y = [
                    row for row in new if row["catalog_size"] == size
                    and row["language"] == language and row["k"] == k
                ]
                a, b = cohort_metrics(x), cohort_metrics(y)
                cells.append({
                    "catalog_size": size, "language": language, "k": k,
                    "v1": a, "v2": b,
                    "found_route_delta": b["found_total"] - a["found_total"],
                    "full_coverage_count_delta": (
                        sum(row["full_coverage"] for row in y)
                        - sum(row["full_coverage"] for row in x)
                    ),
                    "candidate_bytes_ratio": (
                        b["serialized_candidate_bytes"] / a["serialized_candidate_bytes"]
                        if a["serialized_candidate_bytes"] else None
                    ),
                })
    return {
        "cohorts": cells,
        "any_language_size_k_regression": any(
            row["found_route_delta"] < 0
            or row["full_coverage_count_delta"] < 0
            for row in cells
        ),
        "v1_top5": cohort_metrics([row for row in old if row["k"] == 5]),
        "v2_top5": cohort_metrics([row for row in new if row["k"] == 5]),
        "case_disagreements_top5": [
            {
                "id": before["task_id"], "catalog_size": before["catalog_size"],
                "language": before["language"],
                "required": before["required_route_count"],
                "v1_missing": before["missing_required_route_ids"],
                "v2_missing": after["missing_required_route_ids"],
                "v1_selected_ids": before["selected_route_ids"],
                "v2_selected_ids": after["selected_route_ids"],
            }
            for before, after in zip(old, new, strict=True)
            if before["k"] == 5
            and (
                before["found_required_count"] != after["found_required_count"]
                or before["full_coverage"] != after["full_coverage"]
            )
        ],
    }


def assess(*, cases_per_group: int = TASKS_PER_CELL) -> dict[str, Any]:
    if (
        type(cases_per_group) is not int
        or not 1 <= cases_per_group <= TASKS_PER_CELL
    ):
        raise ValueError("only preregistered 1..5 exposed DEV cases allowed")
    v1, v2, sources = frozen_genomes()
    tasks = select_cases(build_tasks(), cases_per_group=cases_per_group)
    cached = preload(tasks)
    before, v1_rank_p95, v1_total_p95 = evaluate_genome(cached, v1)
    after, v2_rank_p95, v2_total_p95 = evaluate_genome(cached, v2)
    result = compare_pairs(before, after)
    guard = decide(before, after, candidate_p95_ms=v2_rank_p95)
    # This is a *relative research finding*; even a pass is NOT promotion.
    # A case can regress while being masked by aggregate gains; report it.
    scoped_gate = (
        guard["decision"] == "KEEP_RESEARCH_CANDIDATE"
        and v2_total_p95 <= 150
        and v2_total_p95 <= v1_total_p95 * 1.50
        and not result["any_language_size_k_regression"]
    )
    if any(not math.isfinite(x) or x < 0 for x in (
        v1_rank_p95, v1_total_p95, v2_rank_p95, v2_total_p95
    )):
        raise ValueError("invalid paired runtime samples")
    identity = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in INPUTS
    }
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    return {
        "schema_version": 1, "id": "frozen_V1_V2_exact_current_CPU_paired_DEV",
        "source_commit": commit,
        "source_manifest_sha256": identity,
        "data_sha256": sources["source_corpus_sha256"],
        "scope": RESEARCH_LIMITS.copy(),
        "frozen_sources": sources,
        "catalog_sizes": list(CATALOG_SIZES),
        "ks": list(KS),
        "cases_per_language_stratum": cases_per_group,
        "paired_real_planner_calls": (
            len(tasks) * len(CATALOG_SIZES) * 3
        ),
        "evaluated_requests_per_candidate": len(cached),
        "incumbent_v1": {
            "width": v1["width"], "rank_p95_ms": round(v1_rank_p95, 5),
            "retrieval_plus_rank_p95_ms": round(v1_total_p95, 5),
        },
        "challenger_v2": {
            "width": v2["width"], "rank_p95_ms": round(v2_rank_p95, 5),
            "retrieval_plus_rank_p95_ms": round(v2_total_p95, 5),
        },
        "paired_results": result,
        "existing_strict_dev_guard": guard,
        "retrospective_DEV_no_regression": scoped_gate,
        "is_external_independent_confirmation": False,
        "is_eligible_for_product_promotion": False,
        "compute": {
            "python": platform.python_version(),
            "platform": platform.platform(),
            "cpu_count": os.cpu_count(),
            "run_id": os.environ.get("GITHUB_RUN_ID"),
        },
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases-per-group", type=int, default=5)
    ap.add_argument("--output", required=True, type=Path)
    args = ap.parse_args()
    report = assess(cases_per_group=args.cases_per_group)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    paired = report["paired_results"]
    print(json.dumps({
        "status": "PAIRED_EXPOSED_DEV_NOT_RELEASE",
        "cases": report["evaluated_requests_per_candidate"],
        "v1_top5": paired["v1_top5"]["route_recall"],
        "v2_top5": paired["v2_top5"]["route_recall"],
        "top5_found_delta": (
            paired["v2_top5"]["found_total"]
            - paired["v1_top5"]["found_total"]
        ),
        "any_regression": paired["any_language_size_k_regression"],
        "relative_dev_gate": report["retrospective_DEV_no_regression"],
        "independent": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

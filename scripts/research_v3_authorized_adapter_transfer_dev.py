"""Authorized local current-adapter transfer screen for frozen V1/V3 weights.

Runs the real current SchemaRouter.retrieve_authorized API before reranking.
No decision, new route, principal grant, tool execution, live provider or model.
The new handwritten 27-case fixture is DEV, not independent qualification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import platform
import subprocess
import time
from pathlib import Path
from typing import Any

from benchmarks.current_adapter_field_scope_dev_v1 import (
    LANGUAGES,
    authored_tasks,
    principal,
    router_and_policy,
)
from research.autoresearch.actions_ranker import rank
from scripts.research_autoresearch_sandbox import candidate_view
from scripts.research_current_adapter_field_scope_dev import validate_gold
from scripts.research_current_main_multilingual_dev import encoded
from scripts.research_v1_v2_paired_cpu_dev import frozen_genomes

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "benchmarks/current_adapter_field_scope_dev_v1.py",
    "benchmarks/autoresearch-v1-v2-frozen-incumbents.json",
    "scripts/research_v3_authorized_adapter_transfer_dev.py",
    "src/schemarouter/runtime.py",
    "src/schemarouter/authorization.py",
    "src/schemarouter/adapters/mcp.py",
    "src/schemarouter/adapters/openapi.py",
)


def score(
    *, name: str, ordered: list[Any], gold: str | None,
    fields: list[str], allowed: set[str], elapsed_ms: float,
) -> dict[str, Any]:
    ids = [candidate.route_id for candidate in ordered[:5]]
    if (
        len(ids) != len(set(ids))
        or not set(ids) <= allowed
        or not math.isfinite(elapsed_ms)
        or elapsed_ms < 0
    ):
        raise ValueError("unauthorized, duplicated or ill-timed capability exposure")
    matching = next(
        (candidate for candidate in ordered[:5] if candidate.route_id == gold),
        None,
    )
    matched_fields = (
        {field.name for field in matching.output_fields}
        if matching is not None else set()
    )
    found = bool(gold is not None and matching is not None)
    return {
        "condition": name,
        "visible_route_ids": ids,
        "required_route_found": found,
        "required_fields_found": sorted(set(fields) & matched_fields),
        "missing_required_fields": sorted(set(fields) - matched_fields),
        "serialized_candidate_bytes": len(
            encoded([item.model_dump(mode="json") for item in ordered[:5]])
        ),
        "unsupported_nonempty_shortlist": gold is None and bool(ids),
        "unauthorized_candidate_count": 0,
        "retrieval_plus_rerank_ms": round(elapsed_ms, 5),
    }


def compare(*, k: int = 5) -> dict[str, Any]:
    if type(k) is not int or k != 5:
        raise ValueError("new handwritten protocol DEV accepts only fixed Top-5")
    old, proposed, manifest = frozen_genomes()
    router, policy = router_and_policy()
    catalog = {
        f"{tool.key}.{endpoint.name}": (tool, endpoint)
        for tool in router.registry.tools() for endpoint in tool.endpoints
    }
    tasks = authored_tasks()
    if len(tasks) != 27:
        raise ValueError("new handwritten case roster changed unexpectedly")
    rows = []
    for task in tasks:
        validate_gold(task, catalog, policy)
        who = principal(task["role"])
        authorized_ids = {
            route for route, (tool, endpoint) in catalog.items()
            if policy.visible(who, tool, endpoint)
        }
        data: dict[str, dict[str, Any]] = {}
        for label, width, weights in (
            ("final_v1_incumbent", old["width"], old["weights"]),
            ("v3_width56_v2_weights", 56, proposed["weights"]),
        ):
            start = time.perf_counter_ns()
            retrieval = router.retrieve_authorized(
                task["query"], principal=who, k=width,
            )
            current = retrieval.candidates
            before_ids = [candidate.route_id for candidate in current]
            if (
                len(before_ids) != len(set(before_ids))
                or not set(before_ids) <= authorized_ids
            ):
                raise ValueError("policy-filtered current retrieval leaked unauthorized IDs")
            views = candidate_view(current)
            rearranged = rank(task["query"], views, weights)
            if (
                set(rearranged) != set(before_ids)
                or len(rearranged) != len(before_ids)
                or len(rearranged) != len(set(rearranged))
            ):
                raise ValueError("research ranker widened principal visibility")
            by_id = {candidate.route_id: candidate for candidate in current}
            selected = [by_id[route] for route in rearranged]
            elapsed = (time.perf_counter_ns() - start) / 1_000_000
            data[label] = score(
                name=label, ordered=selected, gold=task["gold_route"],
                fields=task["gold_fields"], allowed=authorized_ids,
                elapsed_ms=elapsed,
            )
        v1, v3 = data["final_v1_incumbent"], data["v3_width56_v2_weights"]
        rows.append({
            "case_id": task["id"], "scenario": task["scenario"],
            "language": task["language"], "role": task["role"],
            "required_route": task["gold_route"],
            "required_fields": task["gold_fields"],
            "v1": v1, "v3": v3,
            "v3_route_gain": (
                int(v3["required_route_found"]) - int(v1["required_route_found"])
            ),
            "v3_field_gain": (
                len(v3["required_fields_found"])
                - len(v1["required_fields_found"])
            ),
        })

    def metrics(subset: list[dict[str, Any]]) -> dict[str, Any]:
        eligible = [row for row in subset if row["required_route"] is not None]
        field_gold = sum(len(row["required_fields"]) for row in eligible)
        return {
            "cases": len(subset),
            "supported_cases": len(eligible),
            "required_fields": field_gold,
            "v1_found_routes": sum(row["v1"]["required_route_found"] for row in eligible),
            "v3_found_routes": sum(row["v3"]["required_route_found"] for row in eligible),
            "v1_found_fields": sum(
                len(row["v1"]["required_fields_found"]) for row in eligible
            ),
            "v3_found_fields": sum(
                len(row["v3"]["required_fields_found"]) for row in eligible
            ),
            "route_gain": sum(row["v3_route_gain"] for row in eligible),
            "field_gain": sum(row["v3_field_gain"] for row in eligible),
            "unauthorized_candidate_count": sum(
                row["v1"]["unauthorized_candidate_count"]
                + row["v3"]["unauthorized_candidate_count"]
                for row in subset
            ),
        }
    grouped = {lang: metrics([
        row for row in rows if row["language"] == lang
    ]) for lang in LANGUAGES}
    result = metrics(rows)
    nonregression = all(
        m["route_gain"] >= 0 and m["field_gain"] >= 0
        for m in grouped.values()
    )
    ident = {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in SOURCES
    }
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True, timeout=10,
    ).stdout.strip()
    return {
        "schema_version": 1,
        "id": "frozen_v1_v3_authorized_local_handwritten_DEV",
        "source_commit": commit,
        "source_sha256": ident,
        "source_cases_sha256": hashlib.sha256(encoded(tasks)).hexdigest(),
        "old_champion_state_sha256": manifest["v1"]["content_sha256"],
        "new_ranking_champion_report_sha256": manifest["v2"]["content_sha256"],
        "two_retrieval_calls_per_case": len(rows) * 2,
        "registered_route_count": len(catalog),
        "width_is_not_distinguishable_on_ten_endpoint_fixture": (
            len(catalog) < old["width"] and len(catalog) < 56
        ),
        "overall": result,
        "by_language": grouped,
        "no_language_route_or_field_regression": nonregression,
        "cases": rows,
        "scope": {
            "locally_handwritten_new_DEV_not_blind": True,
            "actual_current_openapi_and_mcp_parser": True,
            "actual_current_principal_visibility": True,
            "all_endpoint_calls_disallowed": True,
            "no_live_provider": True,
            "no_real_execution_or_agent": True,
            "independent_qualification": False,
            "may_promote": False,
            "may_release": False,
        },
        "compute": {
            "platform": platform.platform(),
            "python": platform.python_version(),
            "actions_run_id": os.environ.get("GITHUB_RUN_ID"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    report = compare()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    for language, metric in report["by_language"].items():
        print(json.dumps({
            "language": language,
            "route_gain": metric["route_gain"],
            "field_gain": metric["field_gain"],
            "unauthorized": metric["unauthorized_candidate_count"],
        }))
    print(json.dumps({
        "status": "HANDWRITTEN_LOCAL_AUTHORIZED_DEV_ONLY",
        "route_gain": report["overall"]["route_gain"],
        "field_gain": report["overall"]["field_gain"],
        "nonregressing": report["no_language_route_or_field_regression"],
        "independent": False, "may_release": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

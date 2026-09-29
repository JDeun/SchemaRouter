"""Evaluate the preregistered #430 adaptive shortlist policies.

Input is a frozen JSONL file with one row per semantic task x catalog size.
This script never generates task content and never calls an LLM.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-adaptive-shortlist-preregistration.json"
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, raw in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw.strip()
        if not line:
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"line {line_number}: row must be an object")
        rows.append(value)
    return rows


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {
            "count": 0,
            "mean": None,
            "median": None,
            "p95": None,
            "min": None,
            "max": None,
        }
    ordered = sorted(values)
    position = 0.95 * (len(ordered) - 1)
    lo = math.floor(position)
    hi = math.ceil(position)
    if lo == hi:
        p95 = ordered[lo]
    else:
        weight = position - lo
        p95 = ordered[lo] * (1.0 - weight) + ordered[hi] * weight
    return {
        "count": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p95": p95,
        "min": min(values),
        "max": max(values),
    }


def _random_any_required_probability(
    catalog_size: int,
    required_count: int,
    k: int,
) -> float:
    if required_count <= 0:
        raise ValueError("BoR is undefined for rows with no required route")
    if catalog_size <= 0:
        raise ValueError("catalog_size must be positive")
    if required_count > catalog_size:
        raise ValueError("required_count cannot exceed catalog_size")
    bounded_k = min(max(k, 0), catalog_size)
    if bounded_k == 0:
        return 0.0
    if catalog_size - required_count < bounded_k:
        return 1.0
    miss = math.comb(
        catalog_size - required_count,
        bounded_k,
    ) / math.comb(catalog_size, bounded_k)
    return 1.0 - miss


def _bits_over_random(
    observed_any_required: float,
    random_any_required: float,
) -> float | None:
    if observed_any_required <= 0.0:
        return None
    if random_any_required <= 0.0:
        return None
    return math.log2(observed_any_required / random_any_required)


def _adaptive_k(
    scores: list[float],
    policy: dict[str, Any],
    evaluated_positions: list[int],
    zero_spread_epsilon: float = 1e-9,
) -> int:
    min_k = int(policy["min_k"])
    max_k = int(policy["max_k"])
    if len(scores) < max_k:
        raise ValueError(
            f"ranking has {len(scores)} scores but policy requires {max_k}"
        )
    if min_k < 1 or min_k >= max_k:
        raise ValueError("adaptive policy requires 1 <= min_k < max_k")

    spread = scores[0] - scores[max_k - 1]
    if spread <= zero_spread_epsilon:
        return max_k

    gaps = {
        position: (
            scores[position - 1] - scores[position]
        ) / spread
        for position in evaluated_positions
        if min_k <= position < max_k
    }
    if not gaps:
        return max_k

    threshold = float(policy["threshold"])
    policy_id = str(policy["id"])
    if policy_id.startswith("REL-GAP-"):
        for position in sorted(gaps):
            if gaps[position] >= threshold:
                return position
        return max_k

    if policy_id.startswith("MAX-GAP-"):
        position, value = max(
            gaps.items(),
            key=lambda item: (item[1], -item[0]),
        )
        return position if value >= threshold else max_k

    raise ValueError(f"unsupported adaptive policy: {policy_id}")


def _fixed_k(policy: dict[str, Any]) -> int:
    return int(policy["k"])


def _validate_rows(
    rows: list[dict[str, Any]],
    prereg: dict[str, Any],
    *,
    strict_surface: bool,
) -> None:
    if not rows:
        raise ValueError("no evaluation rows")

    catalogs = [int(value) for value in prereg["catalogs"]["endpoint_counts"]]
    supported = set(prereg["metric_populations"]["supported_task_strata"])
    unsupported = set(prereg["metric_populations"]["unsupported_task_strata"])
    all_strata = supported | unsupported
    languages = set(prereg["development_surface"]["languages"])
    max_k = max(
        int(policy.get("k", policy.get("max_k", 0)))
        for policy in (
            prereg["candidate_policies"]["controls"]
            + prereg["candidate_policies"]["adaptive"]
        )
    )

    seen_keys: set[tuple[str, int]] = set()
    task_metadata: dict[str, tuple[str, str, str, tuple[str, ...]]] = {}

    for index, row in enumerate(rows):
        task_id = str(row["task_id"])
        query = str(row["query"])
        stratum = str(row["task_stratum"])
        language = str(row["language"])
        catalog_size = int(row["catalog_size"])
        required = tuple(sorted(str(value) for value in row["required_route_ids"]))
        ranking = row["ranking"]
        latency = float(row["retrieval_latency_ms"])

        if not task_id or not query:
            raise ValueError(f"row {index}: empty task_id or query")
        if stratum not in all_strata:
            raise ValueError(f"row {index}: unknown task stratum {stratum}")
        if language not in languages:
            raise ValueError(f"row {index}: unknown language {language}")
        if catalog_size not in catalogs:
            raise ValueError(f"row {index}: unexpected catalog size {catalog_size}")
        if latency < 0 or not math.isfinite(latency):
            raise ValueError(f"row {index}: invalid retrieval latency")
        if stratum in supported and not required:
            raise ValueError(f"row {index}: supported row has no required routes")
        if stratum in unsupported and required:
            raise ValueError(
                f"row {index}: unsupported row must not contain required routes"
            )
        if not isinstance(ranking, list) or len(ranking) < max_k:
            raise ValueError(f"row {index}: ranking must contain Top-{max_k}")

        route_ids: list[str] = []
        scores: list[float] = []
        for rank, candidate in enumerate(ranking[:max_k], start=1):
            route_id = str(candidate["route_id"])
            score = float(candidate["score"])
            if not route_id:
                raise ValueError(f"row {index} rank {rank}: empty route_id")
            if not math.isfinite(score):
                raise ValueError(f"row {index} rank {rank}: non-finite score")
            route_ids.append(route_id)
            scores.append(score)

        prefix_tokens = row.get("prefix_schema_tokens")
        if not isinstance(prefix_tokens, dict):
            raise ValueError(f"row {index}: prefix_schema_tokens must be an object")
        for depth in range(1, max_k + 1):
            value = int(prefix_tokens.get(str(depth), -1))
            if value < 0:
                raise ValueError(
                    f"row {index}: missing/negative prefix_schema_tokens[{depth}]"
                )

        if len(route_ids) != len(set(route_ids)):
            raise ValueError(f"row {index}: duplicate route_id in ranking")
        if any(
            scores[offset] < scores[offset + 1]
            for offset in range(len(scores) - 1)
        ):
            raise ValueError(f"row {index}: ranking scores are not descending")

        key = (task_id, catalog_size)
        if key in seen_keys:
            raise ValueError(f"duplicate task/catalog row: {key}")
        seen_keys.add(key)

        metadata = (query, stratum, language, required)
        prior = task_metadata.setdefault(task_id, metadata)
        if prior != metadata:
            raise ValueError(
                f"task metadata differs across catalogs for {task_id}"
            )

    if not strict_surface:
        return

    expected_tasks = int(
        prereg["development_surface"]["unique_semantic_tasks"]
    )
    expected_rows = expected_tasks * len(catalogs)
    if len(task_metadata) != expected_tasks:
        raise ValueError(
            f"expected {expected_tasks} tasks, found {len(task_metadata)}"
        )
    if len(rows) != expected_rows:
        raise ValueError(f"expected {expected_rows} rows, found {len(rows)}")

    for task_id in task_metadata:
        present = {
            catalog_size
            for current_task, catalog_size in seen_keys
            if current_task == task_id
        }
        if present != set(catalogs):
            raise ValueError(
                f"task {task_id} does not appear in every catalog"
            )

    expected_cell = int(
        prereg["development_surface"]["tasks_per_stratum_language_cell"]
    )
    cell_counts: dict[tuple[str, str], int] = {}
    for _task_id, (_query, stratum, language, _required) in task_metadata.items():
        key = (stratum, language)
        cell_counts[key] = cell_counts.get(key, 0) + 1

    expected_cells = {
        (stratum, language)
        for stratum in all_strata
        for language in languages
    }
    if set(cell_counts) != expected_cells:
        raise ValueError("development surface is missing stratum/language cells")
    wrong_cells = {
        key: count
        for key, count in cell_counts.items()
        if count != expected_cell
    }
    if wrong_cells:
        raise ValueError(f"unbalanced stratum/language cells: {wrong_cells}")


def _evaluate_policy(
    rows: list[dict[str, Any]],
    policy: dict[str, Any],
    prereg: dict[str, Any],
    *,
    adaptive: bool,
) -> dict[str, Any]:
    supported = set(prereg["metric_populations"]["supported_task_strata"])
    evaluated_positions = [
        int(value)
        for value in prereg["score_semantics"]["evaluated_positions"]
    ]

    def new_bucket() -> dict[str, Any]:
        return {
            "required_hits": 0,
            "required_total": 0,
            "supported_full_coverage": 0,
            "supported_any_hit": 0,
            "supported_count": 0,
            "random_any_probabilities": [],
            "candidate_counts": [],
            "schema_tokens": [],
            "retrieval_latencies": [],
        }

    pooled = new_bucket()
    per_catalog_acc: dict[str, dict[str, Any]] = {}
    selected_depths: dict[str, int] = {}
    unsupported_depths: dict[str, list[float]] = {}

    for row in rows:
        ranking = row["ranking"]
        scores = [float(candidate["score"]) for candidate in ranking]
        if adaptive:
            k = _adaptive_k(
                scores,
                policy,
                evaluated_positions,
            )
        else:
            k = _fixed_k(policy)

        selected = ranking[:k]
        selected_routes = {
            str(candidate["route_id"])
            for candidate in selected
        }
        catalog_key = str(int(row["catalog_size"]))
        bucket = per_catalog_acc.setdefault(catalog_key, new_bucket())

        for target in (pooled, bucket):
            target["candidate_counts"].append(float(k))
            target["schema_tokens"].append(
                float(row["prefix_schema_tokens"][str(k)])
            )
            target["retrieval_latencies"].append(
                float(row["retrieval_latency_ms"])
            )

        selected_depths[
            f'{row["task_id"]}@{row["catalog_size"]}'
        ] = k

        stratum = str(row["task_stratum"])
        required = {
            str(route_id)
            for route_id in row["required_route_ids"]
        }
        if stratum in supported:
            hits = len(required & selected_routes)
            random_probability = _random_any_required_probability(
                int(row["catalog_size"]),
                len(required),
                k,
            )
            for target in (pooled, bucket):
                target["required_hits"] += hits
                target["required_total"] += len(required)
                target["supported_full_coverage"] += int(
                    hits == len(required)
                )
                target["supported_any_hit"] += int(hits > 0)
                target["supported_count"] += 1
                target["random_any_probabilities"].append(
                    random_probability
                )
        else:
            unsupported_depths.setdefault(stratum, []).append(float(k))

    def summarize(bucket: dict[str, Any]) -> dict[str, Any]:
        supported_count = int(bucket["supported_count"])
        observed_any = (
            bucket["supported_any_hit"] / supported_count
            if supported_count
            else 0.0
        )
        random_values = bucket["random_any_probabilities"]
        random_any = (
            statistics.fmean(random_values)
            if random_values
            else 0.0
        )
        required_total = int(bucket["required_total"])
        return {
            "supported_required_route_recall": (
                bucket["required_hits"] / required_total
                if required_total
                else None
            ),
            "supported_all_required_full_coverage": (
                bucket["supported_full_coverage"] / supported_count
                if supported_count
                else None
            ),
            "supported_any_required_coverage": observed_any,
            "bits_over_random_any_required": _bits_over_random(
                observed_any,
                random_any,
            ),
            "mean_random_any_required_probability": random_any,
            "candidate_count": _distribution(bucket["candidate_counts"]),
            "schema_tokens": _distribution(bucket["schema_tokens"]),
            "retrieval_latency_ms": _distribution(
                bucket["retrieval_latencies"]
            ),
        }

    pooled_summary = summarize(pooled)
    per_catalog = {
        key: summarize(value)
        for key, value in sorted(
            per_catalog_acc.items(),
            key=lambda item: int(item[0]),
        )
    }
    catalog_recalls = [
        value["supported_required_route_recall"]
        for value in per_catalog.values()
        if value["supported_required_route_recall"] is not None
    ]
    catalog_coverages = [
        value["supported_all_required_full_coverage"]
        for value in per_catalog.values()
        if value["supported_all_required_full_coverage"] is not None
    ]

    return {
        "policy_id": str(policy["id"]),
        "adaptive": adaptive,
        **pooled_summary,
        "per_catalog": per_catalog,
        "worst_catalog_required_route_recall": (
            min(catalog_recalls)
            if catalog_recalls
            else None
        ),
        "worst_catalog_all_required_full_coverage": (
            min(catalog_coverages)
            if catalog_coverages
            else None
        ),
        "unsupported_candidate_count": {
            stratum: _distribution(values)
            for stratum, values in sorted(unsupported_depths.items())
        },
        "selected_depths": selected_depths,
    }


def _adaptive_eligible(
    metrics: dict[str, Any],
    fixed5: dict[str, Any],
    prereg: dict[str, Any],
) -> bool:
    worst_recall = metrics["worst_catalog_required_route_recall"]
    worst_coverage = metrics[
        "worst_catalog_all_required_full_coverage"
    ]
    mean_count = metrics["candidate_count"]["mean"]
    p95_count = metrics["candidate_count"]["p95"]
    mean_tokens = metrics["schema_tokens"]["mean"]
    fixed5_tokens = fixed5["schema_tokens"]["mean"]
    if None in {
        worst_recall,
        worst_coverage,
        mean_count,
        p95_count,
        mean_tokens,
        fixed5_tokens,
    }:
        return False

    gates = prereg["dev_selection"]["eligibility_thresholds"]
    expected_catalogs = {
        str(int(value))
        for value in gates["catalog_sizes"]
    }
    if set(metrics["per_catalog"]) != expected_catalogs:
        return False

    return bool(
        worst_recall >= float(gates["required_tool_set_recall_min"])
        and worst_coverage
        >= float(gates["all_required_full_coverage_min"])
        and mean_count
        < float(gates["mean_candidate_count_max_exclusive"])
        and p95_count <= float(gates["p95_candidate_count_max"])
        and (
            mean_tokens < fixed5_tokens
            if gates["mean_schema_tokens_must_be_less_than_fixed5"]
            else True
        )
    )


def _selection_key(metrics: dict[str, Any]) -> tuple[Any, ...]:
    return (
        float(metrics["candidate_count"]["mean"]),
        -float(metrics["worst_catalog_required_route_recall"]),
        -float(metrics["worst_catalog_all_required_full_coverage"]),
        -float(metrics["supported_required_route_recall"]),
        float(metrics["schema_tokens"]["mean"]),
        float(metrics["retrieval_latency_ms"]["p95"]),
        str(metrics["policy_id"]),
    )


def evaluate(
    rows: list[dict[str, Any]],
    prereg: dict[str, Any],
    *,
    strict_surface: bool = True,
) -> dict[str, Any]:
    _validate_rows(
        rows,
        prereg,
        strict_surface=strict_surface,
    )
    controls = prereg["candidate_policies"]["controls"]
    adaptive = prereg["candidate_policies"]["adaptive"]

    results: dict[str, dict[str, Any]] = {}
    for policy in controls:
        metrics = _evaluate_policy(
            rows,
            policy,
            prereg,
            adaptive=False,
        )
        results[str(policy["id"])] = metrics
    for policy in adaptive:
        metrics = _evaluate_policy(
            rows,
            policy,
            prereg,
            adaptive=True,
        )
        results[str(policy["id"])] = metrics

    fixed5 = results["FIXED-5"]
    eligible_ids: list[str] = []
    for policy in adaptive:
        policy_id = str(policy["id"])
        eligible = _adaptive_eligible(
            results[policy_id],
            fixed5,
            prereg,
        )
        results[policy_id]["dev_eligible"] = eligible
        if eligible:
            eligible_ids.append(policy_id)

    selected = (
        min(
            eligible_ids,
            key=lambda policy_id: _selection_key(results[policy_id]),
        )
        if eligible_ids
        else None
    )
    return {
        "experiment": prereg["experiment"],
        "issue": prereg["issue"],
        "surface": "development",
        "strict_surface_validation": strict_surface,
        "row_count": len(rows),
        "policy_metrics": results,
        "eligible_adaptive_policies": sorted(eligible_ids),
        "selected_adaptive_policy": selected,
        "selection_rule": prereg["dev_selection"]["selection_order"],
        "claim_boundary": (
            "DEV policy selection only; confirmation and downstream agent "
            "claims remain unavailable"
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--prereg", type=Path, default=DEFAULT_PREREG)
    parser.add_argument(
        "--allow-partial-surface",
        action="store_true",
        help="test/debug only; never use for canonical DEV selection",
    )
    args = parser.parse_args()

    prereg = json.loads(args.prereg.read_text(encoding="utf-8"))
    rows = _load_jsonl(args.input)
    result = evaluate(
        rows,
        prereg,
        strict_surface=not args.allow_partial_surface,
    )
    result["input_sha256"] = _sha256(args.input)
    result["preregistration_sha256"] = _sha256(args.prereg)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "input_sha256": result["input_sha256"],
                "selected_adaptive_policy": result[
                    "selected_adaptive_policy"
                ],
                "eligible_adaptive_policies": result[
                    "eligible_adaptive_policies"
                ],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

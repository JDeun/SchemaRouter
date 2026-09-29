"""Evaluate preregistered structural retrieval variants on #430 DEV only."""

from __future__ import annotations

import argparse
import inspect
import json
import math
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_v5_catalog import (  # noqa: E402
    CATALOG_SIZES,
    STRATA,
    build_registry,
    build_tasks,
)
from schemarouter import PlanRequest, SchemaPlanner  # noqa: E402
from schemarouter.planner import _tokens  # noqa: E402

PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-retrieval-preregistration.json"
)
_SIMPLE_IDENTIFIER_RE = re.compile(r"^[A-Za-z0-9_]+$")


def _singularize_identifier(value: str) -> str:
    lowered = value.casefold()
    if not lowered.isalpha():
        return lowered
    if len(lowered) > 4 and lowered.endswith("ies"):
        return lowered[:-3] + "y"
    if (
        len(lowered) > 3
        and lowered.endswith("s")
        and not lowered.endswith("ss")
    ):
        return lowered[:-1]
    return lowered


def _tool_identifier_forms(tool: Any) -> set[str]:
    raw = {str(tool.name), str(tool.key).rsplit(".", 1)[-1]}
    return {
        _singularize_identifier(value)
        for value in raw
        if value and _SIMPLE_IDENTIFIER_RE.fullmatch(value)
    }


def _tool_identifier_match(query_tokens: set[str], tool: Any) -> bool:
    query_forms = {
        _singularize_identifier(token)
        for token in query_tokens
        if token.isascii() and token.isalnum()
    }
    return bool(query_forms & _tool_identifier_forms(tool))


def _common_prefix_length(left: str, right: str) -> int:
    count = 0
    for left_char, right_char in zip(left, right, strict=False):
        if left_char != right_char:
            break
        count += 1
    return count


def _same_operation_family(left: str, right: str) -> bool:
    left = left.casefold()
    right = right.casefold()
    if left == right:
        return True
    if not (
        left.isascii()
        and right.isascii()
        and left.isalpha()
        and right.isalpha()
    ):
        return False
    shorter = min(len(left), len(right))
    if shorter < 4:
        return False
    prefix = _common_prefix_length(left, right)
    return prefix >= 4 and prefix / shorter >= 0.7


def _operation_tokens(endpoint: Any) -> set[str]:
    tokens = set(
        _tokens(
            str(endpoint.name)
            .replace("_", " ")
            .replace("-", " ")
        )
    )
    for alias in endpoint.operation_aliases:
        tokens.update(_tokens(str(alias)))
    return {
        token
        for token in tokens
        if token.isascii() and token.isalpha()
    }


def _operation_family_match(
    query_tokens: set[str],
    endpoint: Any,
) -> bool:
    query_ascii = {
        token
        for token in query_tokens
        if token.isascii() and token.isalpha()
    }
    operations = _operation_tokens(endpoint)
    return any(
        _same_operation_family(query_token, operation)
        for query_token in query_ascii
        for operation in operations
    )


def _schema_terms(tool: Any, endpoint: Any) -> set[str]:
    parts = [
        str(tool.name),
        str(tool.description),
        str(endpoint.name),
        str(endpoint.description),
        *[str(alias) for alias in endpoint.operation_aliases],
    ]
    for field in endpoint.output_fields:
        parts.extend(
            [
                str(field.name),
                str(field.semantic_id or ""),
                *[str(alias) for alias in field.aliases],
                ".".join(field.projection_path),
            ]
        )
    return set(_tokens(" ".join(parts)))


def _specificity_by_route(registry: Any) -> dict[str, float]:
    entries: list[tuple[str, set[str]]] = []
    frequencies: Counter[str] = Counter()

    for tool in registry.tools():
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            terms = _schema_terms(tool, endpoint)
            entries.append((route_id, terms))
            frequencies.update(terms)

    endpoint_count = len(entries)
    if endpoint_count <= 1:
        return {
            route_id: 0.0
            for route_id, _terms in entries
        }

    denominator = math.log(endpoint_count + 1)
    discrimination = {
        term: math.log(
            (endpoint_count + 1) / (frequency + 1)
        )
        / denominator
        for term, frequency in frequencies.items()
    }

    result: dict[str, float] = {}
    for route_id, terms in entries:
        values = [
            discrimination[term]
            for term in terms
            if term in discrimination
        ]
        result[route_id] = (
            sum(values) / len(values)
            if values
            else 0.0
        )
    return result


def _base_candidates(
    planner: SchemaPlanner,
    query: str,
) -> list[Any]:
    request = planner._prepare_request(PlanRequest(query=query))  # noqa: SLF001
    intent = planner.analyzer.analyze(request, planner.registry)
    if inspect.isawaitable(intent):
        raise RuntimeError(
            "structural retrieval DEV requires synchronous analyzer"
        )
    return planner._semantic_recall_catalog(  # noqa: SLF001
        request,
        intent,
    )


def _rank_variant(
    candidates: list[Any],
    *,
    query: str,
    specificity: dict[str, float],
    variant: dict[str, Any],
) -> list[dict[str, Any]]:
    query_tokens = set(_tokens(query))
    tool_bonus = float(variant["tool_identifier_bonus"])
    operation_bonus = float(variant["operation_family_bonus"])
    use_specificity = bool(variant["specificity_tiebreak"])

    scored: list[tuple[float, float, Any]] = []
    for candidate in candidates:
        score = float(candidate.score)
        if tool_bonus and _tool_identifier_match(
            query_tokens,
            candidate.tool,
        ):
            score += tool_bonus
        if operation_bonus and _operation_family_match(
            query_tokens,
            candidate.endpoint,
        ):
            score += operation_bonus

        route_id = (
            f"{candidate.tool.key}.{candidate.endpoint.name}"
        )
        specificity_value = (
            specificity.get(route_id, 0.0)
            if use_specificity
            else 0.0
        )
        scored.append((score, specificity_value, candidate))

    scored.sort(
        key=lambda item: (
            -item[0],
            -item[1],
            item[2].endpoint.server_projection is None,
            item[2].tool.key,
            item[2].endpoint.name,
        )
    )
    return [
        {
            "route_id": (
                f"{candidate.tool.key}.{candidate.endpoint.name}"
            ),
            "score": score,
            "schema_specificity": specificity_value,
        }
        for score, specificity_value, candidate in scored
    ]


def _group_summary(
    rows: list[dict[str, Any]],
) -> dict[str, Any]:
    required_total = sum(
        len(row["required_route_ids"])
        for row in rows
    )
    required_hits = sum(
        sum(
            route_id in set(row["top10_route_ids"])
            for route_id in row["required_route_ids"]
        )
        for row in rows
    )
    full_coverage = sum(
        all(
            route_id in set(row["top10_route_ids"])
            for route_id in row["required_route_ids"]
        )
        for row in rows
    )
    return {
        "task_count": len(rows),
        "required_route_count": required_total,
        "required_route_recall_at_10": (
            required_hits / required_total
            if required_total
            else None
        ),
        "all_required_full_coverage_at_10": (
            full_coverage / len(rows)
            if rows
            else None
        ),
    }


def evaluate() -> dict[str, Any]:
    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    tasks = [
        task
        for task in build_tasks()
        if task["required_route_ids"]
    ]
    variants = list(prereg["variants"])

    rows_by_variant: dict[str, list[dict[str, Any]]] = {
        str(variant["id"]): []
        for variant in variants
    }

    for catalog_size in CATALOG_SIZES:
        registry = build_registry(catalog_size)
        planner = SchemaPlanner(
            registry,
            candidate_index=False,
        )
        specificity = _specificity_by_route(registry)

        for task in tasks:
            query = str(task["query"])
            base_candidates = _base_candidates(planner, query)

            for variant in variants:
                variant_id = str(variant["id"])
                ranking = _rank_variant(
                    base_candidates,
                    query=query,
                    specificity=specificity,
                    variant=variant,
                )
                top10 = [
                    str(item["route_id"])
                    for item in ranking[:10]
                ]
                positions = {
                    str(item["route_id"]): index
                    for index, item in enumerate(
                        ranking,
                        start=1,
                    )
                }
                rows_by_variant[variant_id].append(
                    {
                        "task_id": str(task["task_id"]),
                        "task_stratum": str(
                            task["task_stratum"]
                        ),
                        "language": str(task["language"]),
                        "catalog_size": catalog_size,
                        "required_route_ids": [
                            str(route_id)
                            for route_id in task[
                                "required_route_ids"
                            ]
                        ],
                        "top10_route_ids": top10,
                        "required_route_ranks": {
                            str(route_id): positions.get(
                                str(route_id)
                            )
                            for route_id in task[
                                "required_route_ids"
                            ]
                        },
                    }
                )

    metrics: dict[str, Any] = {}
    baseline_rows = rows_by_variant["BASELINE"]
    baseline_rank_map = {
        (
            row["task_id"],
            row["catalog_size"],
            route_id,
        ): rank
        for row in baseline_rows
        for route_id, rank in row[
            "required_route_ranks"
        ].items()
    }

    for variant in variants:
        variant_id = str(variant["id"])
        rows = rows_by_variant[variant_id]
        per_catalog: dict[str, Any] = {}
        per_stratum: dict[str, Any] = {}
        per_language: dict[str, Any] = {}

        for catalog_size in CATALOG_SIZES:
            subset = [
                row
                for row in rows
                if row["catalog_size"] == catalog_size
            ]
            per_catalog[str(catalog_size)] = _group_summary(
                subset
            )

        for stratum in STRATA:
            subset = [
                row
                for row in rows
                if row["task_stratum"] == stratum
            ]
            if subset:
                per_stratum[stratum] = _group_summary(subset)

        for language in sorted(
            {str(row["language"]) for row in rows}
        ):
            subset = [
                row
                for row in rows
                if row["language"] == language
            ]
            per_language[language] = _group_summary(subset)

        recovered = 0
        lost = 0
        rank_deltas: list[int] = []
        for row in rows:
            for route_id, rank in row[
                "required_route_ranks"
            ].items():
                key = (
                    row["task_id"],
                    row["catalog_size"],
                    route_id,
                )
                baseline_rank = baseline_rank_map[key]
                baseline_top10 = (
                    baseline_rank is not None
                    and baseline_rank <= 10
                )
                current_top10 = (
                    rank is not None and rank <= 10
                )
                recovered += int(
                    current_top10 and not baseline_top10
                )
                lost += int(
                    baseline_top10 and not current_top10
                )
                if (
                    baseline_rank is not None
                    and rank is not None
                ):
                    rank_deltas.append(
                        int(baseline_rank) - int(rank)
                    )

        worst_recall = min(
            float(summary[
                "required_route_recall_at_10"
            ])
            for summary in per_catalog.values()
        )
        worst_full = min(
            float(summary[
                "all_required_full_coverage_at_10"
            ])
            for summary in per_catalog.values()
        )
        typed = per_stratum[
            "typed_numeric_units"
        ]["required_route_recall_at_10"]
        baseline_catalog = {
            key: _group_summary(
                [
                    row
                    for row in baseline_rows
                    if str(row["catalog_size"]) == key
                ]
            )
            for key in per_catalog
        }
        no_catalog_regression = all(
            float(per_catalog[key][
                "required_route_recall_at_10"
            ])
            >= float(baseline_catalog[key][
                "required_route_recall_at_10"
            ])
            for key in per_catalog
        )

        gates = prereg["eligibility"]
        eligible = bool(
            worst_recall
            >= float(
                gates[
                    "each_catalog_required_route_recall_at_10_min"
                ]
            )
            and worst_full
            >= float(
                gates[
                    "each_catalog_all_required_full_coverage_at_10_min"
                ]
            )
            and float(typed)
            >= float(
                gates[
                    "typed_numeric_units_required_route_recall_at_10_min"
                ]
            )
            and (
                no_catalog_regression
                if gates[
                    "no_catalog_recall_regression_vs_baseline"
                ]
                else True
            )
        )

        metrics[variant_id] = {
            "tool_identifier_bonus": float(
                variant["tool_identifier_bonus"]
            ),
            "operation_family_bonus": float(
                variant["operation_family_bonus"]
            ),
            "specificity_tiebreak": bool(
                variant["specificity_tiebreak"]
            ),
            "eligible": eligible,
            "worst_catalog_required_route_recall_at_10": (
                worst_recall
            ),
            "worst_catalog_all_required_full_coverage_at_10": (
                worst_full
            ),
            "per_catalog": per_catalog,
            "per_stratum": per_stratum,
            "per_language": per_language,
            "newly_recovered_required_routes": recovered,
            "newly_lost_required_routes": lost,
            "mean_required_route_rank_improvement": (
                sum(rank_deltas) / len(rank_deltas)
                if rank_deltas
                else None
            ),
        }

    eligible_ids = [
        variant_id
        for variant_id, value in metrics.items()
        if value["eligible"] and variant_id != "BASELINE"
    ]

    def selection_key(variant_id: str) -> tuple[Any, ...]:
        value = metrics[variant_id]
        tool_bonus = float(value["tool_identifier_bonus"])
        operation_bonus = float(
            value["operation_family_bonus"]
        )
        return (
            tool_bonus + operation_bonus,
            max(tool_bonus, operation_bonus),
            -float(
                value[
                    "worst_catalog_required_route_recall_at_10"
                ]
            ),
            -float(
                value[
                    "worst_catalog_all_required_full_coverage_at_10"
                ]
            ),
            variant_id,
        )

    selected = (
        min(eligible_ids, key=selection_key)
        if eligible_ids
        else None
    )

    return {
        "schema_version": 1,
        "issue": 430,
        "experiment": prereg["experiment"],
        "surface": "development",
        "scorer_core_changed": False,
        "confirmation_surface_used": False,
        "b2_outcomes_used": False,
        "variant_metrics": metrics,
        "eligible_variants": sorted(eligible_ids),
        "selected_variant": selected,
        "selection_rule": prereg["dev_selection"],
        "claim_boundary": prereg["claim_boundary"],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "eligible_variants": result[
                    "eligible_variants"
                ],
                "selected_variant": result[
                    "selected_variant"
                ],
                "variant_metrics": {
                    key: {
                        "eligible": value["eligible"],
                        "worst_recall": value[
                            "worst_catalog_required_route_recall_at_10"
                        ],
                        "worst_full_coverage": value[
                            "worst_catalog_all_required_full_coverage_at_10"
                        ],
                        "recovered": value[
                            "newly_recovered_required_routes"
                        ],
                        "lost": value[
                            "newly_lost_required_routes"
                        ],
                    }
                    for key, value in result[
                        "variant_metrics"
                    ].items()
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

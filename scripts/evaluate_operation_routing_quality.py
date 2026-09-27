"""Evaluate operation-routing reports against long-term production targets."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _fraction(numerator: int, denominator: int) -> float | None:
    return numerator / denominator if denominator else None


def _finite(value: object, *, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{label} must be finite")
    return result


def _backend_rows(report: dict[str, Any], backend: str) -> list[dict[str, Any]]:
    rows = [
        row
        for row in report.get("rows", [])
        if isinstance(row, dict) and row.get("backend") == backend
    ]
    if not rows:
        raise ValueError(f"report has no rows for backend {backend!r}")
    return rows


def _slice_accuracy(
    rows: list[dict[str, Any]],
    *,
    key: str,
) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        value = row.get(key)
        if isinstance(value, str) and value:
            grouped[value].append(row)

    result: dict[str, dict[str, Any]] = {}
    for value, group in sorted(grouped.items()):
        supported = [row for row in group if row.get("expected") is not None]
        result[value] = {
            "cases": len(group),
            "supported_cases": len(supported),
            "supported_exact_route_accuracy": _fraction(
                sum(bool(row.get("correct")) for row in supported),
                len(supported),
            ),
        }
    return result


def _route_accuracy(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        expected = row.get("expected")
        if isinstance(expected, str) and expected:
            grouped[expected].append(row)

    return {
        route: {
            "cases": len(group),
            "exact_route_accuracy": _fraction(
                sum(bool(row.get("correct")) for row in group),
                len(group),
            ),
        }
        for route, group in sorted(grouped.items())
    }


def evaluate(
    report: dict[str, Any],
    targets: dict[str, Any],
    *,
    backend: str,
) -> dict[str, Any]:
    rows = _backend_rows(report, backend)
    supported = [row for row in rows if row.get("expected") is not None]
    no_route = [row for row in rows if row.get("expected") is None]
    near_domain = [
        row
        for row in rows
        if row.get("category") == "near_domain_unsupported_operation"
    ]

    exact_accuracy = _fraction(
        sum(bool(row.get("correct")) for row in supported),
        len(supported),
    )
    unsupported_rejection = _fraction(
        sum(row.get("predicted") is None for row in near_domain),
        len(near_domain),
    )
    false_routes = sum(row.get("predicted") is not None for row in no_route)
    false_route_rate = _fraction(false_routes, len(no_route))
    invalid_plan_rate = _fraction(
        sum(bool(row.get("invalid_plan")) for row in rows),
        len(rows),
    )
    execution_errors = sum(row.get("error") is not None for row in rows)

    languages = _slice_accuracy(rows, key="language")
    routes = _route_accuracy(rows)
    language_values = [
        item["supported_exact_route_accuracy"]
        for item in languages.values()
        if item["supported_exact_route_accuracy"] is not None
    ]
    route_values = [
        item["exact_route_accuracy"]
        for item in routes.values()
        if item["exact_route_accuracy"] is not None
    ]

    final_targets = targets.get("final_targets", {})
    exact_target = _finite(
        final_targets["supported_exact_route_accuracy"]["target_min"],
        label="supported exact-route target",
    )
    unsupported_target = _finite(
        final_targets["unsupported_rejection"]["target_range"][0],
        label="unsupported rejection target",
    )
    false_route_target = _finite(
        final_targets["false_route_rate"]["target_max"],
        label="false-route target",
    )
    invalid_target = _finite(
        final_targets["invalid_plan_rate"]["target_max"],
        label="invalid-plan target",
    )

    gates = {
        "supported_exact_route_accuracy": (
            exact_accuracy is not None and exact_accuracy >= exact_target
        ),
        "unsupported_rejection": (
            unsupported_rejection is not None
            and unsupported_rejection >= unsupported_target
        ),
        "false_route_rate": (
            false_route_rate is not None and false_route_rate <= false_route_target
        ),
        "invalid_plan_rate": (
            invalid_plan_rate is not None and invalid_plan_rate <= invalid_target
        ),
        "execution_errors_zero": execution_errors == 0,
    }

    return {
        "backend": backend,
        "cases": len(rows),
        "supported_cases": len(supported),
        "no_route_cases": len(no_route),
        "near_domain_unsupported_cases": len(near_domain),
        "metrics": {
            "supported_exact_route_accuracy": exact_accuracy,
            "unsupported_rejection": unsupported_rejection,
            "false_routes": false_routes,
            "false_route_rate": false_route_rate,
            "invalid_plan_rate": invalid_plan_rate,
            "execution_errors": execution_errors,
            "worst_language_supported_accuracy": (
                min(language_values) if language_values else None
            ),
            "worst_route_accuracy": min(route_values) if route_values else None,
        },
        "gates": gates,
        "production_target_passed": all(gates.values()),
        "language_slices": languages,
        "route_slices": routes,
        "note": (
            "Production targets are standing long-term objectives, not retroactive "
            "promotion gates for preregistered research cycles."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--backend", required=True)
    parser.add_argument(
        "--targets",
        type=Path,
        default=Path("benchmarks/operation-routing-production-targets.json"),
    )
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()

    result = evaluate(
        _load(args.report),
        _load(args.targets),
        backend=args.backend,
    )
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(rendered, encoding="utf-8")
    print(rendered, end="")


if __name__ == "__main__":
    main()

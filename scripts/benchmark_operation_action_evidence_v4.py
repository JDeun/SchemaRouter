from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import math
import statistics
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable

ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "scripts" / "benchmark_decision_routing.py"

SIMILARITY_GRID = (0.20, 0.25, 0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60)
MARGIN_GRID = (0.0, 0.02, 0.05, 0.08, 0.10, 0.15)


def _load_benchmark_module() -> Any:
    spec = importlib.util.spec_from_file_location(
        "benchmark_decision_routing_for_action_evidence",
        BENCHMARK,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load benchmark_decision_routing.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_callable(value: str) -> Callable[[list[str]], Iterable[Iterable[float]]]:
    module_name, separator, attribute = value.partition(":")
    if not separator or not module_name or not attribute:
        raise ValueError("embedding callable must use module:function syntax")
    module = importlib.import_module(module_name)
    target = getattr(module, attribute, None)
    if not callable(target):
        raise TypeError(f"{value!r} does not resolve to a callable")
    return target


def _coerce_vectors(
    raw: Iterable[Iterable[float]],
    *,
    expected_count: int,
) -> list[list[float]]:
    values = [list(map(float, vector)) for vector in raw]
    if len(values) != expected_count:
        raise ValueError(
            f"embedder returned {len(values)} vectors; expected {expected_count}"
        )
    if not values or not values[0]:
        raise ValueError("embedder returned an empty vector")
    dimensions = len(values[0])
    if any(len(vector) != dimensions for vector in values):
        raise ValueError("embedder returned inconsistent vector dimensions")
    if any(
        not math.isfinite(value)
        for vector in values
        for value in vector
    ):
        raise ValueError("embedder returned a non-finite value")
    return values


def _cosine(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        raise ValueError("embedding vector must have non-zero norm")
    value = sum(a * b for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )
    return max(-1.0, min(1.0, value))


def _quantile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return ordered[0]
    position = q * (len(ordered) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    weight = position - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def _distribution(values: list[float]) -> dict[str, float | int | None]:
    return {
        "count": len(values),
        "p05": _quantile(values, 0.05),
        "p10": _quantile(values, 0.10),
        "p25": _quantile(values, 0.25),
        "p50": _quantile(values, 0.50),
        "p75": _quantile(values, 0.75),
        "p90": _quantile(values, 0.90),
        "p95": _quantile(values, 0.95),
    }


def _action_catalog(registry: Any) -> list[tuple[str, str]]:
    catalog: list[tuple[str, str]] = []
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            route = f"{tool.key}.{endpoint.name}"
            operation_name = endpoint.name.replace("_", " ").replace("-", " ")
            parts = [operation_name, *endpoint.operation_aliases]
            action_text = "\n".join(part.strip() for part in parts if part.strip())
            if not action_text:
                raise ValueError(f"empty action text for {route}")
            catalog.append((route, action_text))
    return sorted(catalog)


def _corpus_sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _percentile(values: list[float], q: float) -> float | None:
    value = _quantile(values, q)
    return round(value, 3) if value is not None else None


def _fast_accept_grid(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    points: list[dict[str, Any]] = []
    for similarity in SIMILARITY_GRID:
        for margin in MARGIN_GRID:
            accepted = [
                row
                for row in rows
                if row["top_similarity"] >= similarity
                and row["top_margin"] >= margin
            ]
            correct = sum(
                row["expected"] is not None
                and row["top_route"] == row["expected"]
                for row in accepted
            )
            wrong_supported = sum(
                row["expected"] is not None
                and row["top_route"] != row["expected"]
                for row in accepted
            )
            false_route = sum(row["expected"] is None for row in accepted)
            points.append(
                {
                    "min_similarity": similarity,
                    "min_margin": margin,
                    "accepted": len(accepted),
                    "coverage": len(accepted) / len(rows),
                    "correct_supported": correct,
                    "wrong_supported": wrong_supported,
                    "false_routes": false_route,
                    "precision": (
                        correct / len(accepted)
                        if accepted
                        else None
                    ),
                }
            )
    return sorted(
        points,
        key=lambda item: (
            -(item["precision"] if item["precision"] is not None else -1.0),
            -item["coverage"],
        ),
    )


def analyze(
    *,
    corpus_path: str,
    embedder: Callable[[list[str]], Iterable[Iterable[float]]],
    warmup_cases: int = 24,
    hardware_label: str | None = None,
) -> dict[str, Any]:
    benchmark = _load_benchmark_module()
    registry = benchmark.reference_registry()
    allowed_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }
    cases = benchmark.load_corpus(corpus_path, allowed_routes=allowed_routes)
    catalog = _action_catalog(registry)
    route_ids = [route for route, _text in catalog]
    action_texts = [text for _route, text in catalog]

    option_vectors = _coerce_vectors(
        embedder(action_texts),
        expected_count=len(action_texts),
    )

    for case in cases[: min(warmup_cases, len(cases))]:
        _coerce_vectors(embedder([case.query]), expected_count=1)

    rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    for case in cases:
        started = time.perf_counter()
        query_vector = _coerce_vectors(
            embedder([case.query]),
            expected_count=1,
        )[0]
        similarities = [
            _cosine(query_vector, option_vector)
            for option_vector in option_vectors
        ]
        latency_ms = (time.perf_counter() - started) * 1000
        latencies.append(latency_ms)

        ranked = sorted(
            enumerate(similarities),
            key=lambda item: (-item[1], item[0]),
        )
        top_index, top_similarity = ranked[0]
        second_similarity = ranked[1][1] if len(ranked) > 1 else top_similarity
        top_route = route_ids[top_index]
        route_similarities = {
            route_ids[index]: similarity
            for index, similarity in enumerate(similarities)
        }
        rows.append(
            {
                "case_id": case.id,
                "query": case.query,
                "category": case.category,
                "language": case.language,
                "unsupported_family": case.unsupported_family,
                "expected": case.expected,
                "top_route": top_route,
                "top_similarity": top_similarity,
                "second_similarity": second_similarity,
                "top_margin": top_similarity - second_similarity,
                "expected_similarity": (
                    route_similarities[case.expected]
                    if case.expected is not None
                    else None
                ),
                "route_similarities": route_similarities,
                "latency_ms": latency_ms,
            }
        )

    supported = [row for row in rows if row["expected"] is not None]
    near = [
        row
        for row in rows
        if row["category"] == "near_domain_unsupported_operation"
    ]
    ood = [row for row in rows if row["category"] == "out_of_domain"]
    supported_correct = [
        row for row in supported if row["top_route"] == row["expected"]
    ]

    by_language: dict[str, dict[str, Any]] = {}
    for language in sorted({row["language"] for row in supported}):
        group = [row for row in supported if row["language"] == language]
        correct = sum(row["top_route"] == row["expected"] for row in group)
        by_language[language] = {
            "cases": len(group),
            "correct": correct,
            "raw_top_exact_rate": correct / len(group),
        }

    by_route: dict[str, dict[str, Any]] = {}
    for route in sorted({row["expected"] for row in supported}):
        group = [row for row in supported if row["expected"] == route]
        correct = sum(row["top_route"] == route for row in group)
        by_route[route] = {
            "cases": len(group),
            "correct": correct,
            "raw_top_exact_rate": correct / len(group),
            "expected_similarity": _distribution(
                [float(row["expected_similarity"]) for row in group]
            ),
        }

    false_family_top = defaultdict(int)
    for row in near:
        false_family_top[str(row["unsupported_family"])] += 1

    return {
        "schema_version": 1,
        "corpus": corpus_path,
        "corpus_sha256": _corpus_sha256(corpus_path),
        "hardware_label": hardware_label,
        "model_surface": {
            "option_count": len(catalog),
            "action_text_policy": "endpoint name + trusted operation_aliases only",
            "routes": [
                {"route": route, "action_text": text}
                for route, text in catalog
            ],
        },
        "cases": len(rows),
        "supported_cases": len(supported),
        "near_domain_unsupported_cases": len(near),
        "out_of_domain_cases": len(ood),
        "supported_raw_top_correct": len(supported_correct),
        "supported_raw_top_exact_rate": len(supported_correct) / len(supported),
        "score_geometry": {
            "supported_expected_similarity": _distribution(
                [float(row["expected_similarity"]) for row in supported]
            ),
            "supported_correct_top_similarity": _distribution(
                [float(row["top_similarity"]) for row in supported_correct]
            ),
            "supported_correct_top_margin": _distribution(
                [float(row["top_margin"]) for row in supported_correct]
            ),
            "near_domain_top_similarity": _distribution(
                [float(row["top_similarity"]) for row in near]
            ),
            "near_domain_top_margin": _distribution(
                [float(row["top_margin"]) for row in near]
            ),
            "out_of_domain_top_similarity": _distribution(
                [float(row["top_similarity"]) for row in ood]
            ),
            "out_of_domain_top_margin": _distribution(
                [float(row["top_margin"]) for row in ood]
            ),
        },
        "supported_by_language": by_language,
        "supported_by_route": by_route,
        "near_domain_family_counts": dict(sorted(false_family_top.items())),
        "fast_accept_grid": _fast_accept_grid(rows),
        "latency": {
            "warmup_cases": warmup_cases,
            "mean_ms": round(statistics.fmean(latencies), 3),
            "p50_ms": _percentile(latencies, 0.50),
            "p95_ms": _percentile(latencies, 0.95),
        },
        "rows": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", required=True)
    parser.add_argument(
        "--embedding-callable",
        default="benchmarks.multilingual_embedder:embed",
    )
    parser.add_argument("--warmup-cases", type=int, default=24)
    parser.add_argument("--hardware-label", default=None)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    if args.warmup_cases < 0:
        parser.error("--warmup-cases must be >= 0")

    result = analyze(
        corpus_path=args.corpus,
        embedder=_load_callable(args.embedding_callable),
        warmup_cases=args.warmup_cases,
        hardware_label=args.hardware_label,
    )
    destination = Path(args.out)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({key: value for key, value in result.items() if key != "rows"}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

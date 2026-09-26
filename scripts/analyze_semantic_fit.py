"""Analyze embedding-similarity signals for semantic capability fit.

Research utility only. It records similarity distributions without granting execution authority
or changing SchemaRouter runtime behavior.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from scripts.benchmark_decision_routing import (  # noqa: E402
    load_callable,
    load_corpus,
    reference_registry,
)


def _cosine(left: list[float], right: list[float]) -> float:
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        raise ValueError("embedding vectors must be non-zero")
    return sum(a * b for a, b in zip(left, right, strict=True)) / (
        left_norm * right_norm
    )


def _option_catalog() -> list[tuple[str, str]]:
    catalog: list[tuple[str, str]] = []
    for tool in reference_registry().tools():
        for endpoint in tool.endpoints:
            fields = [
                field.semantic_id or field.name
                for field in endpoint.output_fields
                if not field.identifier
            ]
            parts = [tool.description.strip(), endpoint.description.strip()]
            if fields:
                parts.append("Fields: " + ", ".join(fields))
            description = "\n".join(part for part in parts if part)
            label = f"{tool.key}.{endpoint.name}"
            text = f"{label}\n{description}" if description else label
            catalog.append((label, text))
    return catalog


def _percentile(values: list[float], q: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1.0 - fraction) + ordered[upper] * fraction


def _group_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, selected in (
        ("routed", [row for row in rows if not row["is_ood"]]),
        ("ood", [row for row in rows if row["is_ood"]]),
    ):
        metrics = {}
        for key in (
            "top_similarity",
            "top1_margin",
            "top2_boundary_margin",
            "top1_mean_margin",
        ):
            values = [float(row[key]) for row in selected]
            metrics[key] = {
                "mean": statistics.fmean(values) if values else None,
                "p10": _percentile(values, 0.10),
                "p50": _percentile(values, 0.50),
                "p90": _percentile(values, 0.90),
            }
        result[name] = {
            "cases": len(selected),
            "top1_route_accuracy": (
                sum(row["top_route"] == row["expected"] for row in selected)
                / len(selected)
                if selected
                else None
            ),
            "metrics": metrics,
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--embedding-callable", required=True)
    parser.add_argument("--split", default=None)
    parser.add_argument("--json-out", type=Path, required=True)
    parser.add_argument("--csv-out", type=Path, default=None)
    args = parser.parse_args()

    registry = reference_registry()
    allowed_routes = {
        f"{tool.key}.{endpoint.name}"
        for tool in registry.tools()
        for endpoint in tool.endpoints
    }
    cases = load_corpus(args.corpus, allowed_routes=allowed_routes)
    if args.split is not None:
        cases = [case for case in cases if case.split == args.split]
    if not cases:
        raise ValueError("no cases selected")

    catalog = _option_catalog()
    embed = load_callable(
        args.embedding_callable,
        option_name="--embedding-callable",
    )
    texts = [case.query for case in cases] + [text for _, text in catalog]
    raw_vectors = embed(texts)
    vectors = [[float(value) for value in vector] for vector in raw_vectors]
    if len(vectors) != len(texts):
        raise ValueError("embedding callable returned the wrong number of vectors")
    query_vectors = vectors[: len(cases)]
    option_vectors = vectors[len(cases) :]

    rows: list[dict[str, Any]] = []
    for case, query_vector in zip(cases, query_vectors, strict=True):
        ranked = sorted(
            (
                (catalog[index][0], _cosine(query_vector, option_vector))
                for index, option_vector in enumerate(option_vectors)
            ),
            key=lambda item: (-item[1], item[0]),
        )
        similarities = [score for _, score in ranked]
        route_to_rank = {
            route: index + 1
            for index, (route, _) in enumerate(ranked)
        }
        top_route, top_similarity = ranked[0]
        second_similarity = ranked[1][1]
        third_similarity = ranked[2][1]
        mean_similarity = statistics.fmean(similarities)
        rows.append(
            {
                "case_id": case.id,
                "split": case.split,
                "language": case.language,
                "category": case.category,
                "expected": case.expected,
                "is_ood": case.expected is None,
                "top_route": top_route,
                "expected_rank": (
                    route_to_rank.get(case.expected)
                    if case.expected is not None
                    else None
                ),
                "top_similarity": top_similarity,
                "second_similarity": second_similarity,
                "third_similarity": third_similarity,
                "top1_margin": top_similarity - second_similarity,
                "top2_boundary_margin": second_similarity - third_similarity,
                "mean_similarity": mean_similarity,
                "top1_mean_margin": top_similarity - mean_similarity,
            }
        )

    payload = {
        "schema_version": 1,
        "corpus": str(args.corpus),
        "split": args.split,
        "embedding_callable": args.embedding_callable,
        "case_count": len(rows),
        "catalog_size": len(catalog),
        "summary": _group_summary(rows),
        "rows": rows,
    }
    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if args.csv_out is not None:
        args.csv_out.parent.mkdir(parents=True, exist_ok=True)
        with args.csv_out.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps(payload["summary"], ensure_ascii=False))


if __name__ == "__main__":
    main()

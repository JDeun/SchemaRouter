"""Evaluate the #434 DEV representation ablation on frozen artifacts.

This evaluator intentionally scores only DESCRIPTION-ONLY, RAW-SPEC, and TYPED-MULTIFIELD.
INTENT-MANUAL and TYPED+INTENT remain blocked until their generator revision, prompt, and
filter policy are separately frozen.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import statistics
import sys
import time
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.agent_utility_v2_catalog import CATALOG_SIZES, K_VALUES  # noqa: E402
from schemarouter import InMemoryRegistry, ToolSpec  # noqa: E402
from schemarouter.validation import (  # noqa: E402
    effective_input_schema,
    effective_output_schema,
)

CONDITIONS = ("DESCRIPTION-ONLY", "RAW-SPEC", "TYPED-MULTIFIELD")
TYPED_FIELDS = (
    "tool_resource_identity",
    "endpoint_operation",
    "description",
    "required_inputs",
    "output_semantic_ids",
    "output_datatypes",
    "units_dimensions",
    "read_write_destructive_policy",
)
RRF_K = 60
_TOKEN_RE = re.compile(
    r"[a-z0-9_./+%-]+|[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]",
    re.IGNORECASE,
)


def _canonical_text(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _tokens(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_RE.findall(text)]


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    position = quantile * (len(ordered) - 1)
    low = math.floor(position)
    high = math.ceil(position)
    if low == high:
        return ordered[low]
    weight = position - low
    return ordered[low] * (1 - weight) + ordered[high] * weight


@dataclass(frozen=True)
class Document:
    route_id: str
    raw: dict[str, Any]
    description_text: str
    raw_spec_text: str
    typed_fields: dict[str, str]


class BM25Index:
    def __init__(self, documents: dict[str, str]) -> None:
        self.route_ids = tuple(sorted(documents))
        self.tokens = {
            route_id: _tokens(documents[route_id])
            for route_id in self.route_ids
        }
        self.term_counts = {
            route_id: Counter(tokens)
            for route_id, tokens in self.tokens.items()
        }
        self.lengths = {
            route_id: len(tokens)
            for route_id, tokens in self.tokens.items()
        }
        self.avgdl = (
            statistics.fmean(self.lengths.values())
            if self.lengths
            else 0.0
        )
        self.df: Counter[str] = Counter()
        self.postings: dict[str, dict[str, int]] = {}
        for route_id, counts in self.term_counts.items():
            self.df.update(counts)
            for term, tf in counts.items():
                self.postings.setdefault(term, {})[route_id] = tf
        self.n = len(self.route_ids)
        self.weight_postings: dict[str, dict[str, float]] = {}
        k1 = 1.5
        b = 0.75
        for term, posting in self.postings.items():
            df = self.df[term]
            idf = math.log(1.0 + (self.n - df + 0.5) / (df + 0.5))
            weights: dict[str, float] = {}
            for route_id, tf in posting.items():
                dl = self.lengths[route_id]
                norm = tf + k1 * (
                    1.0 - b + b * dl / self.avgdl
                    if self.avgdl
                    else 1.0
                )
                weights[route_id] = idf * (tf * (k1 + 1.0)) / norm
            self.weight_postings[term] = weights

    def rank_positive_counts(
        self,
        query_counts: Counter[str],
    ) -> list[tuple[str, float]]:
        if not query_counts or self.n == 0:
            return []

        scores: dict[str, float] = {}
        for term, query_tf in query_counts.items():
            weights = self.weight_postings.get(term)
            if not weights:
                continue
            for route_id, contribution in weights.items():
                scores[route_id] = (
                    scores.get(route_id, 0.0)
                    + query_tf * contribution
                )
        return sorted(
            scores.items(),
            key=lambda row: (-row[1], row[0]),
        )

    def rank_positive(self, query: str) -> list[tuple[str, float]]:
        return self.rank_positive_counts(Counter(_tokens(query)))

    def rank(self, query: str) -> list[tuple[str, float]]:
        positive = self.rank_positive(query)
        seen = {route_id for route_id, _ in positive}
        return [
            *positive,
            *[
                (route_id, 0.0)
                for route_id in self.route_ids
                if route_id not in seen
            ],
        ]

def _datatype_text(schema: dict[str, Any]) -> str:
    if not schema:
        return ""
    values: list[str] = []
    declared = schema.get("type")
    if isinstance(declared, str):
        values.append(declared)
    elif isinstance(declared, list):
        values.extend(str(value) for value in declared)
    for key in ("format", "enum", "const", "oneOf", "anyOf", "allOf"):
        if key in schema:
            values.append(f"{key}={_canonical_text(schema[key])}")
    return " ".join(values)


def _document(tool: ToolSpec, endpoint: Any) -> Document:
    route_id = f"{tool.key}.{endpoint.name}"
    raw_input = effective_input_schema(endpoint)
    raw_output = effective_output_schema(endpoint)

    raw = {
        "route_id": route_id,
        "tool": tool.key,
        "tool_description": tool.description,
        "endpoint": endpoint.name,
        "endpoint_description": endpoint.description,
        "input_schema": raw_input,
        "output_schema": raw_output,
        "parameters": [
            parameter.model_dump(mode="json")
            for parameter in endpoint.parameters
        ],
        "output_fields": [
            field.model_dump(mode="json")
            for field in endpoint.output_fields
        ],
        "read_only": endpoint.read_only,
        "destructive": endpoint.destructive,
        "provider": tool.provider,
        "source_type": tool.source_type,
        "access_mode": tool.access_mode,
    }

    description_text = " ".join(
        value
        for value in (tool.description, endpoint.description)
        if value
    )
    raw_spec_text = " ".join(
        [
            tool.key,
            endpoint.name,
            description_text,
            _canonical_text(raw_input),
            _canonical_text(raw_output),
        ]
    )

    required_inputs = " ".join(
        " ".join(
            [
                parameter.name,
                parameter.description,
                "required" if parameter.required else "optional",
                _canonical_text(parameter.json_schema),
            ]
        )
        for parameter in endpoint.parameters
    )
    semantic_ids = " ".join(
        field.semantic_id or ""
        for field in endpoint.output_fields
    )
    datatype_text = " ".join(
        _datatype_text(field.json_schema)
        for field in endpoint.output_fields
    )
    units = " ".join(
        " ".join(
            value
            for value in (
                field.unit,
                (
                    field.unit_normalization.dimension
                    if field.unit_normalization is not None
                    else None
                ),
                (
                    field.unit_normalization.canonical_unit
                    if field.unit_normalization is not None
                    else None
                ),
            )
            if value
        )
        for field in endpoint.output_fields
    )
    policy = " ".join(
        [
            f"read_only={str(bool(endpoint.read_only)).lower()}",
            f"destructive={str(bool(endpoint.destructive)).lower()}",
        ]
    )
    typed_fields = {
        "tool_resource_identity": " ".join(
            value
            for value in (
                tool.key,
                tool.provider,
                tool.source_type,
                tool.access_mode,
            )
            if value
        ),
        "endpoint_operation": " ".join(
            [endpoint.name, *endpoint.operation_aliases]
        ),
        "description": description_text,
        "required_inputs": required_inputs,
        "output_semantic_ids": semantic_ids,
        "output_datatypes": datatype_text,
        "units_dimensions": units,
        "read_write_destructive_policy": policy,
    }
    return Document(
        route_id=route_id,
        raw=raw,
        description_text=description_text,
        raw_spec_text=raw_spec_text,
        typed_fields=typed_fields,
    )


def _load_registry(path: Path) -> InMemoryRegistry:
    payload = json.loads(path.read_text(encoding="utf-8"))
    registry = InMemoryRegistry()
    registry.update_many(
        [ToolSpec.model_validate(row) for row in payload]
    )
    return registry


def _documents(registry: InMemoryRegistry) -> dict[str, Document]:
    return {
        document.route_id: document
        for tool in registry.tools()
        for endpoint in tool.endpoints
        for document in (_document(tool, endpoint),)
    }


class RepresentationRetriever:
    def __init__(self, documents: dict[str, Document], condition: str) -> None:
        self.documents = documents
        self.condition = condition
        started = time.perf_counter_ns()
        if condition == "DESCRIPTION-ONLY":
            self.indexes = {
                "description": BM25Index(
                    {
                        route_id: document.description_text
                        for route_id, document in documents.items()
                    }
                )
            }
            serialized = {
                route_id: document.description_text
                for route_id, document in documents.items()
            }
        elif condition == "RAW-SPEC":
            self.indexes = {
                "raw_spec": BM25Index(
                    {
                        route_id: document.raw_spec_text
                        for route_id, document in documents.items()
                    }
                )
            }
            serialized = {
                route_id: document.raw_spec_text
                for route_id, document in documents.items()
            }
        elif condition == "TYPED-MULTIFIELD":
            self.indexes = {
                field: BM25Index(
                    {
                        route_id: document.typed_fields[field]
                        for route_id, document in documents.items()
                    }
                )
                for field in TYPED_FIELDS
            }
            serialized = {
                route_id: document.typed_fields
                for route_id, document in documents.items()
            }
        else:
            raise ValueError(f"unsupported condition: {condition}")
        self.route_ids = tuple(sorted(documents))
        self._route_index = {
            route_id: index
            for index, route_id in enumerate(self.route_ids)
        }
        self._typed_index_items = tuple(self.indexes.items())
        self._typed_term_entries: dict[
            str,
            list[tuple[int, int, float]],
        ] = {}
        if condition == "TYPED-MULTIFIELD":
            for position, (_, index) in enumerate(self._typed_index_items):
                for term, weights in index.weight_postings.items():
                    entries = self._typed_term_entries.setdefault(term, [])
                    entries.extend(
                        (
                            position,
                            self._route_index[route_id],
                            contribution,
                        )
                        for route_id, contribution in weights.items()
                    )
        self.build_seconds = (time.perf_counter_ns() - started) / 1_000_000_000
        self.index_bytes = len(_canonical_text(serialized).encode("utf-8"))

    def rank(self, query: str) -> tuple[list[tuple[str, float]], float]:
        started = time.perf_counter_ns()
        if self.condition != "TYPED-MULTIFIELD":
            ranking = next(iter(self.indexes.values())).rank(query)
        else:
            query_counts = Counter(_tokens(query))
            field_scores: list[dict[int, float] | None] = [
                None
                for _ in self._typed_index_items
            ]
            for term, query_tf in query_counts.items():
                for position, route_index, contribution in (
                    self._typed_term_entries.get(term, ())
                ):
                    scores = field_scores[position]
                    if scores is None:
                        scores = {}
                        field_scores[position] = scores
                    scores[route_index] = (
                        scores.get(route_index, 0.0)
                        + query_tf * contribution
                    )

            rrf: dict[int, float] = {}
            for scores in field_scores:
                if not scores:
                    continue
                ranked_indexes = sorted(
                    scores,
                    key=lambda route_index: (
                        -scores[route_index],
                        route_index,
                    ),
                )
                for rank, route_index in enumerate(ranked_indexes, start=1):
                    rrf[route_index] = (
                        rrf.get(route_index, 0.0)
                        + 1.0 / (RRF_K + rank)
                    )
            positive_indexes = sorted(
                rrf,
                key=lambda route_index: (
                    -rrf[route_index],
                    route_index,
                ),
            )
            seen = set(rrf)
            ranking = [
                *[
                    (self.route_ids[route_index], rrf[route_index])
                    for route_index in positive_indexes
                ],
                *[
                    (route_id, 0.0)
                    for route_index, route_id in enumerate(self.route_ids)
                    if route_index not in seen
                ],
            ]
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        return ranking, elapsed_ms


def _reciprocal_rank(ranking: list[str], route: str) -> float:
    try:
        return 1.0 / (ranking.index(route) + 1)
    except ValueError:
        return 0.0


def _ndcg(ranking: list[str], relevant: set[str], k: int) -> float:
    if not relevant:
        return 0.0
    dcg = sum(
        1.0 / math.log2(index + 1)
        for index, route in enumerate(ranking[:k], start=1)
        if route in relevant
    )
    ideal = sum(
        1.0 / math.log2(index + 1)
        for index in range(1, min(k, len(relevant)) + 1)
    )
    return dcg / ideal if ideal else 0.0


def _candidate_context(
    documents: dict[str, Document],
    ranking: list[str],
    k: int,
) -> dict[str, int]:
    payload = [
        documents[route_id].raw
        for route_id in ranking[:k]
    ]
    text = _canonical_text(payload)
    return {
        "characters": len(text),
        "utf8_bytes": len(text.encode("utf-8")),
    }


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    supported = [row for row in rows if row["supported"]]
    required_instances = sum(
        len(row["required_routes"])
        for row in supported
    )
    result: dict[str, Any] = {
        "rows": len(rows),
        "supported_rows": len(supported),
        "unsupported_rows": len(rows) - len(supported),
        "mrr_required_route_instances": (
            statistics.fmean(
                rr
                for row in supported
                for rr in row["reciprocal_ranks"]
            )
            if required_instances
            else 0.0
        ),
        "retrieval_latency_ms": {
            "p50": _percentile([row["latency_ms"] for row in rows], 0.5),
            "p95": _percentile([row["latency_ms"] for row in rows], 0.95),
        },
        "k": {},
    }
    for k in K_VALUES:
        recall_hits = sum(row["k"][str(k)]["hits"] for row in supported)
        full = sum(
            row["k"][str(k)]["full_coverage"]
            for row in supported
        )
        result["k"][str(k)] = {
            "Recall": (
                recall_hits / required_instances
                if required_instances
                else 0.0
            ),
            "FullCoverage": (
                full / len(supported)
                if supported
                else 0.0
            ),
            "nDCG": (
                statistics.fmean(
                    row["k"][str(k)]["ndcg"]
                    for row in supported
                )
                if supported
                else 0.0
            ),
            "TopK_context_characters_mean": statistics.fmean(
                row["k"][str(k)]["context_characters"]
                for row in rows
            ),
            "TopK_context_utf8_bytes_mean": statistics.fmean(
                row["k"][str(k)]["context_utf8_bytes"]
                for row in rows
            ),
        }
    return result


def evaluate(freeze_dir: Path) -> dict[str, Any]:
    manifest = json.loads(
        (freeze_dir / "freeze-manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("surface") != "development":
        raise RuntimeError("representation evaluator accepts only the DEV surface")
    if manifest.get("confirmation_surface_opened") is not False:
        raise RuntimeError("confirmation surface must remain sealed during DEV evaluation")

    task_rows = json.loads(
        (freeze_dir / "dev-tasks.json").read_text(encoding="utf-8")
    )

    result: dict[str, Any] = {
        "schema_version": 1,
        "experiment": "typed-multifield-intent-manual-retrieval-ablation-v1",
        "issue": 434,
        "surface": "development",
        "freeze_manifest": manifest,
        "rrf_k": RRF_K,
        "dev_representation_revision": "r6-integer-route-slots",
        "conditions_scored": list(CONDITIONS),
        "conditions_blocked": {
            "INTENT-MANUAL": (
                "blocked until generator revision, prompt, and filter policy are frozen"
            ),
            "TYPED+INTENT": (
                "blocked until INTENT-MANUAL is frozen"
            ),
        },
        "token_projection": {
            "status": "not_scored_in_dependency_free_dev_evaluator",
            "tokenizer": "Qwen/Qwen3-0.6B",
            "revision": "c1899de289a04d12100db370d81485cdf75e47ca",
        },
        "catalog_sizes": {},
    }

    for size in CATALOG_SIZES:
        catalog_path = freeze_dir / f"catalog-{size}.json"
        registry = _load_registry(catalog_path)
        documents = _documents(registry)
        size_result: dict[str, Any] = {}

        for condition in CONDITIONS:
            retriever = RepresentationRetriever(documents, condition)
            rows: list[dict[str, Any]] = []

            for task in task_rows:
                ranking_pairs, latency_ms = retriever.rank(str(task["query"]))
                ranking = [route_id for route_id, _ in ranking_pairs]
                relevant = set(str(route) for route in task["required_routes"])
                row: dict[str, Any] = {
                    "semantic_task_id": task["semantic_task_id"],
                    "stratum": task["stratum"],
                    "language": task["language"],
                    "query": task["query"],
                    "supported": bool(task["supported"]),
                    "required_routes": sorted(relevant),
                    "latency_ms": latency_ms,
                    "top10": [
                        {"route_id": route_id, "score": score}
                        for route_id, score in ranking_pairs[:10]
                    ],
                    "reciprocal_ranks": [
                        _reciprocal_rank(ranking, route)
                        for route in sorted(relevant)
                    ],
                    "k": {},
                }
                for k in K_VALUES:
                    selected = set(ranking[:k])
                    hits = len(relevant.intersection(selected))
                    context = _candidate_context(documents, ranking, k)
                    row["k"][str(k)] = {
                        "hits": hits,
                        "required_count": len(relevant),
                        "full_coverage": bool(relevant) and hits == len(relevant),
                        "ndcg": _ndcg(ranking, relevant, k),
                        "context_characters": context["characters"],
                        "context_utf8_bytes": context["utf8_bytes"],
                    }
                rows.append(row)

            aggregate = _aggregate(rows)
            by_language = {
                language: _aggregate(
                    [row for row in rows if row["language"] == language]
                )
                for language in sorted({row["language"] for row in rows})
            }
            by_stratum = {
                stratum: _aggregate(
                    [row for row in rows if row["stratum"] == stratum]
                )
                for stratum in sorted({row["stratum"] for row in rows})
            }
            size_result[condition] = {
                "index_build_seconds": retriever.build_seconds,
                "index_bytes": retriever.index_bytes,
                "aggregate": aggregate,
                "by_language": by_language,
                "by_stratum": by_stratum,
                "rows": rows,
            }
        result["catalog_sizes"][str(size)] = size_result

    raw = []
    typed = []
    for size in CATALOG_SIZES:
        raw_metrics = result["catalog_sizes"][str(size)]["RAW-SPEC"]
        typed_metrics = result["catalog_sizes"][str(size)]["TYPED-MULTIFIELD"]
        raw.append(raw_metrics)
        typed.append(typed_metrics)

    raw_recall5 = statistics.fmean(
        row["aggregate"]["k"]["5"]["Recall"]
        for row in raw
    )
    typed_recall5 = statistics.fmean(
        row["aggregate"]["k"]["5"]["Recall"]
        for row in typed
    )
    raw_full5 = statistics.fmean(
        row["aggregate"]["k"]["5"]["FullCoverage"]
        for row in raw
    )
    typed_full5 = statistics.fmean(
        row["aggregate"]["k"]["5"]["FullCoverage"]
        for row in typed
    )
    raw_recall10 = statistics.fmean(
        row["aggregate"]["k"]["10"]["Recall"]
        for row in raw
    )
    typed_recall10 = statistics.fmean(
        row["aggregate"]["k"]["10"]["Recall"]
        for row in typed
    )
    p95_ratios = []
    index_ratios = []
    for raw_metrics, typed_metrics in zip(raw, typed, strict=True):
        raw_p95 = raw_metrics["aggregate"]["retrieval_latency_ms"]["p95"]
        typed_p95 = typed_metrics["aggregate"]["retrieval_latency_ms"]["p95"]
        if raw_p95:
            p95_ratios.append(typed_p95 / raw_p95)
        if raw_metrics["index_bytes"]:
            index_ratios.append(
                typed_metrics["index_bytes"] / raw_metrics["index_bytes"]
            )

    result["dev_gate_descriptive"] = {
        "comparator": "RAW-SPEC under BM25",
        "Recall@5_delta": typed_recall5 - raw_recall5,
        "FullCoverage@5_delta": typed_full5 - raw_full5,
        "Recall@10_delta": typed_recall10 - raw_recall10,
        "retrieval_p95_ratio_max": max(p95_ratios) if p95_ratios else None,
        "index_bytes_ratio_max": max(index_ratios) if index_ratios else None,
        "quality_gain_gate": (
            typed_recall5 - raw_recall5 >= 0.02
            or typed_full5 - raw_full5 >= 0.02
        ),
        "Recall@10_guardrail": typed_recall10 - raw_recall10 >= -0.005,
        "latency_guardrail": (
            bool(p95_ratios) and max(p95_ratios) <= 1.5
        ),
        "index_size_guardrail": (
            bool(index_ratios) and max(index_ratios) <= 3.0
        ),
        "confirmation_claim_allowed": False,
        "note": (
            "DEV is tuning-eligible and descriptive only. Confirmation remains sealed."
        ),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate(args.freeze_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "dev_gate_descriptive": result["dev_gate_descriptive"],
                "catalog_sizes": {
                    size: {
                        condition: metrics["aggregate"]["k"]
                        for condition, metrics in conditions.items()
                    }
                    for size, conditions in result["catalog_sizes"].items()
                },
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

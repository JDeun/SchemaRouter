"""Evaluate frozen V6F Tool-Embed positive retrieval on DEV only."""

from __future__ import annotations

import argparse
import gc
import json
import math
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from benchmarks.operation_routing_v6f_catalog import development_registry  # noqa: E402
from benchmarks.schema_adb_baseline import (  # noqa: E402
    ACTION_WEIGHT,
    SCHEMA_WEIGHT,
    _action_text,
    _cosine,
    _schema_text,
    _to_vectors,
)
from benchmarks.schema_adb_baseline import BGE_MODEL, BGE_REVISION  # noqa: E402
from benchmarks.tool_specialized_retriever import (  # noqa: E402
    ToolSpecializedRouteRetriever,
)

TOOL_EMBED_MODEL = "Lux1997/Tool-Embed-0.6B"
TOOL_EMBED_REVISION = "103d16d3593dec6c6f2217be620febb846932f6a"
TOOL_EMBED_INSTRUCTION = (
    "Given a web search query, retrieve relevant passages that answer the query"
)
MAX_LENGTH = 512


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
        "min": min(values) if values else None,
        "p50": _quantile(values, 0.50),
        "p90": _quantile(values, 0.90),
        "p95": _quantile(values, 0.95),
        "max": max(values) if values else None,
        "mean": statistics.fmean(values) if values else None,
    }


def _tool_key(route_id: str) -> str:
    return route_id.split(".", 1)[0]


class ToolEmbedEncoder:
    def __init__(self) -> None:
        import torch
        from transformers import AutoModel, AutoTokenizer

        self.torch = torch
        self.tokenizer = AutoTokenizer.from_pretrained(
            TOOL_EMBED_MODEL,
            revision=TOOL_EMBED_REVISION,
            padding_side="left",
            trust_remote_code=False,
        )
        self.model = AutoModel.from_pretrained(
            TOOL_EMBED_MODEL,
            revision=TOOL_EMBED_REVISION,
            torch_dtype=torch.float32,
            trust_remote_code=False,
        )
        self.model.to("cpu")
        self.model.eval()
        self.max_seen_tokens = 0

    @staticmethod
    def _query_text(text: str) -> str:
        return (
            f"Instruct: {TOOL_EMBED_INSTRUCTION}\n"
            f"Query:{text}"
        )

    def _last_token_pool(self, hidden: Any, attention_mask: Any) -> Any:
        torch = self.torch
        left_padding = (
            attention_mask[:, -1].sum() == attention_mask.shape[0]
        )
        if bool(left_padding):
            return hidden[:, -1]
        sequence_lengths = attention_mask.sum(dim=1) - 1
        batch_size = hidden.shape[0]
        return hidden[
            torch.arange(batch_size, device=hidden.device),
            sequence_lengths,
        ]

    def __call__(
        self,
        texts: list[str],
        is_query: bool,
    ) -> list[list[float]]:
        torch = self.torch
        prepared = [
            self._query_text(text) if is_query else str(text)
            for text in texts
        ]
        lengths = [
            len(
                self.tokenizer(
                    text,
                    add_special_tokens=True,
                    truncation=False,
                )["input_ids"]
            )
            for text in prepared
        ]
        self.max_seen_tokens = max(self.max_seen_tokens, *lengths)
        if any(length > MAX_LENGTH for length in lengths):
            raise ValueError(
                "V6F input exceeded preregistered 512-token maximum"
            )

        inputs = self.tokenizer(
            prepared,
            return_tensors="pt",
            padding=True,
            truncation=False,
        )
        inputs = {key: value.to("cpu") for key, value in inputs.items()}
        with torch.inference_mode():
            outputs = self.model(**inputs)
            pooled = self._last_token_pool(
                outputs.last_hidden_state,
                inputs["attention_mask"],
            )
            pooled = torch.nn.functional.normalize(pooled, p=2, dim=1)
        return pooled.detach().cpu().tolist()


def _bge_predictions(
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from sentence_transformers import SentenceTransformer

    registry = development_registry()
    route_specs: dict[str, tuple[str, str]] = {}
    for tool in registry.tools():
        for endpoint in tool.endpoints:
            route_id = f"{tool.key}.{endpoint.name}"
            route_specs[route_id] = (
                _schema_text(tool, endpoint),
                _action_text(endpoint),
            )
    route_ids = tuple(sorted(route_specs))

    model = SentenceTransformer(
        BGE_MODEL,
        revision=BGE_REVISION,
        trust_remote_code=False,
    )
    static = _to_vectors(
        model.encode(
            [
                *(route_specs[route][0] for route in route_ids),
                *(route_specs[route][1] for route in route_ids),
            ],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).tolist()
    )
    count = len(route_ids)
    schema_vectors = dict(zip(route_ids, static[:count], strict=True))
    action_vectors = dict(zip(route_ids, static[count:], strict=True))

    query_vectors = _to_vectors(
        model.encode(
            [str(row["query"]) for row in rows],
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        ).tolist()
    )

    predictions: list[dict[str, Any]] = []
    for row, query_vector in zip(rows, query_vectors, strict=True):
        ranking = sorted(
            (
                (
                    SCHEMA_WEIGHT
                    * _cosine(query_vector, schema_vectors[route_id])
                    + ACTION_WEIGHT
                    * _cosine(query_vector, action_vectors[route_id]),
                    route_id,
                )
                for route_id in route_ids
            ),
            key=lambda item: (-item[0], item[1]),
        )
        predictions.append(
            {
                "id": row["id"],
                "predicted": ranking[0][1],
                "top_score": ranking[0][0],
                "top2_margin": ranking[0][0] - ranking[1][0],
            }
        )

    del model
    gc.collect()
    return predictions


def evaluate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows or any(row.get("expected") is None for row in rows):
        raise ValueError("V6F evaluator accepts supported DEV rows only")

    bge_rows = _bge_predictions(rows)
    bge_by_id = {row["id"]: row for row in bge_rows}

    load_started = time.perf_counter_ns()
    encoder = ToolEmbedEncoder()
    model_load_ms = (time.perf_counter_ns() - load_started) / 1_000_000

    registry = development_registry()
    static_started = time.perf_counter_ns()
    retriever = ToolSpecializedRouteRetriever(registry, encoder)
    static_profile_encode_ms = (
        time.perf_counter_ns() - static_started
    ) / 1_000_000

    result_rows: list[dict[str, Any]] = []
    latencies: list[float] = []
    errors = 0

    for case in rows:
        started = time.perf_counter_ns()
        try:
            result = retriever.route(str(case["query"]))
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed_ms)
            result_rows.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "language": case["language"],
                    "expected": case["expected"],
                    "predicted": result["predicted"],
                    "top_score": result["top_score"],
                    "top2_margin": result["top2_margin"],
                    "bge_predicted": bge_by_id[case["id"]]["predicted"],
                    "error": None,
                    "latency_ms": elapsed_ms,
                }
            )
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            latencies.append(elapsed_ms)
            errors += 1
            result_rows.append(
                {
                    "id": case["id"],
                    "query": case["query"],
                    "language": case["language"],
                    "expected": case["expected"],
                    "predicted": None,
                    "top_score": None,
                    "top2_margin": None,
                    "bge_predicted": bge_by_id[case["id"]]["predicted"],
                    "error": f"{type(exc).__name__}: {exc}",
                    "latency_ms": elapsed_ms,
                }
            )

    total = len(result_rows)
    exact = sum(
        row["predicted"] == row["expected"] for row in result_rows
    )
    tool_correct = sum(
        row["predicted"] is not None
        and _tool_key(str(row["predicted"])) == _tool_key(str(row["expected"]))
        for row in result_rows
    )
    bge_exact = sum(
        row["bge_predicted"] == row["expected"] for row in result_rows
    )
    bge_tool = sum(
        _tool_key(str(row["bge_predicted"])) == _tool_key(str(row["expected"]))
        for row in result_rows
    )
    disagreements = sum(
        row["predicted"] != row["bge_predicted"] for row in result_rows
    )
    tool_embed_correct_bge_wrong = sum(
        row["predicted"] == row["expected"]
        and row["bge_predicted"] != row["expected"]
        for row in result_rows
    )
    bge_correct_tool_embed_wrong = sum(
        row["bge_predicted"] == row["expected"]
        and row["predicted"] != row["expected"]
        for row in result_rows
    )

    per_language: dict[str, dict[str, float | int]] = {}
    for language in sorted({str(row["language"]) for row in result_rows}):
        subset = [row for row in result_rows if row["language"] == language]
        per_language[language] = {
            "cases": len(subset),
            "tool_embed_exact": sum(
                row["predicted"] == row["expected"] for row in subset
            )
            / len(subset),
            "bge_exact": sum(
                row["bge_predicted"] == row["expected"] for row in subset
            )
            / len(subset),
        }

    per_tool: dict[str, dict[str, float | int]] = {}
    for tool in sorted({_tool_key(str(row["expected"])) for row in result_rows}):
        subset = [
            row
            for row in result_rows
            if _tool_key(str(row["expected"])) == tool
        ]
        per_tool[tool] = {
            "cases": len(subset),
            "tool_embed_exact": sum(
                row["predicted"] == row["expected"] for row in subset
            )
            / len(subset),
            "bge_exact": sum(
                row["bge_predicted"] == row["expected"] for row in subset
            )
            / len(subset),
        }

    scores = [
        float(row["top_score"])
        for row in result_rows
        if row["top_score"] is not None
    ]
    margins = [
        float(row["top2_margin"])
        for row in result_rows
        if row["top2_margin"] is not None
    ]
    latency = _distribution(latencies)
    p95 = latency["p95"]

    metrics: dict[str, Any] = {
        "tool_embed_supported_exact_route_accuracy": exact / total,
        "tool_embed_supported_tool_accuracy": tool_correct / total,
        "bge_supported_exact_route_accuracy": bge_exact / total,
        "bge_supported_tool_accuracy": bge_tool / total,
        "route_disagreements": disagreements,
        "tool_embed_correct_bge_wrong": tool_embed_correct_bge_wrong,
        "bge_correct_tool_embed_wrong": bge_correct_tool_embed_wrong,
        "top_score": _distribution(scores),
        "top2_margin": _distribution(margins),
        "query_latency_ms": latency,
        "model_load_ms": model_load_ms,
        "static_profile_encode_ms": static_profile_encode_ms,
        "max_seen_tokens": encoder.max_seen_tokens,
        "execution_errors": errors,
        "per_language": per_language,
        "per_tool": per_tool,
    }

    quality_gates = {
        "supported_exact_route_accuracy": (
            metrics["tool_embed_supported_exact_route_accuracy"] >= 0.85
        ),
        "matches_or_exceeds_same_surface_bge": (
            metrics["tool_embed_supported_exact_route_accuracy"]
            >= metrics["bge_supported_exact_route_accuracy"]
        ),
        "execution_errors": errors == 0,
    }
    runtime_gate = p95 is not None and float(p95) <= 250.0

    return {
        "experiment": "tool-specialized-pretrained-route-retriever-v1",
        "issue": 406,
        "surface": "V6F-development",
        "models": {
            "tool_embed": {
                "name": TOOL_EMBED_MODEL,
                "revision": TOOL_EMBED_REVISION,
                "dtype": "float32",
                "device": "cpu",
                "max_length": MAX_LENGTH,
                "pooling": "last_token",
            },
            "bge_baseline": {
                "name": BGE_MODEL,
                "revision": BGE_REVISION,
                "schema_weight": SCHEMA_WEIGHT,
                "action_weight": ACTION_WEIGHT,
            },
        },
        "metrics": metrics,
        "quality_gates": quality_gates,
        "runtime_gate": runtime_gate,
        "quality_pass": all(quality_gates.values()),
        "surface_pass": all(quality_gates.values()) and runtime_gate,
        "policy": {
            "confirmation_scored": False,
            "supported_only": True,
            "tool_embed_is_sole_positive_selector": True,
            "bge_is_diagnostic_only": True,
            "bge_fusion": False,
            "reranker": False,
            "abstention": False,
            "rank2_fallback": False,
            "pseudo_route": False,
            "score_threshold": None,
            "margin_threshold": None,
            "schema_only_profile": True,
            "model_generated_expansion": False,
            "limitations_field": False,
            "dev_selected_hyperparameters": False,
        },
        "rows": result_rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--development", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    rows = json.loads(args.development.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or any(
        not isinstance(row, dict) for row in rows
    ):
        raise ValueError("development corpus must be a list of objects")

    result = evaluate(rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "surface": result["surface"],
                "quality_pass": result["quality_pass"],
                "runtime_gate": result["runtime_gate"],
                "surface_pass": result["surface_pass"],
                "metrics": result["metrics"],
                "quality_gates": result["quality_gates"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

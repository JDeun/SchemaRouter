"""Evaluate frozen #434 INTENT-MANUAL and TYPED+INTENT DEV conditions.

The existing representation evaluator remains the canonical source for DESCRIPTION-ONLY,
RAW-SPEC, and TYPED-MULTIFIELD.  This successor adds only the two preregistered intent
conditions using a separately frozen metadata-only generator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.evaluate_agent_utility_v2_representation as base  # noqa: E402
from benchmarks.agent_utility_v2_catalog import CATALOG_SIZES, K_VALUES  # noqa: E402
from schemarouter import ToolSpec  # noqa: E402

AMENDMENT_PATH = (
    ROOT / "benchmarks" / "agent-utility-v2-intent-manual-amendment.json"
)
CONDITIONS = ("INTENT-MANUAL", "TYPED+INTENT")
RRF_K = 60


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manual_texts(
    path: Path,
    tools: list[ToolSpec],
    *,
    expected_catalog_sha256: str,
) -> dict[str, str]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload["generator_revision"] != (
        "deterministic-capability-intent-manual-v1"
    ):
        raise RuntimeError("intent-manual generator revision drifted")
    if payload["source_catalog_sha256"] != expected_catalog_sha256:
        raise RuntimeError("intent-manual source catalog identity drifted")

    expected: dict[str, tuple[str, str]] = {
        f"{tool.key}.{endpoint.name}": (
            tool.fingerprint,
            endpoint.fingerprint,
        )
        for tool in tools
        for endpoint in tool.endpoints
    }
    rows = payload["rows"]
    if len(rows) != len(expected):
        raise RuntimeError("intent-manual endpoint count drifted")

    result: dict[str, str] = {}
    for row in rows:
        route_id = str(row["route_id"])
        if route_id not in expected:
            raise RuntimeError(
                f"intent-manual invented unregistered route: {route_id}"
            )
        tool_fp, endpoint_fp = expected[route_id]
        if row["tool_fingerprint"] != tool_fp:
            raise RuntimeError(f"tool fingerprint drifted for {route_id}")
        if row["endpoint_fingerprint"] != endpoint_fp:
            raise RuntimeError(f"endpoint fingerprint drifted for {route_id}")
        if route_id in result:
            raise RuntimeError(f"duplicate intent-manual route: {route_id}")
        intents = [
            str(intent["text"]).strip()
            for intent in row["intents"]
            if str(intent["text"]).strip()
        ]
        if not intents:
            raise RuntimeError(f"no generated intents for {route_id}")
        result[route_id] = " ".join(intents)

    if set(result) != set(expected):
        raise RuntimeError("intent-manual route coverage drifted")
    return result


class IntentRetriever:
    def __init__(
        self,
        documents: dict[str, base.Document],
        intent_texts: dict[str, str],
        condition: str,
    ) -> None:
        if set(intent_texts) != set(documents):
            raise RuntimeError(
                "intent manual must map one-to-one to registered documents"
            )
        if condition not in CONDITIONS:
            raise ValueError(f"unsupported condition: {condition}")

        self.documents = documents
        self.condition = condition
        self.route_ids = tuple(sorted(documents))
        started = time.perf_counter_ns()
        self.intent_index = base.BM25Index(intent_texts)
        self.typed = (
            base.RepresentationRetriever(documents, "TYPED-MULTIFIELD")
            if condition == "TYPED+INTENT"
            else None
        )
        intent_serialized = base._canonical_text(intent_texts)
        self.index_bytes = len(intent_serialized.encode("utf-8"))
        if self.typed is not None:
            self.index_bytes += self.typed.index_bytes
        self.build_seconds = (
            time.perf_counter_ns() - started
        ) / 1_000_000_000

    @staticmethod
    def _fuse(
        rankings: tuple[list[tuple[str, float]], ...],
    ) -> list[tuple[str, float]]:
        scores: dict[str, float] = {}
        for ranking in rankings:
            positive = [
                (route_id, score)
                for route_id, score in ranking
                if score > 0.0
            ]
            for rank, (route_id, _) in enumerate(positive, start=1):
                scores[route_id] = (
                    scores.get(route_id, 0.0)
                    + 1.0 / (RRF_K + rank)
                )
        positive = sorted(
            scores.items(),
            key=lambda row: (-row[1], row[0]),
        )
        seen = {route_id for route_id, _ in positive}
        route_ids = sorted(
            {
                route_id
                for ranking in rankings
                for route_id, _ in ranking
            }
        )
        return [
            *positive,
            *[
                (route_id, 0.0)
                for route_id in route_ids
                if route_id not in seen
            ],
        ]

    def rank(self, query: str) -> tuple[list[tuple[str, float]], float]:
        started = time.perf_counter_ns()
        manual = self.intent_index.rank(query)
        if self.condition == "INTENT-MANUAL":
            ranking = manual
        else:
            assert self.typed is not None
            typed, _ = self.typed.rank(query)
            ranking = self._fuse((typed, manual))
        elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
        return ranking, elapsed_ms


def _evaluate_condition(
    *,
    documents: dict[str, base.Document],
    task_rows: list[dict[str, Any]],
    retriever: IntentRetriever,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for task in task_rows:
        query = str(task["query"])
        ranking_pairs, _ = retriever.rank(query)
        for _ in range(base.LATENCY_WARMUP):
            retriever.rank(query)
        latency_samples = [
            retriever.rank(query)[1]
            for _ in range(base.LATENCY_REPEATS)
        ]
        latency_ms = statistics.median(latency_samples)
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
                base._reciprocal_rank(ranking, route)
                for route in sorted(relevant)
            ],
            "k": {},
        }
        for k in K_VALUES:
            selected = set(ranking[:k])
            hits = len(relevant.intersection(selected))
            context = base._candidate_context(documents, ranking, k)
            row["k"][str(k)] = {
                "hits": hits,
                "required_count": len(relevant),
                "full_coverage": bool(relevant) and hits == len(relevant),
                "ndcg": base._ndcg(ranking, relevant, k),
                "context_characters": context["characters"],
                "context_utf8_bytes": context["utf8_bytes"],
            }
        rows.append(row)

    aggregate = base._aggregate(rows)
    return {
        "index_build_seconds": retriever.build_seconds,
        "index_bytes": retriever.index_bytes,
        "aggregate": aggregate,
        "by_language": {
            language: base._aggregate(
                [row for row in rows if row["language"] == language]
            )
            for language in sorted({row["language"] for row in rows})
        },
        "by_stratum": {
            stratum: base._aggregate(
                [row for row in rows if row["stratum"] == stratum]
            )
            for stratum in sorted({row["stratum"] for row in rows})
        },
        "rows": rows,
    }


def _gate(
    raw: list[dict[str, Any]],
    candidate: list[dict[str, Any]],
    *,
    name: str,
) -> dict[str, Any]:
    raw_recall5 = statistics.fmean(
        row["aggregate"]["k"]["5"]["Recall"]
        for row in raw
    )
    candidate_recall5 = statistics.fmean(
        row["aggregate"]["k"]["5"]["Recall"]
        for row in candidate
    )
    raw_full5 = statistics.fmean(
        row["aggregate"]["k"]["5"]["FullCoverage"]
        for row in raw
    )
    candidate_full5 = statistics.fmean(
        row["aggregate"]["k"]["5"]["FullCoverage"]
        for row in candidate
    )
    raw_recall10 = statistics.fmean(
        row["aggregate"]["k"]["10"]["Recall"]
        for row in raw
    )
    candidate_recall10 = statistics.fmean(
        row["aggregate"]["k"]["10"]["Recall"]
        for row in candidate
    )

    p95_ratios: list[float] = []
    index_ratios: list[float] = []
    for raw_metrics, candidate_metrics in zip(raw, candidate, strict=True):
        raw_p95 = raw_metrics["aggregate"]["retrieval_latency_ms"]["p95"]
        candidate_p95 = candidate_metrics["aggregate"][
            "retrieval_latency_ms"
        ]["p95"]
        if raw_p95:
            p95_ratios.append(candidate_p95 / raw_p95)
        if raw_metrics["index_bytes"]:
            index_ratios.append(
                candidate_metrics["index_bytes"]
                / raw_metrics["index_bytes"]
            )

    recall5_delta = candidate_recall5 - raw_recall5
    full5_delta = candidate_full5 - raw_full5
    recall10_delta = candidate_recall10 - raw_recall10
    return {
        "candidate": name,
        "comparator": "RAW-SPEC under BM25",
        "Recall@5_delta": recall5_delta,
        "FullCoverage@5_delta": full5_delta,
        "Recall@10_delta": recall10_delta,
        "retrieval_p95_ratio_max": (
            max(p95_ratios)
            if p95_ratios
            else None
        ),
        "index_bytes_ratio_max": (
            max(index_ratios)
            if index_ratios
            else None
        ),
        "quality_gain_gate": (
            recall5_delta >= 0.02
            or full5_delta >= 0.02
        ),
        "Recall@10_guardrail": recall10_delta >= -0.005,
        "latency_guardrail": (
            bool(p95_ratios)
            and max(p95_ratios) <= 1.5
        ),
        "index_size_guardrail": (
            bool(index_ratios)
            and max(index_ratios) <= 3.0
        ),
        "confirmation_claim_allowed": False,
    }


def evaluate(freeze_dir: Path, intent_dir: Path) -> dict[str, Any]:
    amendment = json.loads(AMENDMENT_PATH.read_text(encoding="utf-8"))
    if amendment["status"] != "frozen_before_intent_manual_dev_scoring":
        raise RuntimeError("intent-manual amendment is not frozen")
    if amendment["evaluation"]["confirmation_allowed"] is not False:
        raise RuntimeError("confirmation must remain sealed")

    result = base.evaluate(freeze_dir)
    result["intent_manual"] = {
        "amendment_path": str(AMENDMENT_PATH.relative_to(ROOT)),
        "amendment_sha256": _file_sha(AMENDMENT_PATH),
        "generator_revision": amendment["generator"]["revision"],
        "fusion": amendment["evaluation"]["typed_plus_intent_fusion"],
    }
    result["conditions_scored"] = [
        *result["conditions_scored"],
        *CONDITIONS,
    ]
    result["conditions_blocked"] = {}
    result["confirmation_state"] = "sealed_not_generated_not_scored"

    freeze = result["freeze_manifest"]
    task_rows = json.loads(
        (freeze_dir / "dev-tasks.json").read_text(encoding="utf-8")
    )

    for size in CATALOG_SIZES:
        registry = base._load_registry(
            freeze_dir / f"catalog-{size}.json"
        )
        tools = sorted(registry.tools(), key=lambda item: item.key)
        documents = base._documents(registry)
        intent_texts = _manual_texts(
            intent_dir / f"intent-manual-{size}.json",
            tools,
            expected_catalog_sha256=(
                freeze["catalogs"][str(size)]["sha256"]
            ),
        )
        for condition in CONDITIONS:
            result["catalog_sizes"][str(size)][condition] = (
                _evaluate_condition(
                    documents=documents,
                    task_rows=task_rows,
                    retriever=IntentRetriever(
                        documents,
                        intent_texts,
                        condition,
                    ),
                )
            )

    raw = [
        result["catalog_sizes"][str(size)]["RAW-SPEC"]
        for size in CATALOG_SIZES
    ]
    result["dev_gates_descriptive"] = {
        "TYPED-MULTIFIELD": result["dev_gate_descriptive"],
        **{
            condition: _gate(
                raw,
                [
                    result["catalog_sizes"][str(size)][condition]
                    for size in CATALOG_SIZES
                ],
                name=condition,
            )
            for condition in CONDITIONS
        },
    }
    result["promotion_ready_on_dev"] = {
        condition: all(
            (
                gate["quality_gain_gate"],
                gate["Recall@10_guardrail"],
                gate["latency_guardrail"],
                gate["index_size_guardrail"],
            )
        )
        for condition, gate in result["dev_gates_descriptive"].items()
    }
    result["promotion_note"] = (
        "DEV is tuning-eligible. No condition may be promoted until an exact "
        "candidate is frozen and the still-sealed confirmation surface is "
        "generated and scored once."
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-dir", type=Path, required=True)
    parser.add_argument("--intent-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    result = evaluate(args.freeze_dir, args.intent_dir)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "dev_gates_descriptive": result["dev_gates_descriptive"],
                "promotion_ready_on_dev": result["promotion_ready_on_dev"],
                "confirmation_state": result["confirmation_state"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()

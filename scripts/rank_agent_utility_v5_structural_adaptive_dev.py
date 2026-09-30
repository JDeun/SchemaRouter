"""Rank the original #430 DEV surface with the confirmed structural retriever."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schemarouter import SchemaPlanner  # noqa: E402
from schemarouter.planner import (  # noqa: E402
    _STRUCTURAL_OPERATION_FAMILY_BONUS,
    _STRUCTURAL_TOOL_IDENTIFIER_BONUS,
)
from scripts.rank_agent_utility_v5_adaptive_dev import (  # noqa: E402
    CATALOG_SIZES,
    MAX_K,
    MODEL_NAME,
    MODEL_REVISION,
    _load_registry,
    _sha,
    _tool_tokens,
    _verify_freeze,
)

PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-adaptive-depth-preregistration.json"
)


def _verify_preregistered_identity(
    manifest: dict[str, Any],
    prereg: dict[str, Any],
) -> None:
    dev = prereg["development_surface"]
    if manifest["task_rows_sha256"] != dev["task_rows_sha256"]:
        raise RuntimeError("structural adaptive DEV task hash drifted")
    if (
        manifest["catalog_family_sha256"]
        != dev["catalog_family_sha256"]
    ):
        raise RuntimeError("structural adaptive DEV catalog family drifted")
    for size in CATALOG_SIZES:
        actual = manifest["catalogs"][str(size)]["sha256"]
        expected = dev["catalog_sha256"][str(size)]
        if actual != expected:
            raise RuntimeError(
                f"structural adaptive catalog-{size} hash drifted"
            )

    retriever = prereg["fixed_retriever"]
    if retriever["candidate_id"] != "STRUCT-4.5-1.5":
        raise RuntimeError("unexpected fixed structural candidate")
    if float(retriever["tool_identifier_bonus"]) != float(
        _STRUCTURAL_TOOL_IDENTIFIER_BONUS
    ):
        raise RuntimeError("structural tool bonus drifted from core")
    if float(retriever["operation_family_bonus"]) != float(
        _STRUCTURAL_OPERATION_FAMILY_BONUS
    ):
        raise RuntimeError("structural operation bonus drifted from core")


def rank_dev(
    freeze_dir: Path,
    *,
    local_files_only: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from transformers import AutoTokenizer

    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    manifest = json.loads(
        (freeze_dir / "freeze-manifest.json").read_text(encoding="utf-8")
    )
    if manifest["status"] != "frozen_before_scoring":
        raise RuntimeError("adaptive DEV surface is not frozen before scoring")
    _verify_preregistered_identity(manifest, prereg)

    tasks = _verify_freeze(freeze_dir, manifest)
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        revision=MODEL_REVISION,
        trust_remote_code=False,
        local_files_only=local_files_only,
    )

    rows: list[dict[str, Any]] = []
    for size in CATALOG_SIZES:
        registry = _load_registry(freeze_dir / f"catalog-{size}.json")
        planner = SchemaPlanner(
            registry,
            structural_retrieval=True,
        )
        for task in tasks:
            query = str(task["query"])
            started = time.perf_counter_ns()
            retrieval = planner.retrieve(query, k=MAX_K)
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000

            top10 = retrieval.candidates
            if len(top10) != MAX_K:
                raise RuntimeError(
                    f"catalog {size} returned only {len(top10)} candidates"
                )
            route_ids = [candidate.route_id for candidate in top10]
            scores = [float(candidate.score) for candidate in top10]
            if len(route_ids) != len(set(route_ids)):
                raise RuntimeError(
                    f"{task['task_id']} catalog {size}: duplicate route"
                )
            if any(
                scores[index] < scores[index + 1]
                for index in range(len(scores) - 1)
            ):
                raise RuntimeError(
                    f"{task['task_id']} catalog {size}: score order drift"
                )

            prefix_schema_tokens = {
                str(depth): _tool_tokens(
                    tokenizer,
                    registry,
                    query,
                    route_ids[:depth],
                )
                for depth in range(1, MAX_K + 1)
            }
            if any(
                prefix_schema_tokens[str(depth)]
                > prefix_schema_tokens[str(depth + 1)]
                for depth in range(1, MAX_K)
            ):
                raise RuntimeError(
                    f"{task['task_id']} catalog {size}: token prefix decreased"
                )

            rows.append(
                {
                    **task,
                    "catalog_size": size,
                    "retrieval_latency_ms": elapsed_ms,
                    "ranking": [
                        {
                            "route_id": candidate.route_id,
                            "score": float(candidate.score),
                        }
                        for candidate in top10
                    ],
                    "prefix_schema_tokens": prefix_schema_tokens,
                }
            )

    expected_rows = len(tasks) * len(CATALOG_SIZES)
    if len(rows) != expected_rows:
        raise RuntimeError(
            f"structural adaptive row count drifted: {len(rows)} != {expected_rows}"
        )

    ranking_manifest = {
        "schema_version": 1,
        "issue": prereg["issue"],
        "experiment": prereg["experiment"],
        "surface": "development",
        "fixed_retriever": prereg["fixed_retriever"],
        "freeze_manifest_sha256": _sha(manifest),
        "task_rows_sha256": manifest["task_rows_sha256"],
        "catalog_family_sha256": manifest["catalog_family_sha256"],
        "model": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "tool_token_definition": (
            "B2 SmolLM3 chat-template tool-token delta for each Top-K prefix"
        ),
        "row_count": len(rows),
        "ranking_rows_sha256": _sha(rows),
        "structural_core_used": True,
        "structural_confirmation_rows_used": False,
        "b2_outcomes_used": False,
    }
    return rows, ranking_manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--freeze-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest-out", type=Path, required=True)
    parser.add_argument("--local-files-only", action="store_true")
    args = parser.parse_args()

    rows, manifest = rank_dev(
        args.freeze_dir,
        local_files_only=args.local_files_only,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            )
    args.manifest_out.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()

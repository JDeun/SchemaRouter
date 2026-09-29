"""Generate frozen Top-10 rankings and exact prefix tool-token counts for #430."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from schemarouter import InMemoryRegistry, ToolSpec  # noqa: E402
from scripts.evaluate_agent_utility_phase_a import _rank  # noqa: E402
from scripts.evaluate_agent_utility_phase_b_smollm3 import (  # noqa: E402
    MODEL_NAME,
    MODEL_REVISION,
    SYSTEM_PROMPT,
    _visible_tools,
)

CATALOG_SIZES = (100, 250, 500)
MAX_K = 10


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _load_registry(path: Path) -> InMemoryRegistry:
    payload = json.loads(path.read_text(encoding="utf-8"))
    registry = InMemoryRegistry()
    registry.update_many(
        [ToolSpec.model_validate(row) for row in payload]
    )
    return registry


def _tool_tokens(
    tokenizer: Any,
    registry: InMemoryRegistry,
    query: str,
    selected_routes: list[str],
) -> int:
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": query},
    ]
    tools = _visible_tools(registry, selected_routes)
    prompt = tokenizer.apply_chat_template(
        messages,
        xml_tools=tools,
        add_generation_prompt=True,
        tokenize=False,
        enable_thinking=False,
    )
    without_tools = tokenizer.apply_chat_template(
        messages,
        add_generation_prompt=True,
        tokenize=False,
        enable_thinking=False,
    )
    with_ids = tokenizer(
        prompt,
        add_special_tokens=False,
    )["input_ids"]
    plain_ids = tokenizer(
        without_tools,
        add_special_tokens=False,
    )["input_ids"]
    return max(0, len(with_ids) - len(plain_ids))


def _verify_freeze(
    freeze_dir: Path,
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    tasks = json.loads(
        (freeze_dir / "dev-tasks.json").read_text(encoding="utf-8")
    )
    if _sha(tasks) != manifest["task_rows_sha256"]:
        raise RuntimeError("adaptive DEV task hash does not match freeze manifest")

    for size in CATALOG_SIZES:
        catalog = json.loads(
            (freeze_dir / f"catalog-{size}.json").read_text(encoding="utf-8")
        )
        expected = manifest["catalogs"][str(size)]["sha256"]
        if _sha(catalog) != expected:
            raise RuntimeError(
                f"adaptive DEV catalog-{size} hash does not match freeze manifest"
            )
    return tasks


def rank_dev(
    freeze_dir: Path,
    *,
    local_files_only: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from transformers import AutoTokenizer

    manifest = json.loads(
        (freeze_dir / "freeze-manifest.json").read_text(encoding="utf-8")
    )
    if manifest["status"] != "frozen_before_scoring":
        raise RuntimeError("adaptive DEV surface is not frozen before scoring")

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
        for task in tasks:
            started = time.perf_counter_ns()
            ranking = _rank(registry, str(task["query"]))
            elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
            top10 = ranking[:MAX_K]
            if len(top10) != MAX_K:
                raise RuntimeError(
                    f"catalog {size} returned only {len(top10)} candidates"
                )

            route_ids = [str(item["route_id"]) for item in top10]
            scores = [float(item["score"]) for item in top10]
            if len(route_ids) != len(set(route_ids)):
                raise RuntimeError(
                    f"{task['task_id']} catalog {size}: duplicate Top-10 route"
                )
            if any(
                scores[index] < scores[index + 1]
                for index in range(len(scores) - 1)
            ):
                raise RuntimeError(
                    f"{task['task_id']} catalog {size}: ranking score drift"
                )

            prefix_schema_tokens = {
                str(depth): _tool_tokens(
                    tokenizer,
                    registry,
                    str(task["query"]),
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
                    f"{task['task_id']} catalog {size}: prefix token count decreased"
                )

            rows.append(
                {
                    **task,
                    "catalog_size": size,
                    "retrieval_latency_ms": elapsed_ms,
                    "ranking": [
                        {
                            "route_id": str(item["route_id"]),
                            "score": float(item["score"]),
                        }
                        for item in top10
                    ],
                    "prefix_schema_tokens": prefix_schema_tokens,
                }
            )

    expected_rows = len(tasks) * len(CATALOG_SIZES)
    if len(rows) != expected_rows:
        raise RuntimeError(
            f"adaptive ranking row count drifted: {len(rows)} != {expected_rows}"
        )

    ranking_manifest = {
        "schema_version": 1,
        "issue": 430,
        "experiment": manifest["experiment"],
        "surface": "development",
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
        "scoring_started_only_after_freeze_manifest_validation": True,
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

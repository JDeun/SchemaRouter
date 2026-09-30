"""Rank the frozen #430 DEV surface with confirmed structural retrieval."""

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

from schemarouter import InMemoryRegistry, SchemaPlanner, ToolSpec  # noqa: E402
from schemarouter.planner import (  # noqa: E402
    _STRUCTURAL_OPERATION_FAMILY_BONUS,
    _STRUCTURAL_TOOL_IDENTIFIER_BONUS,
)
from scripts.evaluate_agent_utility_phase_b_smollm3 import (  # noqa: E402
    MODEL_NAME,
    MODEL_REVISION,
    SYSTEM_PROMPT,
    _visible_tools,
)

PREREG = (
    ROOT
    / "benchmarks"
    / "agent-utility-v5-structural-adaptive-depth-preregistration.json"
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
        [ToolSpec.model_validate(tool) for tool in payload]
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
    with_tools = tokenizer.apply_chat_template(
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
        with_tools,
        add_special_tokens=False,
    )["input_ids"]
    plain_ids = tokenizer(
        without_tools,
        add_special_tokens=False,
    )["input_ids"]
    return max(0, len(with_ids) - len(plain_ids))


def _verify_frozen_dev(
    freeze_dir: Path,
    prereg: dict[str, Any],
) -> list[dict[str, Any]]:
    manifest = json.loads(
        (freeze_dir / "freeze-manifest.json")
        .read_text(encoding="utf-8")
    )
    surface = prereg["development_surface"]

    if manifest["task_rows_sha256"] != surface["task_rows_sha256"]:
        raise RuntimeError("structural adaptive DEV task SHA drifted")
    if (
        manifest["catalog_family_sha256"]
        != surface["catalog_family_sha256"]
    ):
        raise RuntimeError(
            "structural adaptive DEV catalog family SHA drifted"
        )

    for size in CATALOG_SIZES:
        expected = surface["catalog_sha256"][str(size)]
        actual = manifest["catalogs"][str(size)]["sha256"]
        if actual != expected:
            raise RuntimeError(
                f"structural adaptive catalog-{size} SHA drifted"
            )

    tasks = json.loads(
        (freeze_dir / "dev-tasks.json")
        .read_text(encoding="utf-8")
    )
    if _sha(tasks) != surface["task_rows_sha256"]:
        raise RuntimeError(
            "structural adaptive task payload does not match SHA"
        )
    return tasks


def rank_dev(
    freeze_dir: Path,
    *,
    local_files_only: bool,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    from transformers import AutoTokenizer

    prereg = json.loads(PREREG.read_text(encoding="utf-8"))
    fixed = prereg["fixed_retriever"]
    if (
        float(fixed["tool_identifier_bonus"])
        != _STRUCTURAL_TOOL_IDENTIFIER_BONUS
    ):
        raise RuntimeError("structural tool bonus drifted")
    if (
        float(fixed["operation_family_bonus"])
        != _STRUCTURAL_OPERATION_FAMILY_BONUS
    ):
        raise RuntimeError("structural operation bonus drifted")

    tasks = _verify_frozen_dev(freeze_dir, prereg)
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        revision=MODEL_REVISION,
        trust_remote_code=False,
        local_files_only=local_files_only,
    )

    rows: list[dict[str, Any]] = []
    for size in CATALOG_SIZES:
        registry = _load_registry(
            freeze_dir / f"catalog-{size}.json"
        )
        if SchemaPlanner(registry).structural_retrieval:
            raise RuntimeError(
                "structural retrieval product default unexpectedly enabled"
            )
        planner = SchemaPlanner(
            registry,
            structural_retrieval=True,
        )

        for task in tasks:
            query = str(task["query"])
            started = time.perf_counter_ns()
            retrieval = planner.retrieve(query, k=MAX_K)
            elapsed_ms = (
                time.perf_counter_ns() - started
            ) / 1_000_000

            candidates = list(retrieval.candidates)
            if len(candidates) != MAX_K:
                raise RuntimeError(
                    f"catalog {size} returned {len(candidates)} candidates"
                )

            route_ids = [
                candidate.route_id
                for candidate in candidates
            ]
            if len(route_ids) != len(set(route_ids)):
                raise RuntimeError(
                    f"{task['task_id']} catalog {size}: duplicate Top-10 route"
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
                    f"{task['task_id']} catalog {size}: "
                    "prefix token count decreased"
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
                        for candidate in candidates
                    ],
                    "prefix_schema_tokens": prefix_schema_tokens,
                }
            )

    expected_rows = len(tasks) * len(CATALOG_SIZES)
    if len(rows) != expected_rows:
        raise RuntimeError(
            f"structural adaptive row count drifted: "
            f"{len(rows)} != {expected_rows}"
        )

    manifest = {
        "schema_version": 1,
        "issue": 430,
        "experiment": prereg["experiment"],
        "surface": "development",
        "fixed_retriever": fixed,
        "task_rows_sha256": prereg[
            "development_surface"
        ]["task_rows_sha256"],
        "catalog_family_sha256": prereg[
            "development_surface"
        ]["catalog_family_sha256"],
        "model": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "tool_token_definition": prereg[
            "token_accounting"
        ]["definition"],
        "row_count": len(rows),
        "ranking_rows_sha256": _sha(rows),
        "structural_confirmation_rows_used": False,
        "b2_outcomes_used": False,
    }
    return rows, manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--freeze-dir",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--out",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--manifest-out",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
    )
    args = parser.parse_args()

    rows, manifest = rank_dev(
        args.freeze_dir,
        local_files_only=args.local_files_only,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(
                json.dumps(
                    row,
                    ensure_ascii=False,
                    sort_keys=True,
                )
                + "\n"
            )
    args.manifest_out.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(manifest, sort_keys=True))


if __name__ == "__main__":
    main()

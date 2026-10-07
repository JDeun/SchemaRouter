"""Run CYT v2 native BM25 composite pruning on visible development fixtures."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from statistics import median
from typing import Any

from cyt_indexer import (
    PolicyContext,
    apply_tool_kind,
    build_catalog_from_tools,
    prune_catalog_bm25_and_retrieve,
)

CYT_OPTIONS = {
    "score_tool": 0.4,
    "score_tool_enum": 0.1,
    "prune_enums": True,
    "pipeline": ["bm25"],
}


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def run(
    catalog_path: Path,
    cases_path: Path,
    repeats: int,
    revision: str,
) -> dict[str, Any]:
    catalog = _load(catalog_path)
    cases = _load(cases_path)["cases"]
    tools = [
        {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "input_schema": tool["input_schema"],
        }
        for tool in catalog["tools"]
    ]
    index = build_catalog_from_tools(tools)
    catalog_data = index.to_catalog_dict()
    scoring = apply_tool_kind(PolicyContext("prune_optional", "prune_all"), "mcp")
    output = apply_tool_kind(PolicyContext("prune_optional", "prune_all"), "mcp")
    rows: list[dict[str, Any]] = []

    for case in cases:
        durations: list[float] = []
        result: dict[str, Any] = {}
        for _ in range(repeats):
            start = time.perf_counter()
            result = prune_catalog_bm25_and_retrieve(
                catalog_data,
                catalog_data,
                index,
                case["query"],
                scoring,
                output,
                options=CYT_OPTIONS,
            )
            durations.append((time.perf_counter() - start) * 1000.0)

        survivors = result.get("tools", [])
        rows.append(
            {
                "id": case["id"],
                "candidate_tools": [tool["name"] for tool in survivors],
                "candidate_count": len(survivors),
                "latency_ms": median(durations),
                "optional_chunk_count_in": result.get("optional_chunk_count_in"),
                "optional_chunk_count_out": result.get("optional_chunk_count_out"),
            }
        )

    return {
        "schema_version": 1,
        "status": "development_unfrozen",
        "performance_evidence": False,
        "catalog_size": len(tools),
        "implementation": {
            "name": "Clear Your Tools native composite BM25",
            "revision": revision,
            "boundary": "cyt-indexer-sdk prune_catalog_bm25_and_retrieve",
            "options": CYT_OPTIONS,
            "repeats_per_query": repeats,
        },
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--cases", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--implementation-revision", required=True)
    args = parser.parse_args()

    payload = run(
        args.catalog,
        args.cases,
        args.repeats,
        args.implementation_revision,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.out)


if __name__ == "__main__":
    main()

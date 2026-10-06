"""Run SmartMCP's native semantic retrieval on the shared external-validation fixture.

This adapter is intentionally external to SmartMCP core. It uses SmartMCP's
EmbeddingIndex and current search-match serialization contract, performs no
upstream tool execution, and emits the implementation-neutral result format.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from statistics import median
from typing import Any

import smartmcp.embedding as smartmcp_embedding
from mcp import types
from smartmcp.embedding import EmbeddingIndex
from smartmcp.server import _build_search_match

try:
    from scripts.external_validation_provenance import implementation_provenance
except ModuleNotFoundError:  # direct `python scripts/...` execution
    from external_validation_provenance import implementation_provenance


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_tools(snapshot_path: Path) -> list[types.Tool]:
    raw = _load(snapshot_path)
    return [
        types.Tool(
            name=item["name"],
            description=item.get("description", ""),
            inputSchema=item.get("inputSchema", {}),
        )
        for item in raw
    ]


def run(
    *,
    package_dir: Path,
    model: str,
    repeats: int,
    implementation_revision: str | None = None,
) -> dict[str, Any]:
    if repeats < 1:
        raise ValueError("repeats must be positive")

    manifest = _load(package_dir / "manifest.json")
    cases = _load(package_dir / manifest["files"]["cases"])
    snapshot_path = package_dir / manifest["files"]["smartmcp_snapshot"]
    tools = _load_tools(snapshot_path)
    top_k = int(manifest["comparison"]["max_candidates"])

    index = EmbeddingIndex(model)
    build_start = time.perf_counter()
    index.build_index(tools)
    index_build_ms = (time.perf_counter() - build_start) * 1000.0

    rows: list[dict[str, Any]] = []
    for case in cases["cases"]:
        query = case["query"]

        # One unmeasured warmup keeps the reported number focused on the hot
        # retrieval path rather than first-call framework overhead.
        index.search(query, top_k=top_k)

        durations: list[float] = []
        final_results: list[tuple[types.Tool, float]] = []
        for _ in range(repeats):
            start = time.perf_counter()
            current = index.search(query, top_k=top_k)
            durations.append((time.perf_counter() - start) * 1000.0)
            final_results = current

        rows.append(
            {
                "id": case["id"],
                "candidate_tools": [tool.name for tool, _ in final_results],
                "exposed_contracts": [
                    _build_search_match(tool, score)
                    for tool, score in final_results
                ],
                "latency_ms": median(durations),
            }
        )

    provenance = implementation_provenance(
        fixture_reference_revision=manifest["source_revisions"].get("smartmcp"),
        explicit_revision=implementation_revision,
        source_path=(
            Path(smartmcp_embedding.__file__)
            if smartmcp_embedding.__file__
            else None
        ),
        distribution="smartmcp-router",
    )

    return {
        "schema_version": 1,
        "package_id": manifest["package_id"],
        "implementation": {
            "name": "SmartMCP semantic discovery",
            **provenance,
            "configuration": {
                "embedding_model": model,
                "repeats_per_query": repeats,
                "top_k": top_k,
                "adapter_boundary": (
                    "EmbeddingIndex.search + SmartMCP search-match serialization; "
                    "no execution"
                ),
            },
        },
        "index_build_ms": index_build_ms,
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="all-MiniLM-L6-v2")
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument(
        "--implementation-revision",
        help="Exact SmartMCP commit/revision used when it cannot be detected from a git checkout.",
    )
    args = parser.parse_args()

    payload = run(
        package_dir=args.package_dir,
        model=args.model,
        repeats=args.repeats,
        implementation_revision=args.implementation_revision,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(args.out)


if __name__ == "__main__":
    main()

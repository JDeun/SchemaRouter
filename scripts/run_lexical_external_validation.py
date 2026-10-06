"""Run the deterministic raw-spec lexical baseline for the shared fixture."""
from __future__ import annotations

import argparse
import json
import math
import re
import time
from collections import Counter
from pathlib import Path
from statistics import median
from typing import Any

try:
    from scripts.external_validation_provenance import implementation_provenance
except ModuleNotFoundError:  # direct `python scripts/...` execution
    from external_validation_provenance import implementation_provenance

_TOKEN_RE = re.compile(r"[\w.-]+", flags=re.UNICODE)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _tokens(text: str) -> list[str]:
    normalized = text.lower().replace("__", " ").replace("_", " ")
    return _TOKEN_RE.findall(normalized)


def _tool_text(tool: dict[str, Any]) -> str:
    parts = [tool["name"], tool.get("description", "")]
    properties = tool.get("inputSchema", {}).get("properties", {})
    for name, spec in properties.items():
        parts.append(name)
        if isinstance(spec, dict):
            description = spec.get("description")
            if isinstance(description, str):
                parts.append(description)
    return " ".join(parts)


class LexicalIndex:
    """Small deterministic TF-IDF cosine baseline over SmartMCP's raw-spec surface."""

    def __init__(self, tools: list[dict[str, Any]]) -> None:
        self.tools = list(tools)
        self._counts = [Counter(_tokens(_tool_text(tool))) for tool in self.tools]

        document_frequency: Counter[str] = Counter()
        for counts in self._counts:
            document_frequency.update(counts.keys())

        total = len(self.tools)
        self._idf = {
            term: math.log((total + 1) / (frequency + 1)) + 1.0
            for term, frequency in document_frequency.items()
        }
        self._vectors = [self._vector(counts) for counts in self._counts]

    def _vector(self, counts: Counter[str]) -> dict[str, float]:
        return {
            term: float(count) * self._idf.get(term, 1.0)
            for term, count in counts.items()
        }

    @staticmethod
    def _cosine(left: dict[str, float], right: dict[str, float]) -> float:
        if not left or not right:
            return 0.0
        dot = sum(value * right.get(term, 0.0) for term, value in left.items())
        left_norm = math.sqrt(sum(value * value for value in left.values()))
        right_norm = math.sqrt(sum(value * value for value in right.values()))
        if not left_norm or not right_norm:
            return 0.0
        return dot / (left_norm * right_norm)

    def search(self, query: str, *, top_k: int) -> list[tuple[dict[str, Any], float]]:
        query_counts = Counter(_tokens(query))
        query_vector = {
            term: float(count) * self._idf.get(term, 1.0)
            for term, count in query_counts.items()
        }
        scored = [
            (tool, self._cosine(query_vector, vector))
            for tool, vector in zip(self.tools, self._vectors, strict=True)
        ]
        scored.sort(key=lambda item: (-item[1], item[0]["name"]))
        return scored[: min(top_k, len(scored))]


def _exposed_contract(tool: dict[str, Any], score: float) -> dict[str, Any]:
    return {
        "target": tool["name"],
        "description": tool.get("description", ""),
        "score": float(score),
        "input_schema": tool.get("inputSchema", {}),
    }


def run(
    *,
    package_dir: Path,
    repeats: int,
    implementation_revision: str | None = None,
) -> dict[str, Any]:
    if repeats < 1:
        raise ValueError("repeats must be positive")

    manifest = _load(package_dir / "manifest.json")
    cases = _load(package_dir / manifest["files"]["cases"])
    snapshot = _load(package_dir / manifest["files"]["smartmcp_snapshot"])
    top_k = int(manifest["comparison"]["max_candidates"])

    build_start = time.perf_counter()
    index = LexicalIndex(snapshot)
    index_build_ms = (time.perf_counter() - build_start) * 1000.0

    rows: list[dict[str, Any]] = []
    for case in cases["cases"]:
        query = case["query"]
        index.search(query, top_k=top_k)

        durations: list[float] = []
        final_results: list[tuple[dict[str, Any], float]] = []
        for _ in range(repeats):
            start = time.perf_counter()
            current = index.search(query, top_k=top_k)
            durations.append((time.perf_counter() - start) * 1000.0)
            final_results = current

        rows.append(
            {
                "id": case["id"],
                "candidate_tools": [tool["name"] for tool, _ in final_results],
                "exposed_contracts": [
                    _exposed_contract(tool, score)
                    for tool, score in final_results
                ],
                "latency_ms": median(durations),
            }
        )

    provenance = implementation_provenance(
        fixture_reference_revision=manifest["source_revisions"].get("schemarouter"),
        explicit_revision=implementation_revision,
        source_path=Path(__file__),
    )

    return {
        "schema_version": 1,
        "package_id": manifest["package_id"],
        "implementation": {
            "name": "raw-spec lexical TF-IDF cosine baseline",
            **provenance,
            "configuration": {
                "repeats_per_query": repeats,
                "top_k": top_k,
                "surface": (
                    "tool name + description + top-level input parameter names/descriptions"
                ),
                "abstention": "none; deterministic ranked Top-K",
            },
        },
        "index_build_ms": index_build_ms,
        "results": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=20)
    parser.add_argument(
        "--implementation-revision",
        help=(
            "Exact benchmark-code commit/revision used when it cannot be detected "
            "from a git checkout."
        ),
    )
    args = parser.parse_args()

    payload = run(
        package_dir=args.package_dir,
        repeats=args.repeats,
        implementation_revision=args.implementation_revision,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(args.out)


if __name__ == "__main__":
    main()

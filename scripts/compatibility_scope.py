"""Classify changed paths for compatibility smoke fan-out."""

from __future__ import annotations

import argparse
import fnmatch
import sys
from collections.abc import Iterable

_PATTERNS: dict[str, tuple[str, ...]] = {
    "full": (
        ".github/workflows/compatibility.yml",
        "scripts/compatibility_scope.py",
        "tests/test_compatibility_scope.py",
    ),
    "openapi": (
        "src/schemarouter/adapters/openapi.py",
        "src/schemarouter/openapi_compatibility.py",
        "src/schemarouter/ingestion.py",
        "scripts/live_openapi_smoke.py",
        "tests/test_openapi*.py",
    ),
    "optimade": (
        "src/schemarouter/adapters/optimade.py",
        "src/schemarouter/ingestion.py",
        "scripts/live_optimade_smoke.py",
        "tests/test_optimade*.py",
    ),
    "providers": (
        "src/schemarouter/provider_profiles.py",
        "scripts/live_materials_project_provider_smoke.py",
        "scripts/live_crossref_provider_smoke.py",
        "scripts/live_tavily_provider_smoke.py",
        "tests/test_provider_profiles.py",
    ),
    "vector": (
        "src/schemarouter/adapters/vector_native.py",
        "src/schemarouter/adapters/vector_store.py",
        "scripts/live_qdrant_smoke.py",
        "scripts/live_pgvector_smoke.py",
        "scripts/live_chroma_smoke.py",
        "tests/test_vector*.py",
    ),
    "record": (
        "src/schemarouter/adapters/record_native.py",
        "src/schemarouter/adapters/record_store.py",
        "scripts/live_mongodb_smoke.py",
        "scripts/live_clickhouse_smoke.py",
        "tests/test_record*.py",
    ),
    "graph": (
        "src/schemarouter/adapters/graph_native.py",
        "src/schemarouter/adapters/graph_store.py",
        "scripts/live_falkordb_smoke.py",
        "tests/test_graph*.py",
        "tests/test_falkordb_native_adapter.py",
    ),
    "matrix": (
        "src/schemarouter/adapters/**",
        "src/schemarouter/ingestion.py",
        "src/schemarouter/provider_profiles.py",
        "scripts/live_*",
        "scripts/aggregate_compatibility_matrix.py",
    ),
}


def classify_paths(paths: Iterable[str]) -> dict[str, bool]:
    normalized = tuple(path.strip().replace("\\", "/") for path in paths if path.strip())
    result = {
        scope: any(
            fnmatch.fnmatchcase(path, pattern)
            for path in normalized
            for pattern in patterns
        )
        for scope, patterns in _PATTERNS.items()
    }
    if result["full"]:
        for scope in result:
            result[scope] = True
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paths", nargs="*")
    parser.add_argument("--github-output", action="store_true")
    args = parser.parse_args()

    paths = args.paths or [line.rstrip("\n") for line in sys.stdin]
    result = classify_paths(paths)
    if args.github_output:
        for key, enabled in result.items():
            print(f"{key}={'true' if enabled else 'false'}")
    else:
        print(" ".join(key for key, enabled in result.items() if enabled))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

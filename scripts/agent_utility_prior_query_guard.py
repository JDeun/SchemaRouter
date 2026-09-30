"""Known-prior query guard for future 0.14 held-out/final-answer corpora.

This module only reads already-authored research surfaces. It never generates
future benchmark content and never performs semantic/fuzzy matching.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any

from benchmarks.agent_utility_b2_catalog import TASKS as B2_TASKS
from benchmarks.agent_utility_v1_catalog import TASKS as B1_TASKS
from benchmarks.agent_utility_v2_catalog import development_rows
from benchmarks.agent_utility_v5_catalog import build_tasks
from benchmarks.agent_utility_v5_structural_confirmation import (
    build_confirmation_tasks,
)
from benchmarks.agent_utility_v5_structural_fixed3_confirmation import (
    build_fixed3_confirmation_tasks,
)
from scripts.agent_utility_v7_projection import (
    build_projection_task,
    projection_authoring_slots,
)


def normalize_query(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return " ".join(normalized.split()).casefold()


def known_prior_queries() -> dict[str, set[str]]:
    surfaces: dict[str, set[str]] = {
        "b1": {
            normalize_query(str(task.query))
            for task in B1_TASKS
        },
        "b2": {
            normalize_query(str(task.query))
            for task in B2_TASKS
        },
        "representation_dev": {
            normalize_query(str(row["query"]))
            for row in development_rows()
        },
        "adaptive_dev": {
            normalize_query(str(task["query"]))
            for task in build_tasks()
        },
        "structural_confirmation": {
            normalize_query(str(task["query"]))
            for task in build_confirmation_tasks()
        },
        "fixed3_confirmation": {
            normalize_query(str(task["query"]))
            for task in build_fixed3_confirmation_tasks()
        },
        "projection": {
            normalize_query(
                str(build_projection_task(slot, index)["query"])
            )
            for index, slot in enumerate(projection_authoring_slots())
        },
    }
    return {
        name: {query for query in queries if query}
        for name, queries in surfaces.items()
    }


def _query_set_sha256(queries: set[str]) -> str:
    encoded = json.dumps(
        sorted(queries),
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def flattened_known_prior_queries() -> set[str]:
    return set().union(*known_prior_queries().values())


def known_prior_query_manifest() -> dict[str, Any]:
    surfaces = known_prior_queries()
    union = set().union(*surfaces.values())
    return {
        "surface_counts": {
            name: len(queries)
            for name, queries in sorted(surfaces.items())
        },
        "surface_sha256": {
            name: _query_set_sha256(queries)
            for name, queries in sorted(surfaces.items())
        },
        "union_count": len(union),
        "union_sha256": _query_set_sha256(union),
    }


def query_set_sha256(queries: set[str]) -> str:
    return _query_set_sha256(queries)


def queries_from_corpus(path: Path) -> set[str]:
    payload: Any = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        rows = payload.get("tasks", payload.get("rows"))
    else:
        rows = payload
    if not isinstance(rows, list):
        raise ValueError(
            f"{path}: forbidden corpus must be a list or object with tasks/rows"
        )

    queries: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{path}: row {index} must be an object")
        query = row.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(
                f"{path}: row {index} query must be a non-empty string"
            )
        queries.add(normalize_query(query))
    return queries


def assert_no_prior_query_overlap(
    queries: set[str],
    *,
    extra_forbidden_queries: set[str] | None = None,
) -> None:
    known = known_prior_queries()
    collisions: dict[str, list[str]] = {}
    for surface, prior in known.items():
        overlap = sorted(queries & prior)
        if overlap:
            collisions[surface] = overlap[:5]

    if extra_forbidden_queries:
        overlap = sorted(queries & extra_forbidden_queries)
        if overlap:
            collisions["extra_forbidden_corpus"] = overlap[:5]

    if collisions:
        details = "; ".join(
            f"{surface}={values!r}"
            for surface, values in sorted(collisions.items())
        )
        raise ValueError(
            "query overlaps a prior benchmark surface: " + details
        )

"""Read-only per-language retrieval audit for the immutable #432 archive.

This tool reports initial retrieval *only*, not SR-PROGRESSIVE dynamic
candidate_history nor final-agent task success. No models, networking, writes
to scientific inputs, scoring or training.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any
from zipfile import ZipFile

FROZEN_SOURCE = "30663de8f618bc88a893d9bf6214035a70e8e894"
CANONICAL_TASKS_SHA = "452482a8fd1682b1473202f04585ae551df322c9bdc41141fa10abb689f2d01b"
CANONICAL_EPISODE_TASKS = 780
CATALOGS = (100, 250, 500, 1000)
CONDITIONS = ("FULL", "SR-5", "SR-10", "SR-PROGRESSIVE", "ORACLE")
LANGUAGES = ("en", "ko", "ja", "es", "de", "mixed")


def audit(corpus: dict[str, Any], retrieval: dict[str, Any]) -> dict[str, Any]:
    """Fail closed on row omission/duplication, changed science, or bad denominators."""
    if (corpus.get("generator_source_revision") != FROZEN_SOURCE
            or corpus.get("tasks_sha256") != CANONICAL_TASKS_SHA
            or retrieval.get("tasks_sha256") != CANONICAL_TASKS_SHA
            or retrieval.get("issue") != 432
            or corpus.get("issue") != 432):
        raise ValueError("frozen #432 source or task digest drift")
    tasks = corpus.get("tasks")
    if not isinstance(tasks, list) or len(tasks) != CANONICAL_EPISODE_TASKS:
        raise ValueError("missing frozen semantic task population")
    by_id: dict[str, dict[str, Any]] = {}
    for task in tasks:
        task_id = task.get("semantic_task_id")
        language = task.get("language")
        required = task.get("required_routes")
        if (not isinstance(task_id, str) or task_id in by_id
                or language not in LANGUAGES or not isinstance(required, list)
                or type(task.get("supported")) is not bool
                or bool(required) != task["supported"]):
            raise ValueError("invalid frozen task metadata")
        by_id[task_id] = task
    if (retrieval.get("conditions") != list(CONDITIONS)
            or retrieval.get("catalog_sizes") != list(CATALOGS)):
        raise ValueError("changed initial retrieval condition or catalog manifest")
    rows = retrieval.get("rows")
    expected_rows = len(by_id) * len(CATALOGS) * len(CONDITIONS)
    if not isinstance(rows, list) or len(rows) != expected_rows:
        raise ValueError("incomplete initial retrieval rows")
    seen: set[tuple[str, int, str]] = set()
    counts: dict[tuple[int, str, str], dict[str, int]] = defaultdict(
        lambda: {"tasks": 0, "supported": 0, "unsupported": 0,
                 "required": 0, "hits": 0, "all_covered": 0}
    )
    for row in rows:
        task_id = row.get("semantic_task_id")
        if task_id not in by_id:
            raise ValueError("unrecognized frozen semantic task")
        task = by_id[task_id]
        catalog, condition = row.get("catalog_size"), row.get("condition")
        if (type(catalog) is not int or catalog not in CATALOGS
                or condition not in CONDITIONS):
            raise ValueError("invalid catalog or condition")
        unique = (task_id, catalog, condition)
        if unique in seen:
            raise ValueError("duplicate retrieval identity")
        seen.add(unique)
        required = len(task["required_routes"])
        hits = row.get("required_hits")
        covered = row.get("all_required_covered")
        if (row.get("language") != task["language"]
                or row.get("task_stratum") != task["task_stratum"]
                or row.get("supported") is not task["supported"]
                or type(row.get("required_count")) is not int
                or row["required_count"] != required
                or type(hits) is not int or not 0 <= hits <= required
                or (required and (type(covered) is not bool
                                  or covered != (hits == required)))
                or (not required and (covered is not None or hits != 0))):
            raise ValueError("invalid retrieval row provenance or coverage")
        group = counts[(catalog, condition, task["language"])]
        group["tasks"] += 1
        group["supported" if required else "unsupported"] += 1
        group["required"] += required
        group["hits"] += hits
        group["all_covered"] += int(bool(covered))
    if len(seen) != expected_rows:
        raise ValueError("missing retrieval row identities")
    summaries = []
    for (catalog, condition, language), group in sorted(counts.items()):
        denom = group["required"]
        if group["tasks"] != CANONICAL_EPISODE_TASKS // len(LANGUAGES):
            raise ValueError("unbalanced frozen language group")
        summaries.append({
            "catalog_size": catalog,
            "condition": condition,
            "language": language,
            **group,
            "initial_required_route_recall": (
                group["hits"] / denom if denom else None
            ),
            "all_required_coverage_supported": (
                group["all_covered"] / group["supported"]
                if group["supported"] else None
            ),
        })
    if len(summaries) != len(CATALOGS) * len(CONDITIONS) * len(LANGUAGES):
        raise ValueError("missing catalog-condition-language cell")
    return {
        "schema_version": 1,
        "kind": "frozen_432_initial_retrieval_language_audit_only",
        "warning": "Not progressive candidate_history and not final-agent task success",
        "frozen_source": FROZEN_SOURCE,
        "tasks_sha256": CANONICAL_TASKS_SHA,
        "task_count": len(by_id),
        "retrieval_rows": len(rows),
        "groups": summaries,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-zip", type=Path, required=True)
    parser.add_argument("--expected-zip-sha256", required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    digest = hashlib.sha256(args.canonical_zip.read_bytes()).hexdigest()
    if digest != args.expected_zip_sha256.removeprefix("sha256:"):
        raise ValueError("held-out artifact ZIP digest mismatch")
    with ZipFile(args.canonical_zip) as archive:
        corpus = json.loads(
            archive.read("artifacts/recovery-plan/heldout-corpus.json")
        )
        retrieval = json.loads(
            archive.read("artifacts/recovery-plan/heldout-retrieval.json")
        )
    output = audit(corpus, retrieval)
    output["canonical_zip_sha256"] = f"sha256:{digest}"
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()

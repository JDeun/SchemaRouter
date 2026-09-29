"""Validate future #432/#424 corpus identity against frozen authoring slots.

This validator does not generate benchmark content and does not authorize inference.
It enforces only cross-balance/identity integrity and exact normalized-query uniqueness
once independently authored corpus rows exist.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]

SURFACES = {
    "heldout": {
        "generator": ROOT / "scripts" / "generate_agent_utility_v3_heldout_authoring_plan.py",
        "stratum_key": "task_stratum",
        "expected_count": 780,
    },
    "final-answer": {
        "generator": ROOT / "scripts" / "generate_agent_utility_v4_final_answer_authoring_plan.py",
        "stratum_key": "answer_task_stratum",
        "expected_count": 144,
    },
}


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _load_generator(path: Path):
    spec = importlib.util.spec_from_file_location(
        f"_corpus_plan_{path.stem}",
        path,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load authoring-plan generator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def expected_slots(surface: str) -> list[dict[str, Any]]:
    config = SURFACES[surface]
    module = _load_generator(config["generator"])
    plan = module.build_authoring_plan()
    slots = list(plan["slots"])
    if len(slots) != config["expected_count"]:
        raise RuntimeError(
            f"{surface} authoring plan drifted: "
            f"{len(slots)} != {config['expected_count']}"
        )
    return slots


def _normalize_query(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text)
    return " ".join(normalized.split()).casefold()


def validate_rows(surface: str, rows: list[dict[str, Any]]) -> dict[str, Any]:
    if surface not in SURFACES:
        raise ValueError(f"unsupported surface: {surface}")

    config = SURFACES[surface]
    stratum_key = str(config["stratum_key"])
    slots = expected_slots(surface)
    expected = {
        str(slot["semantic_task_id"]): slot
        for slot in slots
    }

    if len(rows) != len(expected):
        raise ValueError(
            f"{surface} row count mismatch: {len(rows)} != {len(expected)}"
        )

    seen_ids: set[str] = set()
    normalized_queries: dict[str, str] = {}

    for index, row in enumerate(rows):
        task_id = str(row.get("semantic_task_id", ""))
        if not task_id:
            raise ValueError(f"row {index} missing semantic_task_id")
        if task_id in seen_ids:
            raise ValueError(f"duplicate semantic_task_id: {task_id}")
        seen_ids.add(task_id)

        slot = expected.get(task_id)
        if slot is None:
            raise ValueError(f"unknown semantic_task_id: {task_id}")

        if row.get(stratum_key) != slot[stratum_key]:
            raise ValueError(
                f"{task_id} {stratum_key} drifted: "
                f"{row.get(stratum_key)!r} != {slot[stratum_key]!r}"
            )
        if row.get("language") != slot["language"]:
            raise ValueError(
                f"{task_id} language drifted: "
                f"{row.get('language')!r} != {slot['language']!r}"
            )

        query = row.get("query")
        if not isinstance(query, str) or not query.strip():
            raise ValueError(f"{task_id} query must be a non-empty string")

        normalized = _normalize_query(query)
        previous = normalized_queries.get(normalized)
        if previous is not None:
            raise ValueError(
                "normalized query text must be unique across semantic tasks: "
                f"{previous} and {task_id}"
            )
        normalized_queries[normalized] = task_id

    missing = sorted(set(expected).difference(seen_ids))
    if missing:
        raise ValueError(
            f"{surface} corpus is missing authoring slots: {missing[:10]}"
        )

    identity_rows = [
        {
            "semantic_task_id": row["semantic_task_id"],
            stratum_key: row[stratum_key],
            "language": row["language"],
        }
        for row in sorted(rows, key=lambda item: str(item["semantic_task_id"]))
    ]
    content_rows = [
        {
            "semantic_task_id": row["semantic_task_id"],
            "query": row["query"],
        }
        for row in sorted(rows, key=lambda item: str(item["semantic_task_id"]))
    ]

    return {
        "surface": surface,
        "row_count": len(rows),
        "identity_sha256": _sha(identity_rows),
        "query_content_sha256": _sha(content_rows),
        "normalized_query_count": len(normalized_queries),
        "authoring_slot_count": len(expected),
        "content_generation_authorized_by_validator": False,
        "inference_authorized_by_validator": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--surface", choices=tuple(SURFACES), required=True)
    parser.add_argument("--input", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    rows = payload["rows"] if isinstance(payload, dict) else payload
    if not isinstance(rows, list):
        raise SystemExit("input must be a JSON list or object with a rows list")

    result = validate_rows(args.surface, rows)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
